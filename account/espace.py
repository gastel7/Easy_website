from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, DecimalField, Max, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.models import Events
from tickets.models import UserTicket

# Rôles qui ont accès à l'administration. Le superuser est aussi admin.
ROLES_ADMINISTRATION = ('admin', 'modérateur')
STATUTS_VENDUS = ('valide', 'scanne')  # billets payés ou déjà utilisés
NOMBRE_DE_LIGNES = 5
NOMBRE_DE_VENTES_RECENTES = 20


def peut_administrer(user):
    return user.is_superuser or getattr(user, 'role', None) in ROLES_ADMINISTRATION


def est_organisateur(user, a_des_evenements=None):
    """Vrai si l'utilisateur a un espace organisateur : rôle « organisateur » ou au moins un événement."""
    if getattr(user, 'role', None) == 'organisateur':
        return True
    if a_des_evenements is None:
        a_des_evenements = user.events.exists()
    return a_des_evenements


def organisateur_requis(vue):
    """Réserve une vue aux organisateurs (vérifié côté serveur, pas seulement caché dans le menu)."""
    @wraps(vue)
    def enveloppe(request, *args, **kwargs):
        if not est_organisateur(request.user):
            raise PermissionDenied("Cette page est réservée aux organisateurs.")
        return vue(request, *args, **kwargs)
    return login_required(enveloppe)


def contexte_espace(request):
    """Variables disponibles dans tous les templates : menu, mode d'affichage, droits."""
    user = request.user
    if not user.is_authenticated:
        return {}

    a_des_billets = user.my_tickets.exists()
    a_des_evenements = user.events.exists()

    # Un compte inscrit comme « organisateur » a un espace organisateur,
    # même avant d'avoir publié son premier événement.
    peut_organiser = est_organisateur(user, a_des_evenements)

    # Mode par défaut : organisateur s'il peut organiser, participant sinon
    mode = request.session.get('espace_mode') or ('organisateur' if peut_organiser else 'participant')
    if mode == 'organisateur' and not peut_organiser:
        mode = 'participant'

    return {
        'espace_mode': mode,
        'espace_a_des_billets': a_des_billets,
        'espace_a_des_evenements': peut_organiser,  # même nom qu'avant, sens élargi : "a un espace organisateur"
        'espace_peut_administrer': peut_administrer(user),
    }


def formater_somme(montant):
    return f"{montant:,.0f}".replace(',', ' ')


def formater_date(date):
    return timezone.localtime(date).strftime('%d/%m/%Y à %H:%M')


def donnees_organisateur(user, maintenant):
    evenements = Events.objects.filter(organisateur=user)
    billets = UserTicket.objects.filter(category__event__organisateur=user).exclude(statut='annule')
    vendus = billets.filter(statut__in=STATUTS_VENDUS)
    encaisse = vendus.aggregate(total=Sum('prix_achat'))['total'] or 0
    vues = evenements.aggregate(total=Sum('nombre_de_vues'))['total'] or 0

    cartes = [
        {'label': 'Événements publiés', 'valeur': str(evenements.count())},
        {'label': 'Billets vendus', 'valeur': str(vendus.count())},
        {'label': 'Montant encaissé', 'valeur': formater_somme(encaisse), 'unite': 'FCFA'},
        {'label': 'Vues', 'valeur': str(vues)},
    ]

    prochains = [
        {
            'titre': evenement.titre,
            'sous_titre': formater_date(evenement.date_debut),
            'droite': evenement.get_statut_display(),
            'url': reverse('core:detail-event', args=[evenement.id]),
        }
        for evenement in evenements.filter(date_debut__gte=maintenant).order_by('date_debut')[:NOMBRE_DE_LIGNES]
    ]

    recents = [
        {
            'titre': billet.category.event.titre,
            'sous_titre': f"{billet.category.nom} · {billet.user.username}",
            'droite': billet.get_statut_display(),
            'url': reverse('core:detail-event', args=[billet.category.event_id]),
        }
        for billet in billets.select_related('category__event', 'user').order_by('-date_achat')[:NOMBRE_DE_LIGNES]
    ]

    listes = [
        {'titre': 'Mes prochains événements', 'vide': "Aucun événement à venir pour le moment.", 'lignes': prochains},
        {'titre': 'Derniers billets réservés', 'vide': "Aucun billet réservé pour le moment.", 'lignes': recents},
    ]
    return cartes, listes


