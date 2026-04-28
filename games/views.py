from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages

from .models import Game


class GameListView(ListView):
    model = Game
    template_name = 'games/game_list.html'
    context_object_name = 'games'
    ordering = ['name']


class GameDetailView(DetailView):
    model = Game
    template_name = 'games/game_detail.html'
    context_object_name = 'game'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['recent_sessions'] = self.object.sessions.order_by('-started_at')[:5]
        return ctx


class GameCreateView(LoginRequiredMixin, CreateView):
    model = Game
    template_name = 'games/game_form.html'
    fields = [
        'name', 'description', 'play_mode', 'scoring_mode', 'team_scoring',
        'winning_score', 'num_rounds', 'allow_negative', 'requires_delaer'
    ]
    success_url = reverse_lazy('games:list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, f'Game "{form.instance.name}" created successfully.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Add Game'
        ctx['button_label'] = 'Add Game'
        return ctx


class GameUpdateView(LoginRequiredMixin, UpdateView):
    model = Game
    template_name = 'games/game_form.html'
    fields = [
        'name', 'description', 'play_mode', 'scoring_mode', 'team_scoring',
        'winning_score', 'num_rounds', 'allow_negative', 'requires_dealer'
    ]
    success_url = reverse_lazy('games:list')

    def form_valid(self, form):
        messages.success(self.request, f'Game "{form.instance.name}" updated successfully.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = f'Edit {self.object.name}'
        ctx['button_label'] = 'Save Changes'
        return ctx
