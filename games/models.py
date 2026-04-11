from django.db import models
from django.contrib.auth.models import User


class Game(models.Model):

    class PlayMode(models.TextChoices):
        INDIVIDUAL = 'individual', 'Individual'
        TEAM = 'team', 'Team'

    class ScoringMode(models.TextChoices):
        CUMULATIVE = 'cumulative', 'Cumulative (highest wins)'
        TARGET = 'target', 'Target Score (first to reach wins)'
        LOWEST = 'lowest_wins', 'Lowest Score Wins'

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    play_mode = models.CharField(
        max_length=20,
        choices=PlayMode.choices,
        default=PlayMode.INDIVIDUAL
    )
    scoring_mode = models.CharField(
        max_length=20,
        choices=ScoringMode.choices,
        default=ScoringMode.CUMULATIVE
    )
    winning_score = models.IntegerField(
        null=True,
        blank=True,
        help_text="Leave blank for open-ended games with no score limit"
    )
    num_rounds = models.IntegerField(
        null=True,
        blank=True,
        help_text="Leave blank for open-ended games with no round limit"
    )
    allow_negative = models.BooleanField(
        default=False,
        help_text="Whether negative scores are allowed (e.g. penalty points)"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_games'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
