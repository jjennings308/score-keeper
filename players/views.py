from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.conf import settings

from .forms import TeamForm
from .models import ClaimToken, GroupMembership, Player, PlayerGroup, Team


# ---------------------------------------------------------------------------
# Player list + detail
# ---------------------------------------------------------------------------

@login_required
def player_list(request):
    players = Player.objects.select_related('user').prefetch_related(
        'group_memberships__group'
    ).order_by('name')
    return render(request, 'players/player_list.html', {'players': players})


def player_detail(request, pk):
    player = get_object_or_404(Player, pk=pk)
    sessions = player.session_entries.select_related(
        'session__game'
    ).order_by('-session__started_at')
    groups = player.group_memberships.select_related('group').all()
    can_edit = request.user.is_authenticated and player.is_editable_by(request.user)
    can_invite = (
        request.user.is_authenticated
        and not player.user
        and player.email
    )
    return render(request, 'players/player_detail.html', {
        'player': player,
        'sessions': sessions,
        'groups': groups,
        'can_edit': can_edit,
        'can_invite': can_invite,
    })


# ---------------------------------------------------------------------------
# Player creation flow
# ---------------------------------------------------------------------------

@login_required
def player_create(request):
    """
    Step 1 — Show the create player form.
    On POST, check for an existing player with the same email and redirect
    to the match confirmation screen if found, otherwise create directly.
    """
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        nickname = request.POST.get('nickname', '').strip()
        email = request.POST.get('email', '').strip().lower() or None
        group_id = request.POST.get('group_id')

        if not name:
            messages.error(request, "Name is required.")
            return render(request, 'players/player_create.html', {
                'post': request.POST,
                'groups': PlayerGroup.objects.filter(owner=request.user),
            })

        # Email match check — the core of Option C
        if email:
            try:
                existing = Player.objects.get(email=email)
                # Store form data in session so confirmation screen can use it
                request.session['pending_player'] = {
                    'name': name,
                    'nickname': nickname,
                    'email': email,
                    'group_id': group_id,
                }
                return redirect(
                    reverse('players:confirm_match', kwargs={'pk': existing.pk})
                )
            except Player.DoesNotExist:
                pass

        # No match found — create a new player record
        player = Player.objects.create(
            name=name,
            nickname=nickname,
            email=email,
            created_by=request.user,
        )
        _maybe_add_to_group(player, group_id, request.user)
        messages.success(request, f"{player.display_name} added.")
        return redirect('players:detail', pk=player.pk)

    return render(request, 'players/player_create.html', {
        'groups': PlayerGroup.objects.filter(owner=request.user),
    })


@login_required
def player_confirm_match(request, pk):
    """
    Step 2 — Show the existing player card and ask the user to confirm
    whether this is the same person or a different one.
    """
    existing = get_object_or_404(Player, pk=pk)
    pending = request.session.get('pending_player', {})

    if not pending:
        # Session expired or direct URL access — send back to create
        return redirect('players:create')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'use_existing':
            # Link the existing player to the requesting user's group
            group_id = pending.get('group_id')
            _maybe_add_to_group(existing, group_id, request.user)
            del request.session['pending_player']
            messages.success(request, f"{existing.display_name} added to your group.")
            return redirect('players:detail', pk=existing.pk)

        elif action == 'create_new':
            # User confirmed they want a separate record despite the match
            player = Player.objects.create(
                name=pending['name'],
                nickname=pending.get('nickname', ''),
                email=None,  # Clear email to avoid unique constraint clash
                created_by=request.user,
            )
            _maybe_add_to_group(player, pending.get('group_id'), request.user)
            del request.session['pending_player']
            messages.warning(
                request,
                f"Created a separate record for {player.display_name}. "
                "Their history won't be shared with other players of the same name."
            )
            return redirect('players:detail', pk=player.pk)

    return render(request, 'players/player_confirm_match.html', {
        'existing': existing,
        'pending': pending,
    })


# ---------------------------------------------------------------------------
# Invite / claim flow
# ---------------------------------------------------------------------------

@login_required
def player_send_invite(request, pk):
    """
    Send a ClaimToken email to a player so they can register and link
    their User account to their existing Player record.
    Only available if the player has an email and no user account yet.
    """
    player = get_object_or_404(Player, pk=pk)

    if player.user:
        messages.info(request, f"{player.display_name} already has an account.")
        return redirect('players:detail', pk=pk)

    if not player.email:
        messages.error(request, "This player has no email address on record.")
        return redirect('players:detail', pk=pk)

    # Create or refresh the claim token
    token_obj, _ = ClaimToken.objects.get_or_create(player=player)
    if not token_obj.is_valid:
        # Expired — regenerate
        token_obj.delete()
        token_obj = ClaimToken.objects.create(player=player)

    claim_url = request.build_absolute_uri(
        reverse('players:claim', kwargs={'token': token_obj.token})
    )

    subject = f"You've been invited to Score Keeper"
    body = render_to_string('players/email/invite.txt', {
        'player': player,
        'claim_url': claim_url,
        'invited_by': request.user.get_full_name() or request.user.username,
    })
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [player.email])

    messages.success(request, f"Invite sent to {player.email}.")
    return redirect('players:detail', pk=pk)


