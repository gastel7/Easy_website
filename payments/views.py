import json
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from tickets.models import UserTicket

from . import tamo
from .forms import CollecteForm
from .models import EVENEMENTS_WEBHOOK, Paiement, WebhookTamo

# Délai minimal entre deux interrogations de l'API pour un même paiement
# (limite Tamo : 120 lectures / minute)
DELAI_VERIF_API = 4  # secondes


# ---------------------------------------------------------------------------
# Accès
# ---------------------------------------------------------------------------

def _paiement_de(reference, user):
    return get_object_or_404(Paiement, reference=reference, user=user)


def _donnees_depuis_reponse(info):
    """Réponse de GET statut → dictionnaire dans le même format que la charge webhook."""
    return {
        'status': info.get('statut', ''),
        'reference': info.get('reference', ''),
        'merchant_reference': info.get('merchant_reference', ''),
        'amount': info.get('amount'),
    }


def _confirmer(paiement, donnees, source=''):
    """Applique une notification/interrogation Tamo à un paiement.

    Contrôles : merchant_reference cohérent, montant conforme (jamais de validation sur
    un montant différent), aucun retour en arrière depuis un statut définitif.
    Retourne True si le paiement a changé.
    """
    donnees = donnees or {}
    merchant_reference = str(donnees.get('merchant_reference') or '')
    if merchant_reference and merchant_reference != paiement.reference:
        # Notification destinée à une autre commande : on n'y touche pas.
        return False

    statut_tamo = str(donnees.get('status') or '').lower()
    if not statut_tamo:
        return False

    if statut_tamo == 'success' and not paiement.montant_confirme(donnees.get('amount')):
        paiement.message = "Montant confirmé par Tamo différent de la commande."
        paiement.save(update_fields=['message', 'updated_at'])
        WebhookTamo.objects.create(
            evenement=f'{source}.montant_incoherent' if source else 'montant_incoherent',
            tamo_reference=str(donnees.get('reference') or paiement.tamo_reference or ''),
            paiement=paiement, charge_utile=donnees, signee_valide=True,
            traite=False, erreur=paiement.message,
        )
        return False

    libelle = {
        'success': "Paiement confirmé.",
        'failed': "Le paiement a échoué. Vous pouvez réessayer.",
        'expired': "La demande de paiement a expiré. Vous pouvez relancer un paiement.",
        'cancelled': "Paiement annulé.",
        'pending': "Paiement en attente de confirmation de l'opérateur…",
        'processing': "Confirmation reçue, paiement en cours…",
    }.get(statut_tamo, '')

    changement = paiement.appliquer_statut_tamo(
        statut_tamo, tamo_reference=str(donnees.get('reference') or ''), message=libelle)
    paiement.save()
    return changement


def _interroger_tamo(paiement, forcer=False):
    """Interroge le statut chez Tamo (plafonné en fréquence) et applique le résultat."""
    if paiement.est_paye:
        return True
    identifiant = paiement.tamo_reference or paiement.tamo_identifiant
    if not identifiant:
        return False

    maintenant = timezone.now()
    if not forcer and paiement.derniere_verification \
            and (maintenant - paiement.derniere_verification).total_seconds() < DELAI_VERIF_API:
        return False

    paiement.derniere_verification = maintenant
    paiement.save(update_fields=['derniere_verification', 'updated_at'])

    try:
        info = tamo.interroger_statut(identifiant)
    except tamo.TamoError as erreur:
        # 429 / réseau : on garde l'état connu, l'utilisateur re-sonde
        paiement.message = str(erreur)
        paiement.save(update_fields=['message', 'updated_at'])
        return False
    return _confirmer(paiement, _donnees_depuis_reponse(info), source='poll')


# ---------------------------------------------------------------------------
# Page de paiement
# ---------------------------------------------------------------------------

@login_required
def page_paiement(request, reference):
    paiement = _paiement_de(reference, request.user)

    if paiement.est_paye:
        messages.success(request, "Ce paiement a déjà été confirmé : vos billets sont valides.")
        return redirect('account:mes-billets')

    cfg = tamo.config()
    billets = paiement.billets.select_related('category', 'category__event').order_by('id')

    context = {
        'paiement': paiement,
        'billets': billets,
        'evenement': paiement.event,
        'form': CollecteForm(),
        'tamo_configure': tamo.est_configure(),
        'tamo_checkout_actif': cfg['CHECKOUT_ACTIVE'] and bool(cfg['API_TOKEN']) and bool(cfg['PRODUCT_ID']),
        'tamo_sdk_url': cfg['CHECKOUT_SDK_URL'],
        'tamo_public_key': cfg['API_TOKEN'],
        'tamo_produit': cfg['PRODUCT_ID'],
        'tamo_marchand': cfg['NOM_MARCHAND'],
        'devise': paiement.devise,
    }
    return render(request, 'payments/paiement.html', context)


