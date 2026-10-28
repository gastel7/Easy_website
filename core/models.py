from django.conf import settings
from django.db import models
from django.conf import settings
from django.urls import reverse 
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils import timezone


class Events(models.Model):
    CATEGORIE_CHOICES = [
        ('concert', 'Concert'),
        ('theatre', 'Théâtre'),
        ('exposition', 'Exposition'),
        ('festival', 'Festival'),
        ('conference', 'Conférence'),
        ('cinema', 'Cinéma'),
        ('sport', 'Sport'),
        ('autres', 'Autres'),
    ]

    ETAT_CHOICES = [
        ('a_venir', 'À venir'),
        ('en_cours', 'En cours'),
        ('termine', 'Terminé'),
        ('annule', 'Annulé'),
    ]

    STATUT_CHOICES = [
        ('public', 'Public'),
        ('prive', 'Privé')
    ]

    organisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='events', verbose_name="Organisateur de l'événement")
    titre = models.CharField(max_length=200, verbose_name="Titre de l'événement")
    categorie = models.CharField(max_length=20, choices=CATEGORIE_CHOICES, verbose_name="Catégorie")
    etat = models.CharField(max_length=20, choices=ETAT_CHOICES, verbose_name="État de l'événement", default="a_venir")
    description = models.TextField(blank=True, verbose_name="Description de l'événement")
    lieu = models.CharField(max_length=200, blank=True, verbose_name="Lieu où va se dérouler l'événement")
    adresse = models.CharField(max_length=255, blank=True)  
    ville = models.CharField(max_length=100, blank=True)
    pays = models.CharField(max_length=100, blank=True)
    date_debut = models.DateTimeField()
    date_fin = models.DateTimeField(blank=True, null=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='public', verbose_name="Statut")


    nombre_de_vues = models.PositiveIntegerField(default=0, verbose_name="Nombre de vues")
    nombre_de_places = models.PositiveIntegerField(default=0, verbose_name="Nombre de places disponibles")
    
    nombre_de_partages = models.PositiveIntegerField(default=0, verbose_name="Nombre de partages")
    lien_de_partage = models.URLField(blank=True, max_length=500, verbose_name="Lien de partage de l'événement")

    age_minimum = models.PositiveIntegerField(default=0,verbose_name="Âge minimum requis", help_text="Laissez à 0 si l'événement est tout public")


    image_principale = models.ImageField(upload_to='images/evenements/', blank=True, null=True, verbose_name="Image principale de l'événement")
    image_2 = models.ImageField(upload_to='images/evenements/', blank=True, null=True, verbose_name="Deuxième image de l'événement")
    image_3 = models.ImageField(upload_to='images/evenements/', blank=True, null=True, verbose_name="Troisième image de l'événement")
    image_4 = models.ImageField(upload_to='images/evenements/', blank=True, null=True, verbose_name="Quatrième image de l'événement")
    image_5 = models.ImageField(upload_to='images/evenements/', blank=True, null=True, verbose_name="Cinquième image de l'événement")

    video = models.FileField(upload_to='videos/', blank=True, null=True, verbose_name="Vidéo de l'événement")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Dernière modification")


    class Meta:
        constraints = [
            # Dernier filet, directement dans la base : la fin ne peut pas être avant le début
            models.CheckConstraint(
                condition=models.Q(date_fin__isnull=True) | models.Q(date_fin__gte=models.F('date_debut')),
                name='event_date_fin_pas_avant_debut',
                violation_error_message="La date de fin ne peut pas être avant la date de début.",
            ),
        ]

    def clean(self):
        # Appelé automatiquement par le ModelForm et par l'admin
        super().clean()
        if self.date_debut and self.date_fin and self.date_fin < self.date_debut:
            raise ValidationError({'date_fin': "La date de fin ne peut pas être avant la date de début."})

    @property
    def un_seul_jour(self):
        """Vrai si la date de fin est vide, ou tombe le même jour (en heure locale) que le début."""
        if not self.date_fin:
            return True
        return timezone.localtime(self.date_debut).date() == timezone.localtime(self.date_fin).date()

    def __str__(self):
        return self.titre



    def __str__(self):
        return self.titre



# La table Commentaire permet aux utilisateurs de laisser des avis sur les événements.
class Commentaire(models.Model):
    event = models.ForeignKey(Events, on_delete=models.CASCADE, related_name='commentaires', verbose_name="Événement associé")
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='commentaires', verbose_name="Auteur du commentaire")
    avis = models.TextField(verbose_name="Contenu du commentaire")
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    note = models.PositiveIntegerField(default=0, verbose_name="Note attribuée à l'événement", validators=[MinValueValidator(0), MaxValueValidator(5)])
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Dernière modification")


    def __str__(self):
        return f"Commentaire de {self.auteur.username} sur {self.event.titre}"


# La table Favoris permet de gérer les événements favoris des utilisateurs. 
# Chaque utilisateur peut ajouter plusieurs événements à ses favoris, 
# et chaque événement peut être ajouté aux favoris par plusieurs utilisateurs. 
# La relation entre les utilisateurs et les événements est donc une relation many-to-many, 
# mais elle est implémentée ici à l'aide d'une table intermédiaire (la table Favoris) 
# afin permettre le stockages d'informations supplémentaires, comme la date d'ajout aux favoris.

class Favoris(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='favoris', verbose_name="Utilisateur")
    event = models.ForeignKey(Events, on_delete=models.CASCADE, related_name='favoris', verbose_name="Événement favori")
    date_ajout = models.DateTimeField(auto_now_add=True, verbose_name="Date d'ajout aux favoris")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Dernière modification")


    class Meta:
        unique_together = ('user', 'event')
        verbose_name = "Favori"
        verbose_name_plural = "Favoris"

    def __str__(self):
        return f"{self.user.username} a ajouté {self.event.titre} à ses favoris"


# Les sponsors de l'événement
class Sponsors(models.Model):
    event = models.ForeignKey(Events, on_delete=models.CASCADE, related_name='sponsors', verbose_name="Événement favori")
    nom_sponsor = models.CharField(max_length=100, blank=True)
    logo = models.ImageField(upload_to="images/logo_sponsor/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Dernière modification")



    def __str__(self):
        return f"{self.nom_sponsor}"


# Les artistes qui interviendront durant l'événements
class Intervenants(models.Model):
    event = models.ForeignKey(Events, on_delete=models.CASCADE, related_name='intervenants', verbose_name="Événement favori")
    nom_intervenant = models.CharField(max_length=100, blank=True)
    photo = models.ImageField(upload_to="images/photo_intervenant/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Dernière modification")


    def __str__(self):
        return f"{self.nom_intervenant}"


# Ngoyo : MBC Company arrêt Cowbell