def player_claim(request, token):
    """
    The landing page for a player claiming their profile via invite link.
    Handles both new registration and linking to an existing account.
    """
    token_obj = get_object_or_404(ClaimToken, token=token)

    if not token_obj.is_valid:
        return render(request, 'players/claim_invalid.html', {
            'reason': 'expired' if token_obj.used is False else 'already used',
        })

    player = token_obj.player

    if request.user.is_authenticated:
        # Logged-in user is claiming this player record
        if hasattr(request.user, 'player_profile'):
            return render(request, 'players/claim_conflict.html', {
                'player': player,
                'existing_profile': request.user.player_profile,
            })
        player.user = request.user
        player.save(update_fields=['user'])
        token_obj.mark_used()
        messages.success(
            request,
            f"Your account is now linked to {player.display_name}. "
            "Your full game history is available."
        )
        return redirect('players:detail', pk=player.pk)

    # Not logged in — send to registration with token preserved in session
    request.session['claim_token'] = token
    return redirect(f"{reverse('account_signup')}?next={reverse('players:claim', kwargs={'token': token})}")


# ---------------------------------------------------------------------------
# Group management
# ---------------------------------------------------------------------------

@login_required
def group_list(request):
    groups = PlayerGroup.objects.filter(owner=request.user).prefetch_related(
        'memberships__player'
    )
    return render(request, 'players/group_list.html', {'groups': groups})


@login_required
def group_create(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        if not name:
            messages.error(request, "Group name is required.")
            return render(request, 'players/group_form.html')
        group = PlayerGroup.objects.create(
            owner=request.user,
            name=name,
            description=description,
        )
        messages.success(request, f"Group '{group.name}' created.")
        return redirect('players:group_detail', pk=group.pk)
    return render(request, 'players/group_form.html')


@login_required
def group_detail(request, pk):
    group = get_object_or_404(PlayerGroup, pk=pk, owner=request.user)
    memberships = group.memberships.select_related('player').all()
    return render(request, 'players/group_detail.html', {
        'group': group,
        'memberships': memberships,
    })


@login_required
def group_update(request, pk):
    group = get_object_or_404(PlayerGroup, pk=pk, owner=request.user)
    if request.method == 'POST':
        group.name = request.POST.get('name', group.name).strip()
        group.description = request.POST.get('description', group.description).strip()
        group.save()
        messages.success(request, "Group updated.")
        return redirect('players:group_detail', pk=group.pk)
    return render(request, 'players/group_form.html', {'group': group})


@login_required
def group_delete(request, pk):
    group = get_object_or_404(PlayerGroup, pk=pk, owner=request.user)
    if request.method == 'POST':
        name = group.name
        group.delete()
        messages.success(request, f"Group '{name}' deleted.")
        return redirect('players:group_list')
    return render(request, 'players/group_confirm_delete.html', {'group': group})


@login_required
def group_remove_player(request, group_pk, player_pk):
    group = get_object_or_404(PlayerGroup, pk=group_pk, owner=request.user)
    membership = get_object_or_404(GroupMembership, group=group, player_id=player_pk)
    if request.method == 'POST':
        membership.delete()
        messages.success(request, "Player removed from group.")
    return redirect('players:group_detail', pk=group_pk)

@login_required
def player_update(request, pk):
    player = get_object_or_404(Player, pk=pk)

    if not player.is_editable_by(request.user):
        messages.error(request, "You don't have permission to edit this player.")
        return redirect('players:detail', pk=pk)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        nickname = request.POST.get('nickname', '').strip()
        email = request.POST.get('email', '').strip().lower() or None

        if not name:
            messages.error(request, "Name is required.")
            return render(request, 'players/player_update.html', {'player': player})

        # If email changed, check it doesn't clash with another player
        if email and email != player.email:
            clash = Player.objects.filter(email=email).exclude(pk=pk).first()
            if clash:
                messages.error(
                    request,
                    f"That email is already linked to {clash.display_name}. "
                    "Each player must have a unique email."
                )
                return render(request, 'players/player_update.html', {'player': player})

        player.name = name
        player.nickname = nickname
        player.email = email
        player.save(update_fields=['name', 'nickname', 'email', 'updated_at'])
        messages.success(request, f"{player.display_name} updated.")
        return redirect('players:detail', pk=pk)

    return render(request, 'players/player_update.html', {'player': player})

# ---------------------------------------------------------------------------
# Team management
# ---------------------------------------------------------------------------

@login_required
def team_list(request):
    teams = Team.objects.prefetch_related('players').order_by('name')
    return render(request, 'players/team_list.html', {'teams': teams})


@login_required
def team_create(request):
    if request.method == 'POST':
        form = TeamForm(request.POST)
        if form.is_valid():
            team = form.save()
            messages.success(request, f"Team '{team.name}' created.")
            return redirect('players:team_list')
    else:
        form = TeamForm()
    return render(request, 'players/team_form.html', {
        'form': form,
        'title': 'Create Team',
        'button_label': 'Create Team',
    })


@login_required
def team_update(request, pk):
    team = get_object_or_404(Team, pk=pk)
    if request.method == 'POST':
        form = TeamForm(request.POST, instance=team)
        if form.is_valid():
            form.save()
            messages.success(request, f"Team '{team.name}' updated.")
            return redirect('players:team_list')
    else:
        form = TeamForm(instance=team)
    return render(request, 'players/team_form.html', {
        'form': form,
        'title': 'Edit Team',
        'button_label': 'Save Changes',
    })


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _maybe_add_to_group(player, group_id, user):
    """Add player to a group if group_id is provided and owned by user."""
    if not group_id:
        return
    try:
        group = PlayerGroup.objects.get(pk=group_id, owner=user)
        GroupMembership.objects.get_or_create(group=group, player=player)
    except PlayerGroup.DoesNotExist:
        pass
