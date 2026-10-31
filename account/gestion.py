"""Gestion du site : pages réservées aux modérateurs (et aux admins). Consultation uniquement."""
import re
from functools import wraps

from django.contrib import messages
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import urlencode
from django.views.decorators.http import require_POST, require_safe

from .espace import peut_administrer

User = get_user_model()

UTILISATEURS_PAR_PAGE = 25
NOMBRE_DE_LIGNES_DETAIL = 5

# Seuls ces deux rôles peuvent être attribués depuis cette page. « admin » et « modérateur » ne s'attribuent
# JAMAIS ici : uniquement par un admin, dans /admin/.
ROLES_ATTRIBUABLES = ('organisateur', 'participant')

# Nom de classe CSS (sans accent) pour chaque rôle
ROLE_CSS = {'admin': 'admin', 'modérateur': 'moderateur', 'organisateur': 'organisateur', 'participant': 'participant'}


def administration_requise(vue):
    """Réserve une vue aux modérateurs et aux admins (vérifié côté serveur)."""
    @wraps(vue)
    def enveloppe(request, *args, **kwargs):
        if not peut_administrer(request.user):
            raise PermissionDenied("Cette page est réservée à l'équipe de gestion du site.")
        return vue(request, *args, **kwargs)
    return login_required(enveloppe)


def utilisateurs_avec_compteurs():
    return User.objects.annotate(
        nb_evenements=Count('events', distinct=True),
        nb_billets=Count('my_tickets', distinct=True),
    )


def peut_attribuer_un_role(acteur, cible):
    """On ne peut donner un rôle qu'à un compte qui n'en a pas encore (inscription via Google, par exemple).
    Jamais à soi-même, ni à un superuser. Changer un rôle existant se fait dans /admin/."""
    return cible.pk != acteur.pk and not cible.is_superuser and not cible.role


def initiales(utilisateur):
    texte = f"{utilisateur.first_name[:1]}{utilisateur.last_name[:1]}".strip() or utilisateur.username[:2]
    return texte.upper()


@administration_requise
@require_safe
def accueil(request):
    # Pour l'instant, le seul module est la liste des utilisateurs
    return redirect('account:gestion-utilisateurs')


@administration_requise
@require_safe
def liste_utilisateurs(request):
    recherche = request.GET.get('q', '').strip()
    roles_valides = [code for code, _ in User.ROLE_CHOICES]
    role = request.GET.get('role', '')
    role_actif = role if (role in roles_valides or role == 'sans_role') else 'tous'
    statut = request.GET.get('statut', '')
    statut_actif = statut if statut in ('actifs', 'inactifs') else 'tous'

    tous = User.objects.all()
    utilisateurs = utilisateurs_avec_compteurs()

    if recherche:
        # Le téléphone est stocké sans espaces (+242061234567) : on compare donc sans espaces ni tirets
        chiffres = re.sub(r'[\s.\-()]', '', recherche)
        condition = (
            Q(first_name__icontains=recherche) | Q(last_name__icontains=recherche)
            | Q(username__icontains=recherche) | Q(email__icontains=recherche)
        )
        if chiffres:
            condition |= Q(tel__contains=chiffres)
            # Saisie « à la française » (06 12 ...) : en base, le 0 de tête est absent (+33 6 12 ...).
            # Un numéro national est toujours la FIN du numéro international, d'où « endswith ».
            if chiffres.startswith('0') and chiffres.lstrip('0'):
                condition |= Q(tel__endswith=chiffres.lstrip('0'))
        utilisateurs = utilisateurs.filter(condition)

    if role_actif == 'sans_role':
        utilisateurs = utilisateurs.filter(role='')
    elif role_actif != 'tous':
        utilisateurs = utilisateurs.filter(role=role_actif)

    if statut_actif == 'actifs':
        utilisateurs = utilisateurs.filter(is_active=True)
    elif statut_actif == 'inactifs':
        utilisateurs = utilisateurs.filter(is_active=False)

    utilisateurs = utilisateurs.order_by('-date_joined', '-id')

    def lien(**changements):
        """Adresse de la liste avec les filtres actuels, en changeant seulement ce qu'on demande."""
        params = {'q': recherche, 'role': role_actif, 'statut': statut_actif}
        params.update(changements)
        params = {cle: valeur for cle, valeur in params.items() if valeur and valeur != 'tous'}
        return '?' + urlencode(params)

    # Compteurs des filtres : une seule requête pour tous les rôles
    par_role = {ligne['role']: ligne['n'] for ligne in tous.values('role').annotate(n=Count('id'))}
    filtres_role = [{'code': 'tous', 'label': 'Tous', 'nombre': tous.count(), 'url': lien(role='tous')}]
    filtres_role += [
        {'code': code, 'label': libelle, 'nombre': par_role.get(code, 0), 'url': lien(role=code)}
        for code, libelle in User.ROLE_CHOICES
    ]
    filtres_role.append({'code': 'sans_role', 'label': 'Sans rôle', 'nombre': par_role.get('', 0), 'url': lien(role='sans_role')})

    filtres_statut = [
        {'code': 'tous', 'label': 'Tous', 'url': lien(statut='tous')},
        {'code': 'actifs', 'label': 'Actifs', 'url': lien(statut='actifs')},
        {'code': 'inactifs', 'label': 'Inactifs', 'url': lien(statut='inactifs')},
    ]

    paginator = Paginator(utilisateurs, UTILISATEURS_PAR_PAGE)
    page_obj = paginator.get_page(request.GET.get('page'))
    for utilisateur in page_obj:
        utilisateur.role_css = ROLE_CSS.get(utilisateur.role, 'aucun')

    parametres = request.GET.copy()
    parametres.pop('page', None)

    context = {
        'utilisateurs': page_obj,
        'page_obj': page_obj,
        'total': paginator.count,
        'recherche': recherche,
        'role_actif': role_actif,
        'statut_actif': statut_actif,
        'filtres_role': filtres_role,
        'filtres_statut': filtres_statut,
        'url_sans_recherche': lien(q=''),
        'base_qs': parametres.urlencode(),
    }
    return render(request, 'account/users_list.html', context)


