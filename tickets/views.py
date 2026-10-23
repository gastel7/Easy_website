from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.models import Events
from .models import TicketCategory, UserTicket

MAX_BILLETS_PAR_COMMANDE = 10


class CommandeRefusee(Exception):
    """La commande ne peut pas être enregistrée : rien n'est créé."""


@login_required
@require_POST
def reserver_billet(request, event_id):
    event = get_object_or_404(Events, id=event_id)
    user = request.user
    peut_gerer = user.is_superuser or getattr(user, 'role', None) == 'modérateur' or user == event.organisateur

    if event.statut == 'prive' and not peut_gerer:
        raise Http404

    retour = redirect('core:detail-event', event.id)

    if event.etat in ('annule', 'termine'):
        messages.error(request, "Cet événement n'accepte plus de réservations.")
        return retour

    # Une quantité par catégorie de cet événement, envoyée dans le champ quantite_<id>
    commande = {}
    for categorie in event.ticket_categories.order_by('id'):
        try:
            quantite = int(request.POST.get(f'quantite_{categorie.id}') or 0)
        except ValueError:
            messages.error(request, "Quantité invalide.")
            return retour

        if quantite < 0:
            messages.error(request, "Quantité invalide.")
            return retour
        if quantite > 0:
            commande[categorie.id] = quantite

    if not commande:
        messages.error(request, "Choisissez au moins un billet.")
        return retour

    if sum(commande.values()) > MAX_BILLETS_PAR_COMMANDE:
        messages.error(request, f"Vous pouvez réserver {MAX_BILLETS_PAR_COMMANDE} billets au maximum par commande.")
        return retour

    try:
        with transaction.atomic():
            # Verrouille les catégories de la commande, toujours dans le même ordre (évite les blocages croisés)
            categories = {
                categorie.id: categorie
                for categorie in TicketCategory.objects.select_for_update()
                .filter(id__in=list(commande), event=event)
                .order_by('id')
            }
            if len(categories) != len(commande):
                raise CommandeRefusee("Un des billets choisis n'existe pas pour cet événement.")

            maintenant = timezone.now()

            # 1. Vérifier toute la commande avant de créer quoi que ce soit
            for categorie_id, quantite in commande.items():
                categorie = categories[categorie_id]

                if not categorie.date_debut_vente <= maintenant <= categorie.date_fin_vente:
                    raise CommandeRefusee(f"La vente du billet « {categorie.nom} » n'est pas ouverte.")

                vendus = UserTicket.objects.filter(category=categorie).exclude(statut='annule').count()
                restants = categorie.quantite_disponible - vendus
                if quantite > restants:
                    raise CommandeRefusee(
                        f"Il ne reste que {max(restants, 0)} billet(s) « {categorie.nom} ». "
                        "Votre commande n'a pas été enregistrée."
                    )

            # 2. Créer les billets. Gratuit : valide tout de suite. Payant : en attente de paiement.
            for categorie_id, quantite in commande.items():
                categorie = categories[categorie_id]
                statut = 'valide' if not categorie.prix else 'en_attente'
                for _ in range(quantite):
                    UserTicket.objects.create(category=categorie, user=user, statut=statut)
    except CommandeRefusee as erreur:
        messages.error(request, str(erreur))
        return retour

    recap = ', '.join(f"{quantite} {categories[categorie_id].nom}" for categorie_id, quantite in commande.items())
    payant = any(categories[categorie_id].prix for categorie_id in commande)

    if payant:
        # TODO : lancer ici le paiement avec la solution de ton collègue, pour le total des billets payants
        messages.info(request, f"Commande enregistrée : {recap}. Les billets payants seront validés après paiement.")
    else:
        messages.success(request, f"Commande confirmée : {recap}.")

    return retour