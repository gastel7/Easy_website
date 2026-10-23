from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, update_session_auth_hash, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import EmailOrPhoneAuthenticationForm, SignUpForm, UpdateForm

User = get_user_model()

# Backend utilisé pour connecter l'utilisateur juste après son inscription
AUTH_BACKEND = 'account.backends.EmailOrPhoneBackend'


def _redirect_after_login(request):
    """Redirige vers ?next=... (ex. page protégée par @login_required) si l'URL est sûre."""
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(next_url)
    return redirect('account:espace')


# 1. L'inscription
def logup_view(request):
    if request.user.is_authenticated:
        return redirect('account:espace')

    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend=AUTH_BACKEND)
            return redirect('account:espace')
    else:
        form = SignUpForm()

    return render(request, 'account/log/log_up.html', {'form': form})


# 2. La connexion (email ou téléphone)
def login_view(request):
    if request.user.is_authenticated:
        return redirect('account:espace')

    if request.method == 'POST':
        form = EmailOrPhoneAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return _redirect_after_login(request)
    else:
        form = EmailOrPhoneAuthenticationForm(request)

    return render(request, 'account/log/log_in.html', {'form': form})


# 3. La déconnexion
@login_required
def logout_view(request):
    logout(request)
    return redirect('account:login')


# 4. Profil & Mise à jour (avec photo)
@login_required
def profile_view(request):
    if request.method == 'POST':
        form = UpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('account:espace')
    else:
        form = UpdateForm(instance=request.user)
    return render(request, 'account/profile/profile.html', {'form': form})


# 5. Changement de mot de passe
@login_required
def change_password_view(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Évite de déconnecter l'utilisateur
            return redirect('account:espace')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'account/profile/change_password.html', {'form': form})


# 6. Liste des utilisateurs (pour les modérateurs)
@login_required
def users_list_view(request):
    organisateurs = User.objects.filter(role='organisateur')
    participants = User.objects.filter(role='participant')

    context = {
        'organisateurs': organisateurs,
        'participants': participants,
    }
    return render(request, 'account/user_list.html', context)


# 7. Suppression de compte (participant ou organisateur)
@login_required
def delete_account_view(request, user_id):
    user = get_object_or_404(User, id=user_id)

    # Seul un modérateur ou un superuser peut supprimer un utilisateur
    if request.user.role != 'modérateur' and not request.user.is_superuser:
        raise PermissionDenied("Vous n'avez pas l'autorisation de supprimer un utilisateur.")

    if request.method == "POST":
        user_deleted = user.username
        user.delete()

        messages.success(request, f"L'utilisateur {user_deleted} a été supprimé avec succès.")
        return redirect('account:users_list')

    return render(request, 'account/profile/delete_user.html', {'user': user})