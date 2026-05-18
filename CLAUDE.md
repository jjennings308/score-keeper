# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Run dev server:**
```bash
python manage.py runserver
```

**Run migrations:**
```bash
python manage.py migrate
```

**Run tests:**
```bash
python manage.py test
python manage.py test scoring.tests  # single app
```

**Build Tailwind CSS** (required after editing any template):
```bash
npx tailwindcss -i ./static/css/input.css -o ./static/css/output.css --watch
# or one-shot:
npx tailwindcss -i ./static/css/input.css -o ./static/css/output.css
```

`static/css/output.css` is gitignored — it must be rebuilt locally. The source is `static/css/input.css`.

**Django shell:**
```bash
python manage.py shell_plus  # django-extensions provides this
```

**Environment:** Requires a `.env` file with at least `SECRET_KEY=<value>`. Settings are split across `config/settings/base.py`, `development.py`, and `production.py`. The dev server uses `development.py` (SQLite, django-extensions, DEBUG=True).

## Architecture

This is a **score-keeping web app** (Django 6 + HTMX + Tailwind CSS). Players join sessions, scores are entered round-by-round with live updates via HTMX, and winners are determined based on configurable game rules.

### Apps

**`games/`** — Game definitions. A `Game` record stores all the rules: scoring mode (cumulative/target/lowest), whether team play is allowed, round limits, winning score, whether negative scores or dealer rotation are used. Sessions reference a single Game to inherit these rules.

**`players/`** — People and rosters. A `Player` can optionally be linked to a Django `User` via a one-to-one. Unregistered players can be invited by email; they receive a `ClaimToken` (72-hour expiry) and claim their profile on first login. `PlayerGroup` acts as a roster — groups are owned by a user, and `GroupMembership` tracks which players belong. Teams (`Team`, `TeamMembership`) are also managed here.

**`scoring/`** — Sessions and score entry. A `Session` ties a `Game`, a `PlayerGroup`, and a set of `SessionPlayer` records (each pointing to either a `Player` or a `Team`, not both). Scoring happens per `Round`; each `Round` has `Score` entries (one per `SessionPlayer`). Key behaviours:
- Rounds can be locked to prevent edits.
- Token-based unauthenticated access lets a non-logged-in scorekeeper enter scores via a time-limited URL.
- HTMX endpoints (`/sessions/<id>/score/`, `/sessions/<id>/totals/`, `/round/<id>/complete/`, etc.) handle live score updates without full page reloads.

**`stats/`** — Statistics. Views for per-game and per-player stats exist; `models.py` is currently empty (stats are computed from `scoring` data).

### URL structure

| Prefix | App |
|--------|-----|
| `/` | Redirects to `/sessions/` |
| `/games/` | games |
| `/players/` | players |
| `/sessions/` | scoring |
| `/stats/` | stats |
| `/accounts/` | Django auth (login/logout/password change) |
| `/admin/` | Django admin |

### Templates & frontend

All templates live in `templates/` (top-level) and per-app `<app>/templates/<app>/` folders. `templates/base.html` pulls in the compiled Tailwind CSS and HTMX from CDN. The navbar is `templates/partials/navbar.html`.

HTMX drives interactive score entry — Django views return HTML fragments rather than JSON for HTMX requests. Check the `HX-Request` header or use `django-htmx` helpers to distinguish HTMX from full-page requests.

### Key model constraints

- A `SessionPlayer` has either a `player` FK or a `team` FK, never both — enforced in `clean()`.
- `Score` has a unique constraint on `(round, session_player)`.
- `GroupMembership` has a unique constraint on `(group, player)`.