@login_required
@require_POST
def lancer_collecte(request, reference):
    """Démarre (ou relance) la collecte côté serveur. Répond en JSON."""
    paiement = _paiement_de(reference, request.user)

    if paiement.est_paye:
        return JsonResponse({'statut': 'reussi', 'paye': True})

    if not tamo.est_configure():
        return JsonResponse({
            'erreur': "Le paiement en ligne n'est pas encore configuré sur ce site. "
                      "Renseignez les clés Tamo (TAMO_API_TOKEN, TAMO_API_SECRET, TAMO_PRODUCT_ID).",
        }, status=503)

    form = CollecteForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'erreurs': form.errors}, status=400)

    paiement.telephone = form.cleaned_data['telephone']
    paiement.operateur = form.cleaned_data['operateur']

    # Clé d'idempotence : on la rejoue telle quelle tant que la tentative est en cours
    # (Tamo renvoie la transaction existante, rien n'est débité deux fois).
    if not paiement.cle_idempotence or paiement.statut in ('echoue', 'expire', 'annule'):
        paiement.nouvelle_cle_idempotence()
    paiement.save(update_fields=['telephone', 'operateur', 'tentative', 'cle_idempotence', 'updated_at'])

    try:
        resultat = tamo.creer_collecte(
            montant=paiement.montant,
            telephone=paiement.telephone,
            operateur=paiement.operateur,
            merchant_reference=paiement.reference,
            payer_name=request.user.get_full_name() or request.user.username,
            description=f"Billets EASY — {paiement.event.titre}",
            metadata={'event_id': paiement.event_id, 'user_id': request.user.pk},
            idempotency_key=paiement.cle_idempotence,
        )
    except tamo.TamoError as erreur:
        # Réseau / 5xx / 429 : on garde la même clé (le prochain appel rejoue l'opération).
        # Refus 4xx : la requête a été rejetée, on repart avec une clé neuve.
        rejouable = erreur.status_code is None or erreur.status_code == 429 or erreur.status_code >= 500
        if rejouable:
            paiement.message = str(erreur)
        else:
            paiement.message = str(erreur)
            paiement.cle_idempotence = ''
            paiement.statut = 'en_attente'
        paiement.save(update_fields=['message', 'cle_idempotence', 'statut', 'updated_at'])
        return JsonResponse({'erreur': str(erreur)}, status=502)

    paiement.statut = 'en_cours'
    paiement.tamo_reference = resultat['reference'] or paiement.tamo_reference
    paiement.tamo_identifiant = resultat['identifiant'] or paiement.tamo_identifiant
    paiement.derniere_verification = timezone.now()
    paiement.message = "Demande envoyée : confirmez le paiement sur votre téléphone."
    paiement.save()

    return JsonResponse({
        'statut': paiement.statut,
        'reference': paiement.reference,
        'tamo_reference': paiement.tamo_reference,
        'message': paiement.message,
    })


@login_required
@require_GET
def statut_paiement(request, reference):
    """Interrogation périodique depuis la page de paiement (le webhook arrive aussi)."""
    paiement = _paiement_de(reference, request.user)
    _interroger_tamo(paiement)
    paiement.refresh_from_db()
    return JsonResponse({
        'statut': paiement.statut,
        'paye': paiement.est_paye,
        'message': paiement.message,
        'lance': bool(paiement.cle_idempotence),
    })


@login_required
@require_POST
def confirmer_checkout(request, reference):
    """Le portail TamoCheckout (SDK) a renvoyé une référence : on la vérifie côté serveur.

    Le navigateur n'est jamais cru sur parole : on interroge l'API avant de valider.
    """
    paiement = _paiement_de(reference, request.user)
    reference_tamo = (request.POST.get('reference') or '').strip()
    if not reference_tamo:
        return JsonResponse({'erreur': "Référence de paiement manquante."}, status=400)

    try:
        info = tamo.interroger_statut(reference_tamo)
    except tamo.TamoError as erreur:
        # Non concluant : le webhook / la sonde finiront par confirmer.
        return JsonResponse({'statut': paiement.statut, 'paye': paiement.est_paye,
                             'message': str(erreur)}, status=202)

    donnees = _donnees_depuis_reponse(info)
    donnees['reference'] = donnees['reference'] or reference_tamo
    donnees['merchant_reference'] = donnees['merchant_reference'] or paiement.reference
    _confirmer(paiement, donnees, source='checkout')
    paiement.refresh_from_db()
    return JsonResponse({'statut': paiement.statut, 'paye': paiement.est_paye,
                         'message': paiement.message})


