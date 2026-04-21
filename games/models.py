from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse


class Game(models.Model):

    class PlayMode(models.TextChoices):
        INDIVIDUAL = 'individual', 'Individual'
        TEAM = 'team', 'Team'

    class ScoringMode(models.TextChoices):
        CUMULATIVE = 'cumulative', 'Cumulative (highest wins)'
        TARGET = 'target', 'Target Score (first to reach wins)'
        LOWEST = 'lowest_wins', 'Lowest Score Wins'

    class TeamScoring(models.TextChoices):
        TEAM = 'team', 'One score per team per round'
        INDIVIDUAL = 'individual', 'Each player scores, team totals sum'

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
    team_scoring = models.CharField(
        max_length=20,
        choices=TeamScoring.choices,
        default=TeamScoring.TEAM,
        help_text="Only applies when Play Mode is Team"
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

    def get_absolute_url(self):
        return reverse('games:detail', kwargs={'pk': self.pk})

    class Meta:
        ordering = ['name']
