import secrets
from datetime import timedelta

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Player(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='player_profile',
        help_text="Linked user account — set when player claims their profile"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_players',
        help_text="User who added this player record"
    )
    name = models.CharField(max_length=100)
    nickname = models.CharField(max_length=50, blank=True)
    email = models.EmailField(
        null=True,
        blank=True,
        unique=True,
        help_text="Used to find existing players and send invite links"
    )
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        return self.nickname if self.nickname else self.name

    @property
    def can_be_edited_by(self):
        """Returns the user who has edit rights over this player record."""
        if self.user:
            return self.user
        return self.created_by

    def is_editable_by(self, user):
        if self.user:
            return self.user == user
        return self.created_by == user

    class Meta:
        ordering = ['name']


class Team(models.Model):
    """
    In-game team construct (e.g. red team vs blue team within a session).
    Distinct from PlayerGroup which is a social roster.
    """
    name = models.CharField(max_length=100)
    players = models.ManyToManyField(Player, related_name='teams', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class PlayerGroup(models.Model):
    """
    A named roster of players owned by a registered user.
    Examples: 'Immediate family', 'Extended family', 'Poker night'.
    Any registered user can create and manage their own groups.
    A player can belong to many groups across different owners.
    """
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='player_groups',
        help_text="The registered user who owns and manages this group"
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.owner.username})"

    def is_editable_by(self, user):
        return self.owner == user

    class Meta:
        ordering = ['name']
        unique_together = ['owner', 'name']


class GroupMembership(models.Model):
    """
    Join table linking players to groups.
    A player can belong to many groups; a group has many players.
    """
    group = models.ForeignKey(
        PlayerGroup,
        on_delete=models.CASCADE,
        related_name='memberships'
    )
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='group_memberships'
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.player.display_name} in {self.group.name}"

    class Meta:
        ordering = ['joined_at']
        unique_together = ['group', 'player']


class ClaimToken(models.Model):
    """
    A short-lived token emailed to a player so they can register
    and link their User account to their existing Player record.
    """
    TOKEN_EXPIRY_HOURS = 72

    player = models.OneToOneField(
        Player,
        on_delete=models.CASCADE,
        related_name='claim_token'
    )
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(48)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=self.TOKEN_EXPIRY_HOURS)
        super().save(*args, **kwargs)

    @property
    def is_valid(self):
        return not self.used and timezone.now() < self.expires_at

    def mark_used(self):
        self.used = True
        self.save(update_fields=['used'])

    def __str__(self):
        return f"Claim token for {self.player.display_name}"

    class Meta:
        ordering = ['-created_at']
