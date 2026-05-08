from django.contrib import admin
from .models import ClaimToken, GroupMembership, Player, PlayerGroup, Team


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'name', 'nickname', 'email', 'user', 'created_by', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'nickname', 'email')
    raw_id_fields = ('user', 'created_by')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PlayerGroup)
class PlayerGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'member_count', 'created_at')
    list_filter = ('owner',)
    search_fields = ('name', 'owner__username')
    raw_id_fields = ('owner',)
    readonly_fields = ('created_at', 'updated_at')

    def member_count(self, obj):
        return obj.memberships.count()
    member_count.short_description = 'Members'


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ('player', 'group', 'joined_at')
    list_filter = ('group',)
    search_fields = ('player__name', 'group__name')
    raw_id_fields = ('player', 'group')
    readonly_fields = ('joined_at',)


@admin.register(ClaimToken)
class ClaimTokenAdmin(admin.ModelAdmin):
    list_display = ('player', 'created_at', 'expires_at', 'used', 'is_valid')
    list_filter = ('used',)
    search_fields = ('player__name', 'player__email')
    raw_id_fields = ('player',)
    readonly_fields = ('token', 'created_at', 'expires_at', 'is_valid')

    def is_valid(self, obj):
        return obj.is_valid
    is_valid.boolean = True
    is_valid.short_description = 'Valid'


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'player_count', 'created_at')
    search_fields = ('name',)
    filter_horizontal = ('players',)

    def player_count(self, obj):
        return obj.players.count()
    player_count.short_description = 'Players'
