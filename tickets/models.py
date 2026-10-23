import secrets

from django.db import models
from django.db.models import Sum
from django.conf import settings
from django.core.exceptions import ValidationError


# Create your models here.

class TicketCategory(models.Model):
    """Représente une catégorie de ticket pour un événement spécifique. Chaque catégorie peut avoir un nom, un prix, un type et une quantité disponible."""
    
    TYPES_DE_TICKET = [
        ('early_bird', 'Early Bird'),
        ('standard', 'Standard'),
        ('vip', 'VIP'),
        ('vvip', 'VVIP'),
        ('gratuit', 'Gratuit'),
        ('donation', 'Donation'),
    ]

    event = models.ForeignKey('core.Events', on_delete=models.CASCADE, related_name='ticket_categories', verbose_name="Événement associé")
    nom = models.CharField(max_length=100, verbose_name="Nom du ticket")
    prix = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Prix du ticket", blank=True, null=True)
    type_de_ticket = models.CharField(max_length=20, choices=TYPES_DE_TICKET, verbose_name="Type de ticket")
    quantite_disponible = models.PositiveIntegerField(default=0, verbose_name="Quantité disponible")
    date_debut_vente = models.DateTimeField(verbose_name="Date de début de vente")
    date_fin_vente = models.DateTimeField(verbose_name="Date de fin de vente")
    

    class Meta:
        verbose_name = "Catégorie de ticket"
        verbose_name_plural = "Catégories de tickets"
        constraints = [
            # Dernier filet dans la base : la vente ne peut pas finir avant d'avoir commencé
            models.CheckConstraint(
                condition=models.Q(date_fin_vente__gt=models.F('date_debut_vente')),
                name='ticket_fin_vente_apres_debut',
                violation_error_message="La fin de la vente doit être après son début.",
            ),
        ]

    def clean(self):
        super().clean()

        erreurs = {}

        # Prix : gratuit = 0, donation = prix minimum (0 si vide), les autres types doivent avoir un prix
        if self.type_de_ticket == 'gratuit':
            self.prix = 0
        elif self.type_de_ticket == 'donation':
            self.prix = self.prix or 0
        elif self.type_de_ticket and (self.prix is None or self.prix <= 0):
            erreurs['prix'] = "Indiquez un prix supérieur à 0 pour ce type de ticket."

        if self.quantite_disponible < 1:
            erreurs['quantite_disponible'] = "La quantité doit être d'au moins 1."

        if self.date_debut_vente and self.date_fin_vente and self.date_fin_vente <= self.date_debut_vente:
            erreurs['date_fin_vente'] = "La fin de la vente doit être après son début."

        if erreurs:
            raise ValidationError(erreurs)

        # Total des places : on ne peut le vérifier que si l'événement existe déjà.
        # Dans le formulaire de l'événement, c'est le formset qui s'en charge (verifier_total = False),
        # car il additionne tous les billets envoyés en même temps.
        if self.event_id and getattr(self, 'verifier_total', True):
            total_places_evenement = self.event.nombre_de_places

            tickets_existants = TicketCategory.objects.filter(event=self.event)
            
            if self.pk:
                tickets_existants = tickets_existants.exclude(pk=self.pk)
                
            somme_tickets_existants = tickets_existants.aggregate(Sum('quantite_disponible'))['quantite_disponible__sum'] or 0

            if somme_tickets_existants + self.quantite_disponible > total_places_evenement:
                places_restantes_possibles = total_places_evenement - somme_tickets_existants
                raise ValidationError({
                    'quantite_disponible': f"Impossible d'ajouter autant de tickets. Il ne reste que {places_restantes_possibles} places disponibles sur les {total_places_evenement} de l'événement."
                })

    def __str__(self):
        return f"{self.nom} - {self.event.titre}"


class UserTicket(models.Model):
    STATUT_CHOICES = [
        ('en_attente', 'En attente de paiement'),
        ('valide', 'Valide'),
        ('scanne', 'Scanné'),
        ('annule', 'Annulé'),
    ]

    category = models.ForeignKey(TicketCategory, on_delete=models.PROTECT, related_name='user_tickets', verbose_name="Catégorie du ticket")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='my_tickets', verbose_name="Acheteur")
    code_unique = models.CharField(max_length=50, unique=True, blank=True, editable=False, verbose_name="Code du billet")
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_attente', verbose_name="Statut du billet")
    prix_achat = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False, verbose_name="Prix payé")
    reference_paiement = models.CharField(max_length=100, blank=True, verbose_name="Référence du paiement")
    date_achat = models.DateTimeField(auto_now_add=True, verbose_name="Date d'achat")
    date_scan = models.DateTimeField(null=True, blank=True, verbose_name="Date du scan")

    class Meta:
        verbose_name = "Ticket Participant"
        verbose_name_plural = "Tickets Participants"
        ordering = ['-date_achat']

    def save(self, *args, **kwargs):
        if not self.pk:
            self.prix_achat = self.category.prix or 0
        if not self.code_unique:
            self.code_unique = secrets.token_urlsafe(16)
        super().save(*args, **kwargs)

    @property
    def event(self):
        return self.category.event

    @property
    def est_utilisable(self):
        return self.statut == 'valide'

    def __str__(self):
        return f"Ticket {self.code_unique} ({self.category.nom}) - {self.user.username}"