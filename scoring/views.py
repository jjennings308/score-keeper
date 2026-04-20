from django.views.generic import ListView, DetailView, CreateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse
from django.urls import reverse
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum

from games.models import Game
from players.models import Player
from .models import Session, SessionPlayer, Round, Score


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
        games = Game.objects.filter(play_mode=Game.PlayMode.INDIVIDUAL).order_by('name')
        # Pre-select game if passed via query param from game detail page
        selected_game_id = request.GET.get('game')
        return render(request, self.template_name, {
            'games': games,
            'selected_game_id': int(selected_game_id) if selected_game_id else None,
        })

    def post(self, request):
        game_id = request.POST.get('game')
        if not game_id:
            messages.error(request, 'Please select a game.')
            return redirect('scoring:create')
        return redirect('scoring:create_players', game_id=game_id)


class SessionPlayersView(LoginRequiredMixin, View):
    """Step 2 — Select players and start session."""
    template_name = 'scoring/session_players.html'

    def get(self, request, game_id):
        game = get_object_or_404(Game, pk=game_id)
        players = Player.objects.order_by('name')
        return render(request, self.template_name, {
            'game': game,
            'players': players,
        })

    def post(self, request, game_id):
        game = get_object_or_404(Game, pk=game_id)
        player_ids = request.POST.getlist('players')

        if len(player_ids) < 2:
            messages.error(request, 'Please select at least 2 players.')
            players = Player.objects.order_by('name')
            return render(request, self.template_name, {
                'game': game,
                'players': players,
            })

        # Create the session
        session = Session.objects.create(
            game=game,
            created_by=request.user,
        )

        # Create SessionPlayer entries in selected order
        for order, player_id in enumerate(player_ids):
            player = get_object_or_404(Player, pk=player_id)
            SessionPlayer.objects.create(
                session=session,
                player=player,
                display_order=order,
            )

        # Create the first round automatically
        Round.objects.create(session=session, round_number=1)

        messages.success(request, f'Session started! Good luck everyone.')
        return redirect('scoring:detail', pk=session.pk)


class SessionDetailView(DetailView):
    """The live score sheet."""
    model = Session
    template_name = 'scoring/session_detail.html'
    context_object_name = 'session'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        session = self.object
        participants = session.participants.select_related('player').order_by('display_order')
        rounds = session.rounds.prefetch_related('scores').order_by('round_number')

        # Build score grid: {round: {session_player_id: score_obj}}
        score_grid = {}
        for round in rounds:
            score_grid[round] = {}
            for score in round.scores.all():
                score_grid[round][score.session_player_id] = score

        # Running totals per participant
        totals = {}
        for sp in participants:
            totals[sp.id] = sp.scores.aggregate(total=Sum('points'))['total'] or 0

        # Best score for highlighting in totals row
        if totals:
            if session.game.scoring_mode == Game.ScoringMode.LOWEST:
                best_score = min(totals.values())
            else:
                best_score = max(totals.values())
        else:
            best_score = None

        # Check if last round has any scores entered
        last_round_has_scores = False
        if rounds:
            last_round = rounds[len(rounds) - 1]
            last_round_has_scores = score_grid.get(last_round, {}) != {}

        ctx['last_round_has_scores'] = last_round_has_scores
        ctx['at_round_limit'] = (
            session.game.num_rounds is not None and 
            rounds.count() >= session.game.num_rounds
        )    
        ctx['participants'] = participants
        ctx['rounds'] = rounds
        ctx['score_grid'] = score_grid
        ctx['totals'] = totals
        ctx['best_score'] = best_score
        return ctx


