from django.db.models import F
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import UserTicket  # Import local à l'app tickets

@receiver(post_save, sender=UserTicket)
def decrementer_stocks_ticket(sender, instance, created, **kwargs):
    if created:
        # 1. Diminuer le stock de la catégorie (-1)
        category = instance.category
        category.quantite_disponible = F('quantite_disponible') - 1
        category.save(update_fields=['quantite_disponible'])
        
        # 2. Mettre à jour les données en mémoire et cibler l'événement
        category.refresh_from_db()
        event = category.event  # Django fait automatiquement le pont vers l'app events
        
        # 3. Diminuer le stock de l'événement global (-1)
        event.nombre_de_places = F('nombre_de_places') - 1
        event.save(update_fields=['nombre_de_places'])
