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
        ('moderateur', 'Moderateur'),
        ('participant', 'Participant'),
        ('organisateur', 'Organisateur'),        
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, blank=True,)
    civilite = models.CharField(max_length=6, choices=CIVILITE)
    profile_picture = models.ImageField(upload_to='users/photos/', null=True, blank=True, verbose_name='Photo de profil')
    email= models.EmailField(unique=True, blank=True)
    tel = models.CharField(blank=True, null=True, max_length=30, unique=True, verbose_name='Numéro de téléphone')
    nationalite = models.CharField(max_length=100, blank=True, null=True, verbose_name='Nationalité')
    birth_date = models.DateField(blank=True, null=True, verbose_name='Date de naissance')
    adresse = models.CharField(max_length=255, blank=True, null=True, verbose_name='Adresse Personnelle')
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)


    def save(self, *args, **kwargs):
        if self.is_superuser and not self.role:
            self.role = 'admin'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
        # return f"{self.first_name} {self.last_name}  : son role est {self.role}"


class EasyMember(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='easy_member')
    description = models.TextField(blank=True)
    easy_role = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}"

    

class Organisateur(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='users_organisateur')
    localisation = models.CharField(max_length=255, blank=True, null=True, verbose_name='adresse de l\'organisateur')
    motivation = models.TextField(blank=True, verbose_name="Motivation de l'organisateur")
    experience = models.TextField(blank=True, verbose_name="Expérience de l'organisateur")

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}"



class Participant(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='users_participant')
    preferences_evenements = models.TextField(blank=True, null=True, verbose_name="Préférences d'événements")
    date_inscription_profil = models.DateTimeField(auto_now_add=True, verbose_name="Date d'inscription au programme")

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}"