class AddRoundView(LoginRequiredMixin, View):
    """Add a new round to a session via HTMX."""

    def post(self, request, pk):
        session = get_object_or_404(Session, pk=pk)

        if session.is_complete:
            return HttpResponse('Session is complete.', status=400)

        # Check round limit
        current_count = session.rounds.count()
        if session.game.num_rounds and current_count >= session.game.num_rounds:
            return HttpResponse(
                f'Maximum rounds ({session.game.num_rounds}) reached.', status=400
            )

        new_round = Round.objects.create(
            session=session,
            round_number=current_count + 1,
        )

        # Re-render just the score table body via HTMX
        participants = session.participants.select_related('player').order_by('display_order')
        rounds = session.rounds.prefetch_related('scores').order_by('round_number')

        score_grid = {}
        for r in rounds:
            score_grid[r] = {}
            for score in r.scores.all():
                score_grid[r][score.session_player_id] = score

        totals = {}
        for sp in participants:
            totals[sp.id] = sp.scores.aggregate(total=Sum('points'))['total'] or 0
            
        # Best score for highlighting in totals row
        if totals:
            if session.game.scoring_mode == Game.ScoringMode.LOWEST:
                best_score = min(totals.values())
            else:
                best_score = max(totals.values())
        else:
            best_score = None

        # Round limit checks
        last_round_has_scores = False
        if rounds:
            last_round = list(rounds)[-1]
            last_round_has_scores = bool(score_grid.get(last_round, {}))

        at_round_limit = (
            session.game.num_rounds is not None and
            rounds.count() >= session.game.num_rounds
        )
            
        return render(request, 'scoring/partials/score_table.html', {
            'session': session,
            'participants': participants,
            'rounds': rounds,
            'score_grid': score_grid,
            'totals': totals,
            'best_score': best_score,
            'last_round_has_scores': last_round_has_scores,
            'at_round_limit': at_round_limit,
        })


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

        # Build score grid
        rounds = session.rounds.prefetch_related('scores').order_by('round_number')
        score_grid = {}
        for r in rounds:
            score_grid[r] = {}
            for score in r.scores.all():
                score_grid[r][score.session_player_id] = score

        participants = session.participants.select_related('player').order_by('display_order')
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
            
        # Auto-add next round if all players have scored in the current round
        # and we haven't hit the round limit
        if not session.is_complete:
            current_round = Round.objects.get(pk=round_id)
            participant_count = participants.count()
            scores_in_round = Score.objects.filter(round=current_round).count()

            if scores_in_round >= participant_count:
                # All players have scored this round
                current_round_count = rounds.count()
                if not session.game.num_rounds or current_round_count < session.game.num_rounds:
                    # Check a next round doesn't already exist
                    next_round_number = current_round.round_number + 1
                    if not Round.objects.filter(session=session, round_number=next_round_number).exists():
                        Round.objects.create(session=session, round_number=next_round_number)
                        # Refresh rounds queryset to include new round
                        rounds = session.rounds.prefetch_related('scores').order_by('round_number')
                        score_grid = {}
                        for r in rounds:
                            score_grid[r] = {}
                            for score in r.scores.all():
                                score_grid[r][score.session_player_id] = score
        
        # Calculate once after potential new round
        last_round_has_scores = False
        if rounds:
            last_round = list(rounds)[-1]
            last_round_has_scores = bool(score_grid.get(last_round, {}))

        at_round_limit = (
            session.game.num_rounds is not None and
            rounds.count() >= session.game.num_rounds
        )

        return render(request, 'scoring/partials/score_table.html', {
            'session': session,
            'participants': participants,
            'rounds': rounds,
            'score_grid': score_grid,
            'totals': totals,
            'best_score': best_score,
            'last_round_has_scores': last_round_has_scores,
            'at_round_limit': at_round_limit,
        })


class CompleteSessionView(LoginRequiredMixin, View):
    """Manually mark a session as complete."""

    def post(self, request, pk):
        session = get_object_or_404(Session, pk=pk)

        # Determine winner based on scoring mode
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
    """Return just the totals row — used by HTMX after score updates."""

    def get(self, request, session_pk):
        session = get_object_or_404(Session, pk=session_pk)
        participants = session.participants.select_related('player').order_by('display_order')
        totals = {}
        for sp in participants:
            totals[sp.id] = sp.scores.aggregate(total=Sum('points'))['total'] or 0
            
        # Calculate best_score
        if totals:
            if session.game.scoring_mode == Game.ScoringMode.LOWEST:
                best_score = min(totals.values())
            else:
                best_score = max(totals.values())
        else:
            best_score = None

        return render(request, 'scoring/partials/totals_row.html', {
            'session': session,
            'participants': participants,
            'totals': totals,
            'best_score': best_score,  
        })
