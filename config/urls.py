from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/sessions/', permanent=False), name='home'),
    path('games/', include('games.urls', namespace='games')),
    path('players/', include('players.urls', namespace='players')),
    path('sessions/', include('scoring.urls', namespace='scoring')),
    path('stats/', include('stats.urls', namespace='stats')),
]
