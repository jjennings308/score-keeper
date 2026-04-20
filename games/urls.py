from django.urls import path
from . import views

app_name = 'games'

urlpatterns = [
    path('', views.GameListView.as_view(), name='list'),
    path('new/', views.GameCreateView.as_view(), name='create'),
    path('<int:pk>/', views.GameDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.GameUpdateView.as_view(), name='update'),
]
