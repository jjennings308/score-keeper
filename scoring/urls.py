from django.urls import path
from . import views

app_name = 'scoring'

urlpatterns = [
    # Session list / home
    path('', views.SessionListView.as_view(), name='list'),

    # New session wizard
    path('new/', views.SessionCreateView.as_view(), name='create'),
    path('new/<int:game_id>/players/', views.SessionPlayersView.as_view(), name='create_players'),

    # Active session
    path('<int:pk>/', views.SessionDetailView.as_view(), name='detail'),
    path('<int:pk>/complete/', views.CompleteSessionView.as_view(), name='complete'),

    # HTMX score save — returns updated totals row only
    path('<int:session_pk>/score/', views.SaveScoreView.as_view(), name='save_score'),
    path('<int:session_pk>/totals/', views.TotalsRowView.as_view(), name='totals'),

    # Round management — all return updated score table
    path('round/<int:round_pk>/complete/', views.CompleteRoundView.as_view(), name='complete_round'),
    path('round/<int:round_pk>/edit/', views.EditRoundView.as_view(), name='edit_round'),
    path('round/<int:round_pk>/save-edits/', views.SaveRoundEditsView.as_view(), name='save_round_edits'),
    path('round/<int:round_pk>/cancel-edit/', views.CancelRoundEditView.as_view(), name='cancel_round_edit'),
]
