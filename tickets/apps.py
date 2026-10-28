from django.apps import AppConfig


class TicketsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tickets'

    # NOTE : plus d'écouteur de signal. Le stock (TicketCategory.quantite_disponible et
    # Events.nombre_de_places) reste la quantité DÉCLARÉE ; le nombre vendu est calculé
    # par requête (voir core.views.detail_event et tickets.views.reserver_billet).
    # Un décrément à la création créait un double retrait et affichait « Complet » trop tôt.
