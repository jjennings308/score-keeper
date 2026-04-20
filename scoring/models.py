from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum

from games.models import Game
from players.models import Player, Team


class Session(models.Model):
    game = models.ForeignKey(
        Game,
        on_delete=models.PROTECT,
        related_name='sessions'
    )
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    is_complete = models.BooleanField(default=False)
    winner = models.CharField(
        max_length=200,
        blank=True,
        help_text="Name of winning player or team, set on completion"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sessions'
    )

    def __str__(self):
        return f"{self.game.name} — {self.started_at.strftime('%Y-%m-%d %H:%M')}"

    def get_totals(self):
        """Return a dict of {SessionPlayer: running_total} for all participants."""
        totals = {}
        for sp in self.participants.all():
            total = sp.scores.aggregate(total=Sum('points'))['total'] or 0
            totals[sp] = total
        return totals

    def check_winner(self):
        """Check if a winning condition has been met. Returns winning SessionPlayer or None."""
        game = self.game
        if not game.winning_score:
            return None
        totals = self.get_totals()
        if game.scoring_mode == Game.ScoringMode.TARGET:
            winners = [sp for sp, total in totals.items() if total >= game.winning_score]
            return winners[0] if winners else None
        elif game.scoring_mode == Game.ScoringMode.LOWEST:
            if totals:
                return min(totals, key=totals.get)
        return None

    class Meta:
        ordering = ['-started_at']


class SessionPlayer(models.Model):
    """
    Represents a participant in a session — either an individual player or a team.
    Exactly one of `player` or `team` should be set, depending on the game's play_mode.
    """
    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name='participants'
    )
    player = models.ForeignKey(
        Player,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='session_entries'
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='session_entries'
    )
    display_order = models.PositiveIntegerField(
        default=0,
        help_text="Column order in the score table"
    )

    def __str__(self):
        if self.player:
            return f"{self.player.name} in {self.session}"
        if self.team:
            return f"{self.team.name} in {self.session}"
        return f"Participant in {self.session}"

    @property
    def display_name(self):
        if self.player:
            return self.player.nickname if self.player.nickname else self.player.name
        if self.team:
            return self.team.name
        return "Unknown"

    @property
    def running_total(self):
        return self.scores.aggregate(total=Sum('points'))['total'] or 0

    class Meta:
        ordering = ['display_order']
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(player__isnull=False, team__isnull=True) |
                    models.Q(player__isnull=True, team__isnull=False)
                ),
                name='session_player_xor_team',
            )
        ]


class Round(models.Model):
    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name='rounds'
    )
    round_number = models.PositiveIntegerField()
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Round {self.round_number} of {self.session}"

    class Meta:
        ordering = ['round_number']
        unique_together = ['session', 'round_number']


class Score(models.Model):
    round = models.ForeignKey(
        Round,
        on_delete=models.CASCADE,
        related_name='scores'
    )
    session_player = models.ForeignKey(
        SessionPlayer,
        on_delete=models.CASCADE,
        related_name='scores'
    )
    points = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.session_player.display_name}: {self.points} pts (Round {self.round.round_number})"

    class Meta:
        unique_together = ['round', 'session_player']
