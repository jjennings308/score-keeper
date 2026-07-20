from django import forms
from .models import Player, Team


class TeamForm(forms.ModelForm):
    players = forms.ModelMultipleChoiceField(
        queryset=Player.objects.order_by('name'),
        required=False,
        widget=forms.SelectMultiple,
    )

    class Meta:
        model = Team
        fields = ['name', 'players']