def donnees_participant(user, maintenant):
    billets = UserTicket.objects.filter(user=user).select_related('category__event')
    valides = billets.filter(statut='valide')
    a_regler = billets.filter(statut='en_attente')
    depense = valides.aggregate(total=Sum('prix_achat'))['total'] or 0

    # Prochain événement : le premier billet valide dont l'événement n'est pas encore passé
    a_venir = valides.filter(category__event__date_debut__gte=maintenant).order_by('category__event__date_debut')
    prochain = a_venir.first()

    if prochain:
        valeur_prochain = timezone.localtime(prochain.category.event.date_debut).strftime('%d/%m')
        pastille_prochain = prochain.category.event.titre
    else:
        valeur_prochain, pastille_prochain = '—', ''

    cartes = [
        {'label': 'Billets valides', 'valeur': str(valides.count())},
        {'label': 'À régler', 'valeur': str(a_regler.count()), 'pastille': 'Paiement requis' if a_regler.exists() else ''},
        {'label': 'Prochain événement', 'valeur': valeur_prochain, 'pastille': pastille_prochain},
        {'label': 'Total payé', 'valeur': formater_somme(depense), 'unite': 'FCFA'},
    ]

    # Un événement n'apparaît qu'une fois, même si on a plusieurs billets pour lui
    evenements_vus = set()
    prochains = []
    for billet in a_venir:
        evenement = billet.category.event
        if evenement.id in evenements_vus:
            continue
        evenements_vus.add(evenement.id)
        prochains.append({
            'titre': evenement.titre,
            'sous_titre': formater_date(evenement.date_debut),
            'droite': billet.category.nom,
            'url': reverse('core:detail-event', args=[evenement.id]),
        })
        if len(prochains) == NOMBRE_DE_LIGNES:
            break

    # « Payer » ouvre la page de paiement de la commande concernée (TamoAPI)
    a_payer = [
        {
            'titre': billet.category.event.titre,
            'sous_titre': f"{billet.category.nom} · {formater_somme(billet.prix_achat)} FCFA",
            'droite': 'À payer',
            'url': reverse('payments:billet', args=[billet.id]),
        }
        for billet in a_regler.order_by('-date_achat')[:NOMBRE_DE_LIGNES]
    ]

    listes = [
        {'titre': 'Mes prochains événements', 'vide': "Aucun événement à venir. Réservez un billet pour le voir ici.", 'lignes': prochains},
        {'titre': 'Billets à régler', 'vide': "Aucun billet en attente de paiement.", 'lignes': a_payer},
    ]
    return cartes, listes


def donnees_tableau_de_bord(user, mode):
    maintenant = timezone.now()
    if mode == 'organisateur':
        return donnees_organisateur(user, maintenant)
    return donnees_participant(user, maintenant)

@login_required
def tableau_de_bord(request):
    mode = contexte_espace(request)['espace_mode']
    cartes, listes = donnees_tableau_de_bord(request.user, mode)
    return render(request, 'account/profile/espace/tableau_de_bord.html', {'cartes': cartes, 'listes': listes})


@login_required
@require_POST
def changer_mode(request):
    mode = request.POST.get('mode')
    if mode in ('participant', 'organisateur'):
        request.session['espace_mode'] = mode
    return redirect('account:espace')


STATUTS_BILLETS = [code for code, _ in UserTicket.STATUT_CHOICES]


@login_required
def mes_billets(request):
    tous = UserTicket.objects.filter(user=request.user)
    statut = request.GET.get('statut')
    filtre_actif = statut if statut in STATUTS_BILLETS else 'tous'

    billets = tous if filtre_actif == 'tous' else tous.filter(statut=filtre_actif)
    billets = billets.select_related('category__event').order_by(
        'category__event__date_debut', 'category__event_id', '-date_achat'
    )

    filtres = [{'code': 'tous', 'label': 'Tous', 'nombre': tous.count()}]
    filtres += [
        {'code': code, 'label': libelle, 'nombre': tous.filter(statut=code).count()}
        for code, libelle in UserTicket.STATUT_CHOICES
    ]

    context = {'billets': billets, 'filtres': filtres, 'filtre_actif': filtre_actif}
    return render(request, 'account/profile/espace/mes_billets.html', context)



