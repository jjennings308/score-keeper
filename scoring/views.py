from django.views.generic import ListView, DetailView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum

from games.models import Game
from players.models import Player, Team
from .models import Session, SessionPlayer, Round, Score


def get_next_dealer(session, current_round_number):
    """
    Return the SessionPlayer who should deal for a given round number.
    Rotates through participants in display_order, wrapping back to the start.
    Round 1 = first participant, Round 2 = second, etc.
    """
    participants = list(session.participants.order_by('display_order'))
    if not participants:
        return None
    index = (current_round_number - 1) % len(participants)
    return participants[index]


def build_score_context(session):
    """Shared helper to build all score sheet context data."""
    participants = session.participants.select_related('player', 'team').order_by('display_order')
    rounds = session.rounds.select_related('dealer__player', 'dealer__team').prefetch_related('scores').order_by('round_number')

    score_grid = {}
    for r in rounds:
        score_grid[r] = {}
        for score in r.scores.all():
            score_grid[r][score.session_player_id] = score

    totals = {}
    for sp in participants:
        totals[sp.id] = sp.scores.aggregate(total=Sum('points'))['total'] or 0

    if totals:
        if session.game.scoring_mode == Game.ScoringMode.LOWEST:
            best_score = min(totals.values())
        else:
            best_score = max(totals.values())
    else:
        best_score = None

    last_round_has_scores = False
    if rounds:
        last_round = list(rounds)[-1]
        last_round_has_scores = bool(score_grid.get(last_round, {}))

    at_round_limit = (
        session.game.num_rounds is not None and
        rounds.count() >= session.game.num_rounds
    )

    return {
        'session': session,
        'participants': participants,
        'rounds': rounds,
        'score_grid': score_grid,
        'totals': totals,
        'best_score': best_score,
        'last_round_has_scores': last_round_has_scores,
        'at_round_limit': at_round_limit,
    }


class SessionListView(ListView):
    model = Session
    template_name = 'scoring/session_list.html'
    context_object_name = 'sessions'
    ordering = ['-started_at']

    def get_queryset(self):
        return Session.objects.select_related('game').prefetch_related('participants').all()


class SessionCreateView(LoginRequiredMixin, View):
    """Step 1 — Select a game."""
    template_name = 'scoring/session_create.html'

    def get(self, request):
        all_games = Game.objects.order_by('name')
        selected_game_id = request.GET.get('game')
        return render(request, self.template_name, {
            'games': all_games,
            'individual_games': all_games.filter(play_mode=Game.PlayMode.INDIVIDUAL),
            'team_games': all_games.filter(play_mode=Game.PlayMode.TEAM),
            'selected_game_id': int(selected_game_id) if selected_game_id else None,
        })

    def post(self, request):
        game_id = request.POST.get('game')
        if not game_id:
            messages.error(request, 'Please select a game.')
            return redirect('scoring:create')
        return redirect('scoring:create_players', game_id=game_id)


class SessionPlayersView(LoginRequiredMixin, View):
    """Step 2 — Select players or teams and start session."""
    template_name = 'scoring/session_players.html'

    def get(self, request, game_id):
        game = get_object_or_404(Game, pk=game_id)
        return render(request, self.template_name, {
            'game': game,
            'players': Player.objects.order_by('name'),
            'teams': Team.objects.prefetch_related('players').order_by('name'),
        })

    def post(self, request, game_id):
        game = get_object_or_404(Game, pk=game_id)
        session = Session.objects.create(game=game, created_by=request.user)

        if game.play_mode == Game.PlayMode.TEAM:
            team_ids = request.POST.getlist('teams')
            if len(team_ids) < 2:
                messages.error(request, 'Please select at least 2 teams.')
                session.delete()
                return render(request, self.template_name, {
                    'game': game,
                    'players': Player.objects.order_by('name'),
                    'teams': Team.objects.prefetch_related('players').order_by('name'),
                })
            for order, team_id in enumerate(team_ids):
                team = get_object_or_404(Team, pk=team_id)
                SessionPlayer.objects.create(
                    session=session,
                    team=team,
                    display_order=order,
                )
        else:
            player_ids = request.POST.getlist('players')
            if len(player_ids) < 2:
                messages.error(request, 'Please select at least 2 players.')
                session.delete()
                return render(request, self.template_name, {
                    'game': game,
                    'players': Player.objects.order_by('name'),
                    'teams': Team.objects.prefetch_related('players').order_by('name'),
                })
            for order, player_id in enumerate(player_ids):
                player = get_object_or_404(Player, pk=player_id)
                SessionPlayer.objects.create(
                    session=session,
                    player=player,
                    display_order=order,
                )

        # Create first round, assigning dealer if game requires it
        first_dealer = get_next_dealer(session, 1) if game.requires_dealer else None
        Round.objects.create(session=session, round_number=1, dealer=first_dealer)

        messages.success(request, 'Session started! Good luck everyone.')
        return redirect('scoring:detail', pk=session.pk)