@administration_requise
@require_safe
def detail_utilisateur(request, user_id):
    utilisateur = get_object_or_404(utilisateurs_avec_compteurs(), pk=user_id)
    utilisateur.role_css = ROLE_CSS.get(utilisateur.role, 'aucun')
    utilisateur.initiales = initiales(utilisateur)

    evenements = utilisateur.events.order_by('-date_debut')[:NOMBRE_DE_LIGNES_DETAIL]
    billets = utilisateur.my_tickets.select_related('category__event').order_by('-date_achat')[:NOMBRE_DE_LIGNES_DETAIL]

    context = {
        'utilisateur': utilisateur,
        'evenements': evenements,
        'billets': billets,
        'peut_attribuer_role': peut_attribuer_un_role(request.user, utilisateur),
        'roles_attribuables': [(code, libelle) for code, libelle in User.ROLE_CHOICES if code in ROLES_ATTRIBUABLES],
    }
    return render(request, 'account/detail_utilisateur.html', context)


@administration_requise
@require_POST
def attribuer_role(request, user_id):
    """Donne un rôle (organisateur ou participant) à un compte qui n'en a pas encore."""
    cible = get_object_or_404(User, pk=user_id)
    role = request.POST.get('role', '')

    if cible.pk == request.user.pk or cible.is_superuser:
        raise PermissionDenied("Ce compte ne peut pas être modifié depuis cette page.")

    if role not in ROLES_ATTRIBUABLES:
        messages.error(request, "Rôle invalide.")
    else:
        # UPDATE conditionnel : si un autre modérateur vient de donner un rôle, rien n'est écrasé
        modifie = User.objects.filter(pk=cible.pk, role='').update(role=role)
        if modifie:
            LogEntry.objects.log_actions(
                request.user.pk, [cible], CHANGE,
                f"Rôle attribué par {request.user.username} : aucun → {role}",
                single_object=True,
            )
            messages.success(request, f"Le rôle « {dict(User.ROLE_CHOICES)[role]} » a été attribué.")
        else:
            messages.error(request, "Ce compte a déjà un rôle. Seul un admin peut le modifier (dans /admin/).")

    return redirect('account:gestion-utilisateur', user_id=cible.pk)