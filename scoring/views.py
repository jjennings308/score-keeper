from django.views.generic import ListView, DetailView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum
from django.template.loader import render_to_string

from games.models import Game
from players.models import Player, Team
from .models import Session, SessionPlayer, Round, Score


def get_next_dealer(session, current_round_number):
    participants = list(session.participants.order_by('display_order'))
    if not participants:
        return None
    index = (current_round_number - 1) % len(participants)
    return participants[index]


def build_score_context(session):
    participants = list(session.participants.select_related('player', 'team').order_by('display_order'))
    rounds = list(session.rounds.select_related('dealer__player', 'dealer__team').order_by('round_number'))

    all_scores = Score.objects.filter(
        round__session=session
    ).select_related('round', 'session_player')

    score_grid = {}
    for r in rounds:
        score_grid[r] = {}
    for score in all_scores:
        score_grid[score.round][score.session_player_id] = score

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

    active_round = None
    for r in rounds:
        if not r.is_locked:
            active_round = r
            break

    active_round_complete = False
    if active_round and not session.is_complete:
        scores_entered = len(score_grid.get(active_round, {}))
        active_round_complete = scores_entered >= len(participants)

    return {
        'session': session,
        'participants': participants,
        'rounds': rounds,
        'score_grid': score_grid,
        'totals': totals,
        'best_score': best_score,
        'active_round': active_round,
        'active_round_complete': active_round_complete,
        'editing_round': None,
    }


def build_totals_context(session):
    participants = list(session.participants.select_related('player', 'team').order_by('display_order'))
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

    return {
        'session': session,
        'participants': participants,
        'totals': totals,
        'best_score': best_score,
    }


def end_session(session):
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


class SessionListView(ListView):
    model = Session
    template_name = 'scoring/session_list.html'
    context_object_name = 'sessions'
    ordering = ['-started_at']

    def get_queryset(self):
        return Session.objects.select_related('game').prefetch_related('participants').all()


class SessionCreateView(LoginRequiredMixin, View):
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
                SessionPlayer.objects.create(session=session, team=team, display_order=order)
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
                SessionPlayer.objects.create(session=session, player=player, display_order=order)

        first_dealer = get_next_dealer(session, 1) if game.requires_dealer else None
        Round.objects.create(session=session, round_number=1, dealer=first_dealer)

        messages.success(request, 'Session started! Good luck everyone.')
        return redirect('scoring:detail', pk=session.pk)


class SessionDetailView(DetailView):
    model = Session
    template_name = 'scoring/session_detail.html'
    context_object_name = 'session'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(build_score_context(self.object))
        return ctx


class SaveScoreView(LoginRequiredMixin, View):
    """
    Save a single score. Returns JSON with:
    - round_pk: which round was scored
    - all_scored: whether all players now have scores in this round
    - totals_html: rendered totals row HTML
    """

    def post(self, request, session_pk):
        session = get_object_or_404(Session, pk=session_pk)
        round_id = request.POST.get('round_id')
        session_player_id = request.POST.get('session_player_id')
        points_raw = request.POST.get('points', '').strip()

        try:
            round_obj = Round.objects.get(pk=round_id, session=session)
        except Round.DoesNotExist:
            return JsonResponse({'error': 'Round not found'}, status=404)

        if round_obj.is_locked:
            return JsonResponse({'error': 'Round is locked'}, status=403)

        if not points_raw:
            Score.objects.filter(
                round_id=round_id,
                session_player_id=session_player_id
            ).delete()
        else:
            try:
                points = int(points_raw)
            except ValueError:
                return JsonResponse({'error': 'Invalid score'}, status=400)

            if not session.game.allow_negative and points < 0:
                return JsonResponse({'error': 'Negative scores not allowed'}, status=400)

            Score.objects.update_or_create(
                round_id=round_id,
                session_player_id=session_player_id,
                defaults={'points': points},
            )

        # Check if all participants have scored this round
        participant_count = session.participants.count()
        scores_count = Score.objects.filter(
            round=round_obj
        ).values('session_player').distinct().count()
        all_scored = scores_count >= participant_count

        # Render updated totals row
        totals_ctx = build_totals_context(session)
        totals_html = render_to_string(
            'scoring/partials/totals_row.html',
            totals_ctx,
            request=request,
        )

        return JsonResponse({
            'round_pk': round_obj.pk,
            'all_scored': all_scored,
            'totals_html': totals_html,
        })


