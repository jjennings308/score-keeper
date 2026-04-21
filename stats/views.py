from django.views.generic import View, ListView
from django.shortcuts import get_object_or_404, render
from django.db.models import Sum, Count, Avg, Max, Min, Q
from django.utils import timezone
from datetime import timedelta

from games.models import Game
from players.models import Player
from scoring.models import Session, SessionPlayer, Score

def player_won(session, session_player):
    if not session.winner:
        return False
    player = session_player.player
    if player:
        print(f"Comparing winner='{session.winner}' vs nickname='{player.nickname}' vs name='{player.name}'")
        return (
            session.winner == player.nickname or
            session.winner == player.name
        )
    if session_player.team:
        return session.winner == session_player.team.name
    return False

def get_date_filter(request):
    """Parse date range from request GET params. Returns a Q filter or None."""
    days = request.GET.get('days')
    if days:
        try:
            days = int(days)
            cutoff = timezone.now() - timedelta(days=days)
            return cutoff
        except ValueError:
            pass
    return None


class GameStatsView(View):
    template_name = 'stats/game_stats.html'

    def get(self, request):
        cutoff = get_date_filter(request)
        days = request.GET.get('days', '')

        games = Game.objects.all().order_by('name')
        game_stats = []

        for game in games:
            sessions = game.sessions.filter(is_complete=True)
            if cutoff:
                sessions = sessions.filter(started_at__gte=cutoff)

            total_sessions = sessions.count()
            if total_sessions == 0:
                continue

            # Win counts per participant name
            win_counts = {}
            for session in sessions:
                if session.winner:
                    win_counts[session.winner] = win_counts.get(session.winner, 0) + 1

            top_winner = max(win_counts, key=win_counts.get) if win_counts else None
            top_winner_wins = win_counts[top_winner] if top_winner else 0

            # Score stats across all scores in this game's sessions
            session_ids = sessions.values_list('id', flat=True)
            scores = Score.objects.filter(round__session_id__in=session_ids)
            score_agg = scores.aggregate(
                avg=Avg('points'),
                high=Max('points'),
                low=Min('points'),
            )

            game_stats.append({
                'game': game,
                'total_sessions': total_sessions,
                'top_winner': top_winner,
                'top_winner_wins': top_winner_wins,
                'avg_score': round(score_agg['avg'], 1) if score_agg['avg'] else None,
                'high_score': score_agg['high'],
                'low_score': score_agg['low'],
            })

        return render(request, self.template_name, {
            'game_stats': game_stats,
            'days': days,
        })


class GameStatsDetailView(View):
    template_name = 'stats/game_stats_detail.html'

    def get(self, request, pk):
        game = get_object_or_404(Game, pk=pk)
        cutoff = get_date_filter(request)
        days = request.GET.get('days', '')

        sessions = game.sessions.filter(is_complete=True).order_by('-started_at')
        if cutoff:
            sessions = sessions.filter(started_at__gte=cutoff)

        total_sessions = sessions.count()

        # Win counts
        win_counts = {}
        for session in sessions:
            if session.winner:
                win_counts[session.winner] = win_counts.get(session.winner, 0) + 1
        winners_ranked = sorted(win_counts.items(), key=lambda x: x[1], reverse=True)

        # Score stats
        session_ids = sessions.values_list('id', flat=True)
        scores = Score.objects.filter(round__session_id__in=session_ids)
        score_agg = scores.aggregate(
            avg=Avg('points'),
            high=Max('points'),
            low=Min('points'),
        )

        # Session history
        session_history = []
        for session in sessions[:20]:
            participants = session.participants.select_related('player', 'team').order_by('display_order')
            totals = {
                sp.display_name: sp.scores.aggregate(t=Sum('points'))['t'] or 0
                for sp in participants
            }
            session_history.append({
                'session': session,
                'totals': totals,
            })

        return render(request, self.template_name, {
            'game': game,
            'total_sessions': total_sessions,
            'winners_ranked': winners_ranked,
            'score_agg': score_agg,
            'session_history': session_history,
            'days': days,
        })


