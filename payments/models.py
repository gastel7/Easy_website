import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


# Statuts renvoyés par TamoAPI (doc TASA §5) → statuts locaux
STATUTS_TAMO = {
    'pending': 'en_cours',      # transaction créée, attente de confirmation opérateur
    'processing': 'en_cours',   # confirmation reçue, en cours chez l'opérateur
    'success': 'reussi',
    'failed': 'echoue',
    'expired': 'expire',
    'cancelled': 'annule',
    'refunded': 'rembourse',
}

# Événements webhook attendus (doc TASA §6)
EVENEMENTS_WEBHOOK = {
    'collection.pending': 'pending',
    'collection.processing': 'processing',
    'collection.success': 'success',
    'collection.failed': 'failed',
    'collection.expired': 'expired',
    'collection.cancelled': 'cancelled',
    'collection.refunded': 'refunded',
}

OPERATEURS = [
    ('MTN_CG', 'MTN Mobile Money Congo'),
    ('ORANGE_SN', 'Orange Money Sénégal'),
]


def generer_reference():
    """Référence marchande : apparaît dans le dashboard Tamo et sert d'identifiant de page."""
    return f"EASY-{secrets.token_urlsafe(9)}"


class Paiement(models.Model):
    """Une commande à payer : regroupe les billets payants d'une réservation.

    statut :
      en_attente — aucun appel à l'API n'a encore été fait (ou nouvelle tentative possible)
      en_cours   — collecte lancée chez Tamo, attente du webhook / de l'interrogation du statut
      reussi     — billets validés
      echoue / expire / annule — nouvelle tentative possible
    """

    STATUT_CHOICES = [
        ('en_attente', 'En attente de paiement'),
        ('en_cours', 'Paiement en cours'),
        ('reussi', 'Payé'),
        ('echoue', 'Échec du paiement'),
        ('expire', 'Paiement expiré'),
        ('annule', 'Paiement annulé'),
        ('rembourse', 'Paiement remboursé'),
    ]
    STATUTS_DEFINITIFS = ('reussi', 'echoue', 'expire', 'annule', 'rembourse')

    reference = models.CharField(max_length=64, unique=True, editable=False, default=generer_reference,
                                 verbose_name="Référence")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='paiements', verbose_name="Acheteur")
    event = models.ForeignKey('core.Events', on_delete=models.PROTECT,
                              related_name='paiements', verbose_name="Événement")
    montant = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Montant")
    devise = models.CharField(max_length=3, default='XAF', verbose_name="Devise")
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_attente',
                              db_index=True, verbose_name="Statut")
    billets = models.ManyToManyField('tickets.UserTicket', related_name='paiements', blank=True,
                                     verbose_name="Billets concernés")

    # Données de la collecte Tamo
    operateur = models.CharField(max_length=20, blank=True, choices=OPERATEURS, verbose_name="Opérateur")
    telephone = models.CharField(max_length=30, blank=True, verbose_name="Numéro Mobile Money")
    tamo_reference = models.CharField(max_length=100, blank=True, db_index=True,
                                      verbose_name="Référence Tamo")
    tamo_identifiant = models.CharField(max_length=100, blank=True, verbose_name="Identifiant Tamo (UUID)")
    cle_idempotence = models.CharField(max_length=190, blank=True, db_index=True,
                                       verbose_name="Clé d'idempotence")
    tentative = models.PositiveIntegerField(default=0, verbose_name="Nombre de tentatives")
    derniere_verification = models.DateTimeField(null=True, blank=True,
                                                 verbose_name="Dernier appel à l'API Tamo")
    message = models.CharField(max_length=255, blank=True, verbose_name="Dernier message")
    paye_le = models.DateTimeField(null=True, blank=True, verbose_name="Date de paiement")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Dernière modification")

    class Meta:
        verbose_name = "Paiement"
        verbose_name_plural = "Paiements"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.reference} — {self.montant} {self.devise} ({self.get_statut_display()})"

    @property
    def est_definitif(self):
        return self.statut in self.STATUTS_DEFINITIFS

    @property
    def est_paye(self):
        return self.statut == 'reussi'

    @property
    def est_lance(self):
        """Une collecte a été appelée et attend encore une réponse définitive."""
        return bool(self.cle_idempotence) and not self.est_definitif

    def montant_confirme(self, montant_recu):
        """Le montant annoncé par Tamo correspond-il à celui de la commande ?"""
        if montant_recu in (None, ''):
            return False
        try:
            return int(montant_recu) == int(self.montant)
        except (TypeError, ValueError):
            return False

    def appliquer_statut_tamo(self, statut_tamo, tamo_reference='', message=''):
        """Met le paiement (et ses billets) au jour d'un statut Tamo. True si quelque chose a changé.

        Règle TASA §6 : on ne repart jamais d'un statut définitif vers un statut en cours.
        """
        nouveau = STATUTS_TAMO.get((statut_tamo or '').strip().lower())
        if nouveau is None:
            return False

        if self.statut == nouveau:
            return False
        if self.statut in self.STATUTS_DEFINITIFS:
            if self.statut != 'reussi' or nouveau != 'rembourse':
                return False
        if nouveau in ('en_attente', 'en_cours') and self.statut in ('echoue', 'expire', 'annule'):
            return False  # pas de retour en arrière

        self.statut = nouveau
        if tamo_reference:
            self.tamo_reference = tamo_reference
        if message:
            self.message = message
        if nouveau == 'reussi':
            self.paye_le = timezone.now()
            self.valider_billets()
        elif nouveau == 'rembourse':
            self.billets.filter(statut='valide').update(statut='annule')
        return True

    def valider_billets(self):
        """Le paiement est confirmé : les billets passent de « en attente » à « valide »."""
        return self.billets.filter(statut='en_attente').update(statut='valide')

    def nouvelle_cle_idempotence(self):
        """Nouvelle clé seulement pour une nouvelle tentative : Tamo renvoie la transaction
        existante si on rejoue la même clé (aucun double débit)."""
        self.tentative += 1
        self.cle_idempotence = f"easy-{self.reference}-{self.tentative}"
        return self.cle_idempotence


class WebhookTamo(models.Model):
    """Journal des rappels signés reçus de TamoAPI : déduplication (event + reference) et audit."""

    evenement = models.CharField(max_length=50, verbose_name="Événement")
    tamo_reference = models.CharField(max_length=100, db_index=True, verbose_name="Référence Tamo")
    paiement = models.ForeignKey(Paiement, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='webhooks', verbose_name="Paiement")
    charge_utile = models.JSONField(default=dict, blank=True, verbose_name="Charge utile")
    signee_valide = models.BooleanField(default=False, verbose_name="Signature valide")
    traite = models.BooleanField(default=False, verbose_name="Traité")
    erreur = models.TextField(blank=True, verbose_name="Erreur éventuelle")
    recu_le = models.DateTimeField(auto_now_add=True, verbose_name="Reçu le")

    class Meta:
        verbose_name = "Webhook Tamo reçu"
        verbose_name_plural = "Webhooks Tamo reçus"
        ordering = ['-recu_le']
        constraints = [
            # Déduplication : Tamo peut renvoyer la même notification plusieurs fois
            models.UniqueConstraint(fields=['evenement', 'tamo_reference'], name='webhook_tamo_unique'),
        ]

    def __str__(self):
        return f"{self.evenement} — {self.tamo_reference}"
