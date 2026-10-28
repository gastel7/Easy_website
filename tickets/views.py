import base64
from decimal import Decimal
from io import BytesIO

import qrcode
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from core.models import Events
from payments.models import Paiement
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

    paiement = None

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
            billets_payes = []
            for categorie_id, quantite in commande.items():
                categorie = categories[categorie_id]
                statut = 'valide' if not categorie.prix else 'en_attente'
                for _ in range(quantite):
                    ticket = UserTicket.objects.create(category=categorie, user=user, statut=statut)
                    if categorie.prix:
                        billets_payes.append(ticket)

            # 3. Commande payante : ouvrir le paiement (TamoAPI) et y renvoyer l'acheteur
            if billets_payes:
                paiement = Paiement.objects.create(
                    user=user,
                    event=event,
                    montant=sum((ticket.prix_achat for ticket in billets_payes), Decimal('0')),
                )
                paiement.billets.set(billets_payes)
    except CommandeRefusee as erreur:
        messages.error(request, str(erreur))
        return retour

    recap = ', '.join(f"{quantite} {categories[categorie_id].nom}" for categorie_id, quantite in commande.items())

    if paiement is not None:
        # Billets payants : la page de paiement lance la collecte Mobile Money (Tamo)
        messages.success(request, f"Commande enregistrée : {recap}. Réglez-la pour valider vos billets.")
        return redirect('payments:page', paiement.reference)

    messages.success(request, f"Commande confirmée : {recap}.")
    return retour


# ---------------------------------------------------------------------------
# QR code du billet
# ---------------------------------------------------------------------------

def _url_de_verification(request, billet):
    """Lien absolu encodé dans le QR code : lisible par n'importe quel lecteur."""
    return request.build_absolute_uri(reverse('tickets:verifier', args=[billet.code_unique]))


@login_required
@require_GET
def qr_code(request, billet_id):
    """QR code du billet validé (ou déjà scanné)."""
    billet = get_object_or_404(UserTicket, pk=billet_id, user=request.user)

    if billet.statut not in ('valide', 'scanne'):
        messages.info(request, "Le QR code est disponible une fois le billet réglé.")
        return redirect('account:mes-billets')

    url_verification = _url_de_verification(request, billet)

    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(url_verification)
    qr.make(fit=True)
    image = qr.make_image(fill_color='black', back_color='white')

    tampon = BytesIO()
    image.save(tampon, format='PNG')

    context = {
        'billet': billet,
        'evenement': billet.category.event,
        'qr_base64': base64.b64encode(tampon.getvalue()).decode('ascii'),
        'url_verification': url_verification,
    }
    return render(request, 'tickets/qr_code.html', context)


@require_GET
def verifier_billet(request, code_unique):
    """Page publique ouverte par le QR code : valide le billet à l'entrée de l'événement.

    Le code_unique sert de jeton : il est impossible à deviner (32 caractères aléatoires).
    """
    billet = get_object_or_404(
        UserTicket.objects.select_related('category__event', 'user'),
        code_unique=code_unique,
    )
    context = {
        'billet': billet,
        'evenement': billet.category.event,
        'utilisable': billet.est_utilisable or billet.statut == 'scanne',
    }
    return render(request, 'tickets/verifier_billet.html', context)