class PlayerStatsView(View):
    template_name = 'stats/player_stats.html'

    def get(self, request):
        cutoff = get_date_filter(request)
        days = request.GET.get('days', '')

        players = Player.objects.all().order_by('name')
        player_stats = []

        for player in players:
            entries = SessionPlayer.objects.filter(
            player=player,
            session__is_complete=True,
        ).select_related('session__game', 'player', 'team')

            if cutoff:
                entries = entries.filter(session__started_at__gte=cutoff)
            entries = list(entries)
            total_sessions = len(entries)

            if total_sessions == 0:
                continue

            wins = sum(
                1 for e in entries
                if  player_won(e.session, e)
            )
            win_pct = round((wins / total_sessions) * 100, 1) if total_sessions else 0

            # Average total score per session
            session_totals = [
                e.scores.aggregate(t=Sum('points'))['t'] or 0
                for e in entries
            ]
            avg_total = round(sum(session_totals) / len(session_totals), 1) if session_totals else 0
            best_total = max(session_totals) if session_totals else None
            worst_total = min(session_totals) if session_totals else None

            # Favourite game
            game_counts = {}
            for e in entries:
                gname = e.session.game.name
                game_counts[gname] = game_counts.get(gname, 0) + 1
            favourite_game = max(game_counts, key=game_counts.get) if game_counts else None

            player_stats.append({
                'player': player,
                'total_sessions': total_sessions,
                'wins': wins,
                'win_pct': win_pct,
                'avg_total': avg_total,
                'best_total': best_total,
                'worst_total': worst_total,
                'favourite_game': favourite_game,
            })

        # Sort by win percentage descending
        player_stats.sort(key=lambda x: x['win_pct'], reverse=True)

        return render(request, self.template_name, {
            'player_stats': player_stats,
            'days': days,
        })


class PlayerStatsDetailView(View):
    template_name = 'stats/player_stats_detail.html'

    def get(self, request, pk):
        player = get_object_or_404(Player, pk=pk)
        cutoff = get_date_filter(request)
        days = request.GET.get('days', '')

        entries = SessionPlayer.objects.filter(
            player=player,
            session__is_complete=True,
        ).select_related('session__game', 'player', 'team').order_by('-session__started_at')
        
        if cutoff:
            entries = entries.filter(session__started_at__gte=cutoff)
        entries = list(entries)
        
        total_sessions = len(entries)

        wins = sum(1 for e in entries if player_won(e.session, e))
        win_pct = round((wins / total_sessions) * 100, 1) if total_sessions else 0

        # Per game breakdown
        game_breakdown = {}
        for e in entries:
            gname = e.session.game.name
            total = e.scores.aggregate(t=Sum('points'))['t'] or 0
            won = player_won(e.session, e)
            if gname not in game_breakdown:
                game_breakdown[gname] = {'sessions': 0, 'wins': 0, 'totals': []}
            game_breakdown[gname]['sessions'] += 1
            game_breakdown[gname]['wins'] += 1 if won else 0
            game_breakdown[gname]['totals'].append(total)

        game_breakdown_list = []
        for gname, data in game_breakdown.items():
            avg = round(sum(data['totals']) / len(data['totals']), 1) if data['totals'] else 0
            win_p = round((data['wins'] / data['sessions']) * 100, 1) if data['sessions'] else 0
            game_breakdown_list.append({
                'game': gname,
                'sessions': data['sessions'],
                'wins': data['wins'],
                'win_pct': win_p,
                'avg_score': avg,
                'best': max(data['totals']) if data['totals'] else None,
            })
        game_breakdown_list.sort(key=lambda x: x['sessions'], reverse=True)

        # Recent sessions
        recent = []
        for e in entries[:15]:
            total = e.scores.aggregate(t=Sum('points'))['t'] or 0
            recent.append({
                'session': e.session,
                'total': total,
                'won': player_won(e.session, e),
            })

        return render(request, self.template_name, {
            'player': player,
            'total_sessions': total_sessions,
            'wins': wins,
            'win_pct': win_pct,
            'game_breakdown': game_breakdown_list,
            'recent': recent,
            'days': days,
        })
