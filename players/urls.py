from django.urls import path
from . import views

app_name = 'players'

urlpatterns = [
    path('', views.PlayerListView.as_view(), name='list'),
    path('new/', views.PlayerCreateView.as_view(), name='create'),
    path('<int:pk>/', views.PlayerDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.PlayerUpdateView.as_view(), name='update'),
    path('teams/', views.TeamListView.as_view(), name='team_list'),
    path('teams/new/', views.TeamCreateView.as_view(), name='team_create'),
    path('teams/<int:pk>/edit/', views.TeamUpdateView.as_view(), name='team_update'),
]
