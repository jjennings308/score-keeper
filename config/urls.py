from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/sessions/', permanent=False), name='home'),
    path('games/', include('games.urls', namespace='games')),
    path('players/', include('players.urls', namespace='players')),
    path('sessions/', include('scoring.urls', namespace='scoring')),
    path('stats/', include('stats.urls', namespace='stats')),
    path('accounts/login/',  auth_views.LoginView.as_view(),  name='account_login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='account_logout'),
    path('accounts/password-change/', auth_views.PasswordChangeView.as_view(
        success_url='/accounts/password-change/done/'
    ), name='account_password_change'),
    path('accounts/password-change/done/', auth_views.PasswordChangeDoneView.as_view(),
        name='account_password_change_done'),
]