class SessionDetailView(DetailView):
    """The live score sheet."""
    model = Session
    template_name = 'scoring/session_detail.html'
    context_object_name = 'session'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(build_score_context(self.object))
        return ctx


class AddRoundView(LoginRequiredMixin, View):
    """Add a new round to a session via HTMX."""

    def post(self, request, pk):
        session = get_object_or_404(Session, pk=pk)

        if session.is_complete:
            return HttpResponse('Session is complete.', status=400)

        current_count = session.rounds.count()
        if session.game.num_rounds and current_count >= session.game.num_rounds:
            return HttpResponse(
                f'Maximum rounds ({session.game.num_rounds}) reached.', status=400
            )

        next_round_number = current_count + 1
        next_dealer = get_next_dealer(session, next_round_number) if session.game.requires_dealer else None
        Round.objects.create(session=session, round_number=next_round_number, dealer=next_dealer)
        return render(request, 'scoring/partials/score_table.html', build_score_context(session))


class SaveScoreView(LoginRequiredMixin, View):
    def post(self, request, session_pk):
        session = get_object_or_404(Session, pk=session_pk)
        round_id = request.POST.get('round_id')
        session_player_id = request.POST.get('session_player_id')
        points_raw = request.POST.get('points', '').strip()

        if not points_raw:
            Score.objects.filter(
                round_id=round_id,
                session_player_id=session_player_id
            ).delete()
        else:
            try:
                points = int(points_raw)
            except ValueError:
                return HttpResponse('Invalid score.', status=400)

            if not session.game.allow_negative and points < 0:
                return HttpResponse('Negative scores not allowed.', status=400)

            Score.objects.update_or_create(
                round_id=round_id,
                session_player_id=session_player_id,
                defaults={'points': points},
            )

        # Check for winner
        winner = session.check_winner()
        if winner and not session.is_complete:
            session.winner = winner.display_name
            session.is_complete = True
            session.ended_at = timezone.now()
            session.save()

        # Auto-add next round if all participants have scored
        if not session.is_complete:
            current_round = Round.objects.get(pk=round_id)
            participant_count = session.participants.count()
            scores_in_round = Score.objects.filter(round=current_round).count()

            if scores_in_round >= participant_count:
                current_round_count = session.rounds.count()
                if not session.game.num_rounds or current_round_count < session.game.num_rounds:
                    next_round_number = current_round.round_number + 1
                    if not Round.objects.filter(session=session, round_number=next_round_number).exists():
                        next_dealer = get_next_dealer(session, next_round_number) if session.game.requires_dealer else None
                        Round.objects.create(
                            session=session,
                            round_number=next_round_number,
                            dealer=next_dealer,
                        )

        return render(request, 'scoring/partials/score_table.html', build_score_context(session))


class CompleteSessionView(LoginRequiredMixin, View):
    """Manually mark a session as complete."""

    def post(self, request, pk):
        session = get_object_or_404(Session, pk=pk)

        totals = session.get_totals()
        if totals:
            if session.game.scoring_mode == Game.ScoringMode.LOWEST:
                winning_sp = min(totals, key=totals.get)
            else:
                winning_sp = max(totals, key=totals.get)
            session.winner = winning_sp.display_name

        session.is_complete = True
        session.ended_at = timezone.now()
        session.save()

        messages.success(request, f'Session complete! Winner: {session.winner}')
        return redirect('scoring:detail', pk=session.pk)


class TotalsRowView(View):
    """Return just the totals row."""

    def get(self, request, session_pk):
        session = get_object_or_404(Session, pk=session_pk)
        ctx = build_score_context(session)
        return render(request, 'scoring/partials/totals_row.html', ctx)
