from django.urls import path
from . import views

app_name = 'players'

urlpatterns = [
    # Player list + detail
    path('', views.player_list, name='list'),
    path('<int:pk>/', views.player_detail, name='detail'),
    path('<int:pk>/edit/', views.player_update, name='update'),

    # Player creation flow
    path('create/', views.player_create, name='create'),
    path('<int:pk>/confirm-match/', views.player_confirm_match, name='confirm_match'),

    # Invite / claim flow
    path('<int:pk>/invite/', views.player_send_invite, name='send_invite'),
    path('claim/<str:token>/', views.player_claim, name='claim'),

    # Group management
    path('groups/', views.group_list, name='group_list'),
    path('groups/create/', views.group_create, name='group_create'),
    path('groups/<int:pk>/', views.group_detail, name='group_detail'),
    path('groups/<int:pk>/edit/', views.group_update, name='group_update'),
    path('groups/<int:pk>/delete/', views.group_delete, name='group_delete'),
    path(
        'groups/<int:group_pk>/players/<int:player_pk>/remove/',
        views.group_remove_player,
        name='group_remove_player',
    ),
]
