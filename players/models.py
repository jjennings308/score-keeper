from django.db import models
from django.contrib.auth.models import User


class Player(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Optional link to a Django auth user account"
    )
    name = models.CharField(max_length=100)
    nickname = models.CharField(max_length=50, blank=True, help_text="Optional alias or nickname")
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        
    @property
    def display_name(self):
        return self.nickname if self.nickname else self.name


class Team(models.Model):
    name = models.CharField(max_length=100)
    players = models.ManyToManyField(Player, related_name='teams', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
