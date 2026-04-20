from django.contrib import admin

from .models import Player, Team


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ['name', 'nickname', 'user', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name', 'nickname', 'user__username', 'user__email']
    readonly_fields = ['created_at']
    raw_id_fields = ['user']


class PlayerInline(admin.TabularInline):
    model = Team.players.through
    extra = 1
    verbose_name = 'Player'
    verbose_name_plural = 'Players'


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ['name', 'player_count', 'created_at']
    search_fields = ['name']
    readonly_fields = ['created_at']
    inlines = [PlayerInline]
    exclude = ['players']

    def player_count(self, obj):
        return obj.players.count()
    player_count.short_description = 'Players'
