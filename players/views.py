from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages

from .models import Player, Team


class PlayerListView(ListView):
    model = Player
    template_name = 'players/player_list.html'
    context_object_name = 'players'
    ordering = ['name']


class PlayerDetailView(DetailView):
    model = Player
    template_name = 'players/player_detail.html'
    context_object_name = 'player'


class PlayerCreateView(LoginRequiredMixin, CreateView):
    model = Player
    template_name = 'players/player_form.html'
    fields = ['name', 'nickname']
    success_url = reverse_lazy('players:list')

    def form_valid(self, form):
        messages.success(self.request, f'Player "{form.instance.name}" created successfully.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Add Player'
        ctx['button_label'] = 'Add Player'
        return ctx


class PlayerUpdateView(LoginRequiredMixin, UpdateView):
    model = Player
    template_name = 'players/player_form.html'
    fields = ['name', 'nickname']
    success_url = reverse_lazy('players:list')

    def form_valid(self, form):
        messages.success(self.request, f'Player "{form.instance.name}" updated successfully.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = f'Edit {self.object.name}'
        ctx['button_label'] = 'Save Changes'
        return ctx


class TeamListView(ListView):
    model = Team
    template_name = 'players/team_list.html'
    context_object_name = 'teams'
    ordering = ['name']


class TeamCreateView(LoginRequiredMixin, CreateView):
    model = Team
    template_name = 'players/team_form.html'
    fields = ['name', 'players']
    success_url = reverse_lazy('players:team_list')

    def form_valid(self, form):
        messages.success(self.request, f'Team "{form.instance.name}" created successfully.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Create Team'
        ctx['button_label'] = 'Create Team'
        return ctx


class TeamUpdateView(LoginRequiredMixin, UpdateView):
    model = Team
    template_name = 'players/team_form.html'
    fields = ['name', 'players']
    success_url = reverse_lazy('players:team_list')

    def form_valid(self, form):
        messages.success(self.request, f'Team "{form.instance.name}" updated successfully.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = f'Edit {self.object.name}'
        ctx['button_label'] = 'Save Changes'
        return ctx
