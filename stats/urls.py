from django.urls import path
from . import views

app_name = 'stats'

urlpatterns = [
    path('games/', views.GameStatsView.as_view(), name='games'),
    path('games/<int:pk>/', views.GameStatsDetailView.as_view(), name='game_detail'),
    path('players/', views.PlayerStatsView.as_view(), name='players'),
    path('players/<int:pk>/', views.PlayerStatsDetailView.as_view(), name='player_detail'),
]