class CompleteRoundView(LoginRequiredMixin, View):
    """Lock the current round, handle end-game, create next round."""

    def post(self, request, round_pk):
        round_obj = get_object_or_404(Round, pk=round_pk)
        session = round_obj.session

        if round_obj.is_locked:
            return HttpResponse('Round already locked.', status=400)

        participant_count = session.participants.count()
        scores_count = Score.objects.filter(
            round=round_obj
        ).values('session_player').distinct().count()
        if scores_count < participant_count:
            return HttpResponse('Not all players have scores.', status=400)

        round_obj.is_locked = True
        round_obj.completed_at = timezone.now()
        round_obj.save()

        # Target score check
        if session.game.winning_score:
            winner = session.check_winner()
            if winner:
                session.winner = winner.display_name
                session.is_complete = True
                session.ended_at = timezone.now()
                session.save()

        # Final round check
        if not session.is_complete:
            is_final_round = (
                session.game.num_rounds is not None and
                round_obj.round_number >= session.game.num_rounds
            )
            if is_final_round:
                end_session(session)
            else:
                next_number = round_obj.round_number + 1
                if not Round.objects.filter(session=session, round_number=next_number).exists():
                    next_dealer = get_next_dealer(session, next_number) if session.game.requires_dealer else None
                    Round.objects.create(session=session, round_number=next_number, dealer=next_dealer)

        ctx = build_score_context(session)
        response = render(request, 'scoring/partials/score_table.html', ctx)
        if session.is_complete:
            response['X-Session-Complete'] = 'true'
        return response

class EditRoundView(LoginRequiredMixin, View):
    """Unlock a locked round for editing."""

    def post(self, request, round_pk):
        round_obj = get_object_or_404(Round, pk=round_pk)
        session = round_obj.session

        round_obj.is_locked = False
        round_obj.save()

        ctx = build_score_context(session)
        ctx['editing_round'] = round_obj
        return render(request, 'scoring/partials/score_table.html', ctx)


class SaveRoundEditsView(LoginRequiredMixin, View):
    """Save edited scores for a round and re-lock it."""

    def post(self, request, round_pk):
        round_obj = get_object_or_404(Round, pk=round_pk)
        session = round_obj.session

        participants = list(session.participants.order_by('display_order'))
        for sp in participants:
            key = f'points_{sp.pk}'
            points_raw = request.POST.get(key, '').strip()
            if points_raw:
                try:
                    points = int(points_raw)
                    Score.objects.update_or_create(
                        round=round_obj,
                        session_player=sp,
                        defaults={'points': points},
                    )
                except ValueError:
                    pass
            else:
                Score.objects.filter(round=round_obj, session_player=sp).delete()

        round_obj.is_locked = True
        round_obj.completed_at = timezone.now()
        round_obj.save()

        return render(request, 'scoring/partials/score_table.html', build_score_context(session))


class CancelRoundEditView(LoginRequiredMixin, View):
    """Cancel editing — re-lock without saving."""

    def post(self, request, round_pk):
        round_obj = get_object_or_404(Round, pk=round_pk)
        session = round_obj.session

        round_obj.is_locked = True
        round_obj.save()

        return render(request, 'scoring/partials/score_table.html', build_score_context(session))


class CompleteSessionView(LoginRequiredMixin, View):
    def post(self, request, pk):
        session = get_object_or_404(Session, pk=pk)
        end_session(session)
        messages.success(request, f'Session complete! Winner: {session.winner}')
        return redirect('scoring:detail', pk=session.pk)


class TotalsRowView(View):
    def get(self, request, session_pk):
        session = get_object_or_404(Session, pk=session_pk)
        ctx = build_totals_context(session)
        return render(request, 'scoring/partials/totals_row.html', ctx)