@login_required
@require_GET
def paiement_du_billet(request, billet_id):
    """« Payer » depuis Mes billets : renvoie vers le paiement de la commande, ou en crée
    un pour un billet réservé avant l'intégration du paiement."""
    billet = get_object_or_404(UserTicket, pk=billet_id, user=request.user)

    if billet.statut != 'en_attente':
        messages.info(request, f"Ce billet est « {billet.get_statut_display()} ».")
        return redirect('account:mes-billets')

    paiement = Paiement.objects.filter(billets=billet, user=request.user).order_by('-created_at').first()
    if paiement is None:
        if not billet.prix_achat:
            messages.info(request, "Ce billet est gratuit : il est déjà valide.")
            return redirect('account:mes-billets')
        paiement = Paiement.objects.create(
            user=request.user, event=billet.category.event, montant=billet.prix_achat)
        paiement.billets.set([billet])
    elif paiement.est_paye:
        # Billet d'une commande déjà réglée : on le valide, on ne re-facture pas
        paiement.valider_billets()
        messages.success(request, "Ce paiement est déjà confirmé : vos billets sont valides.")
        return redirect('account:mes-billets')

    return redirect('payments:page', paiement.reference)


# ---------------------------------------------------------------------------
# Webhook Tamo (doc TASA §6)
# ---------------------------------------------------------------------------

@csrf_exempt
@require_POST
def webhook_tamo(request):
    """POST signé par TamoAPI. Répond 2xx vite, déduplique, ne revient jamais en arrière."""
    corps = request.body  # octets BRUTS : la signature porte dessus, avant tout parsing
    signature = request.META.get('HTTP_X_WEBHOOK_SIGNATURE', '')

    if not tamo.verifier_signature_webhook(corps, signature):
        return HttpResponse("Signature invalide", status=401)

    try:
        charge = json.loads(corps.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return HttpResponse("Charge illisible", status=400)

    evenement = str(charge.get('event') or '')
    data = charge.get('data') if isinstance(charge.get('data'), dict) else {}
    reference_tamo = str(data.get('reference') or '')

    if evenement == 'webhook.test':
        # Test de l'URL de rappel : montant nul, on répond simplement 2xx
        WebhookTamo.objects.create(evenement=evenement,
                                   tamo_reference=reference_tamo or f'test-{uuid.uuid4().hex}',
                                   charge_utile=charge, signee_valide=True, traite=True)
        return HttpResponse("OK")

    statut_attendu = EVENEMENTS_WEBHOOK.get(evenement)
    if statut_attendu is None:
        # Événement inconnu : on accepte pour ne pas provoquer de reprises inutiles
        WebhookTamo.objects.create(evenement=evenement or 'inconnu',
                                   tamo_reference=reference_tamo or uuid.uuid4().hex,
                                   charge_utile=charge, signee_valide=True, traite=True,
                                   erreur="Événement non géré.")
        return HttpResponse("OK")

    # Déduplication : même event + même reference = notification déjà reçue
    journal, deja_recu = WebhookTamo.objects.get_or_create(
        evenement=evenement, tamo_reference=reference_tamo,
        defaults={'charge_utile': charge, 'signee_valide': True},
    )
    if not deja_recu:
        return HttpResponse("Déjà traité")  # notification reçue deux fois

    paiement = Paiement.objects.filter(tamo_reference=reference_tamo).first() \
        or Paiement.objects.filter(reference=str(data.get('merchant_reference') or '')).first()

    if paiement is None:
        journal.traite = True
        journal.erreur = "Aucun paiement ne correspond à cette référence."
        journal.save(update_fields=['traite', 'erreur'])
        return HttpResponse("OK")

    journal.paiement = paiement
    try:
        modifie = _confirmer(paiement, data, source='webhook')
    except Exception as erreur:  # journalise puis 200 pour ne pas boucler chez Tamo
        journal.erreur = f"Erreur de traitement : {erreur}"
        journal.save(update_fields=['paiement', 'erreur'])
        return HttpResponse("OK")
    journal.traite = True
    if not modifie and paiement.statut != 'reussi':
        journal.erreur = "Statut ignoré (statut déjà définitif)."
    journal.save(update_fields=['paiement', 'traite', 'erreur'])
    return HttpResponse("OK")
