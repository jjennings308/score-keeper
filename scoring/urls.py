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
    path('<int:pk>/round/add/', views.AddRoundView.as_view(), name='add_round'),
    path('<int:pk>/complete/', views.CompleteSessionView.as_view(), name='complete'),

    # HTMX endpoints
    path('<int:session_pk>/score/', views.SaveScoreView.as_view(), name='save_score'),
    path('<int:session_pk>/totals/', views.TotalsRowView.as_view(), name='totals'),
]