@login_required
def mes_favoris(request):
    evenements = (
        Events.objects.filter(favoris__user=request.user)
        .select_related('organisateur')
        .annotate(prix_max=Max('ticket_categories__prix'))
        .order_by('-favoris__date_ajout', '-id')
    )
    context = {
        'evenements': evenements,
        'ids_favoris': {event.id for event in evenements},
    }
    return render(request, 'account/profile/espace/mes_favoris.html', context)


# ---------------------------------------------------------------------------
# Espace organisateur : « Mes événements » et « Ventes »
# ---------------------------------------------------------------------------

def evenements_avec_ventes(user):
    """Événements de l'organisateur, avec billets vendus, billets en attente et montant encaissé."""
    vendu = Q(ticket_categories__user_tickets__statut__in=STATUTS_VENDUS)
    en_attente = Q(ticket_categories__user_tickets__statut='en_attente')
    return Events.objects.filter(organisateur=user).annotate(
        billets_vendus=Count('ticket_categories__user_tickets', filter=vendu),
        billets_en_attente=Count('ticket_categories__user_tickets', filter=en_attente),
        montant_encaisse=Coalesce(
            Sum('ticket_categories__user_tickets__prix_achat', filter=vendu),
            Value(0),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
    )


@organisateur_requis
def mes_evenements(request):
    """Tous les événements créés par l'organisateur connecté (et seulement les siens)."""
    maintenant = timezone.now()
    siens = Events.objects.filter(organisateur=request.user)

    periode = request.GET.get('periode')
    filtre_actif = periode if periode in ('a_venir', 'passes') else 'tous'

    evenements = evenements_avec_ventes(request.user)
    if filtre_actif == 'a_venir':
        evenements = evenements.filter(date_debut__gte=maintenant)
    elif filtre_actif == 'passes':
        evenements = evenements.filter(date_debut__lt=maintenant)
    evenements = evenements.order_by('-date_debut')

    filtres = [
        {'code': 'tous', 'label': 'Tous', 'nombre': siens.count()},
        {'code': 'a_venir', 'label': 'À venir', 'nombre': siens.filter(date_debut__gte=maintenant).count()},
        {'code': 'passes', 'label': 'Passés', 'nombre': siens.filter(date_debut__lt=maintenant).count()},
    ]

    context = {'evenements': evenements, 'filtres': filtres, 'filtre_actif': filtre_actif}
    return render(request, 'account/profile/espace/mes_evenements.html', context)


@organisateur_requis
def ventes(request):
    """Ventes de billets pour les événements de l'organisateur connecté."""
    billets = UserTicket.objects.filter(category__event__organisateur=request.user).exclude(statut='annule')
    vendus = billets.filter(statut__in=STATUTS_VENDUS)
    encaisse = vendus.aggregate(total=Sum('prix_achat'))['total'] or 0

    cartes = [
        {'label': 'Billets vendus', 'valeur': str(vendus.count())},
        {'label': 'Montant encaissé', 'valeur': formater_somme(encaisse), 'unite': 'FCFA'},
        {'label': 'En attente de paiement', 'valeur': str(billets.filter(statut='en_attente').count())},
        {'label': 'Billets scannés', 'valeur': str(billets.filter(statut='scanne').count())},
    ]

    par_evenement = [
        {
            'titre': evenement.titre,
            'sous_titre': formater_date(evenement.date_debut),
            'vendus': evenement.billets_vendus,
            'places': evenement.nombre_de_places,
            'en_attente': evenement.billets_en_attente,
            'encaisse': formater_somme(evenement.montant_encaisse),
            'url': reverse('core:detail-event', args=[evenement.id]),
        }
        for evenement in evenements_avec_ventes(request.user).order_by('-date_debut')
    ]

    derniers_billets = [
        {
            'titre': billet.category.event.titre,
            'sous_titre': f"{billet.category.nom} · {billet.user.username}",
            'montant': formater_somme(billet.prix_achat),
            'statut': billet.get_statut_display(),
            'date': formater_date(billet.date_achat),
        }
        for billet in billets.select_related('category__event', 'user').order_by('-date_achat')[:NOMBRE_DE_VENTES_RECENTES]
    ]

    context = {'cartes': cartes, 'par_evenement': par_evenement, 'derniers_billets': derniers_billets}
    return render(request, 'account/profile/espace/ventes.html', context)