from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Event(models.Model):
    CATEGORY_CHOICES = [
        ('concert', 'Concert'),
        ('conference', 'Conférence'),
        ('festival', 'Festival'),
        ('sport', 'Sport'),
        ('theatre', 'Théâtre'),
        ('autre', 'Autre'),
    ]

    STATUS_CHOICES = [
        ('brouillon', 'Brouillon'),
        ('publie', 'Publié'),
        ('archive', 'Archivé'),
    ]

    title = models.CharField(max_length=200, verbose_name='Titre')
    slug = models.SlugField(unique=True, max_length=200, blank=True, verbose_name='URL')
    short_description = models.CharField(max_length=255, blank=True, verbose_name='Résumé')
    description = models.TextField(verbose_name='Description')
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='concert', verbose_name='Catégorie')
    event_date = models.DateTimeField(verbose_name='Date de l\'événement')
    location = models.CharField(max_length=200, verbose_name='Lieu')
    venue = models.CharField(max_length=200, blank=True, verbose_name='Salle / lieu précis')
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0.00, verbose_name='Prix')
    capacity = models.PositiveIntegerField(default=0, verbose_name='Capacité')
    available_tickets = models.PositiveIntegerField(default=0, verbose_name='Tickets disponibles')
    image = models.ImageField(upload_to='events/', blank=True, null=True, verbose_name='Image')
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='organized_events',
        verbose_name='Organisateur',
    )
    is_published = models.BooleanField(default=True, verbose_name='Publié')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='publie', verbose_name='Statut')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-event_date']
        verbose_name = 'Événement'
        verbose_name_plural = 'Événements'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        if not self.available_tickets and self.capacity:
            self.available_tickets = self.capacity
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
