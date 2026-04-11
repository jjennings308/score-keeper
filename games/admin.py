from django.contrib import admin

from scoring.models import Session, SessionPlayer, Round, Score


class SessionPlayerInline(admin.TabularInline):
    model = SessionPlayer
    extra = 1
    fields = ['player', 'team', 'display_order']
    raw_id_fields = ['player', 'team']


class RoundInline(admin.TabularInline):
    model = Round
    extra = 0
    fields = ['round_number', 'completed_at']
    readonly_fields = ['completed_at']
    show_change_link = True


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'game',
        'participant_count',
        'round_count',
        'is_complete',
        'winner',
        'started_at',
    ]
    list_filter = ['is_complete', 'game']
    search_fields = ['game__name', 'winner']
    readonly_fields = ['started_at', 'created_by']
    inlines = [SessionPlayerInline, RoundInline]
    fieldsets = (
        (None, {
            'fields': ('game', 'is_complete', 'winner')
        }),
        ('Timestamps', {
            'fields': ('started_at', 'ended_at', 'created_by'),
            'classes': ('collapse',),
        }),
    )

    def participant_count(self, obj):
        return obj.participants.count()
    participant_count.short_description = 'Participants'

    def round_count(self, obj):
        return obj.rounds.count()
    round_count.short_description = 'Rounds'

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class ScoreInline(admin.TabularInline):
    model = Score
    extra = 0
    fields = ['session_player', 'points']
    raw_id_fields = ['session_player']


@admin.register(Round)
class RoundAdmin(admin.ModelAdmin):
    list_display = ['session', 'round_number', 'completed_at']
    list_filter = ['session__game']
    search_fields = ['session__game__name']
    readonly_fields = ['completed_at']
    inlines = [ScoreInline]


@admin.register(SessionPlayer)
class SessionPlayerAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'session', 'running_total', 'display_order']
    list_filter = ['session__game']
    search_fields = ['player__name', 'team__name']
    raw_id_fields = ['player', 'team', 'session']

    def display_name(self, obj):
        return obj.display_name
    display_name.short_description = 'Participant'

    def running_total(self, obj):
        return obj.running_total
    running_total.short_description = 'Total Score'


@admin.register(Score)
class ScoreAdmin(admin.ModelAdmin):
    list_display = ['session_player', 'round', 'points']
    list_filter = ['round__session__game']
    search_fields = ['session_player__player__name', 'session_player__team__name']
    raw_id_fields = ['round', 'session_player']
