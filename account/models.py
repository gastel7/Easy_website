from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.
class User(AbstractUser):
    CIVILITE =(
        ('Homme', 'Mr'),
        ('Femme', 'Mme')
    )
        
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('modérateur', 'Modérateur'),
        ('participant', 'Participant'),
        ('organisateur', 'Organisateur'),        
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, blank=True,)
    civilite = models.CharField(max_length=6, choices=CIVILITE)
    profile_picture = models.ImageField(upload_to='users/photos/', null=True, blank=True, verbose_name='Photo de profil')
    email= models.EmailField(unique=True, blank=True)
    tel = models.CharField(blank=True, null=True, max_length=30, unique=True, verbose_name='Numéro de téléphone')
    nationalite = models.CharField(max_length=100, blank=True, null=True, verbose_name='Nationalité')
    bith_date = models.DateField(blank=True, null=True, verbose_name='Date de naissance')
    adresse = models.CharField(max_length=255, blank=True, null=True, verbose_name='Adresse')


    def save(self, *args, **kwargs):
        if self.is_superuser and not self.role:
            self.role = 'admin'
        super().save(*args, **kwargs)

