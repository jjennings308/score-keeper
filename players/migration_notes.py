"""
Migration: players app changes
Run with: python manage.py makemigrations players
          python manage.py migrate

What this migration covers:
  - Player: add email, add created_by FK
  - PlayerGroup: new model
  - GroupMembership: new model
  - ClaimToken: new model

The existing Team model and its M2M to Player are unchanged.
"""

# This is a reference migration — run makemigrations to generate the real one.
# Listed here so you know the exact fields being added/created.

# Player changes:
#   email = models.EmailField(null=True, blank=True, unique=True)
#   created_by = models.ForeignKey(User, on_delete=SET_NULL, null=True, blank=True,
#                                  related_name='created_players')

# New models: PlayerGroup, GroupMembership, ClaimToken
# (see players_models.py for full definitions)

# After placing the new models.py, run:
#   python manage.py makemigrations players
#   python manage.py migrate

# On production:
#   cd /var/www/score
#   source .venv/bin/activate
#   DJANGO_SETTINGS_MODULE=config.settings.production python manage.py makemigrations players
#   DJANGO_SETTINGS_MODULE=config.settings.production python manage.py migrate
