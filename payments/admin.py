from django.contrib import admin

from .models import Paiement, WebhookTamo


@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    list_display = ['reference', 'user', 'event', 'montant', 'devise', 'statut',
                    'operateur', 'telephone', 'tamo_reference', 'paye_le', 'created_at']
    list_filter = ['statut', 'operateur', 'devise', 'created_at']
    search_fields = ['reference', 'tamo_reference', 'tamo_identifiant', 'telephone',
                     'user__username', 'user__email', 'event__titre']
    readonly_fields = ['reference', 'tamo_reference', 'tamo_identifiant', 'cle_idempotence',
                       'tentative', 'derniere_verification', 'paye_le', 'created_at', 'updated_at']
    filter_horizontal = ['billets']
    date_hierarchy = 'created_at'

    def get_readonly_fields(self, request, obj=None):
        # Un paiement confirmé ne se modifie plus à la main
        readonly = list(super().get_readonly_fields(request, obj))
        if obj and obj.est_paye:
            readonly += ['user', 'event', 'montant', 'devise', 'statut', 'operateur', 'telephone']
        return readonly


@admin.register(WebhookTamo)
class WebhookTamoAdmin(admin.ModelAdmin):
    list_display = ['evenement', 'tamo_reference', 'paiement', 'signee_valide', 'traite', 'recu_le']
    list_filter = ['evenement', 'signee_valide', 'traite']
    search_fields = ['tamo_reference', 'paiement__reference']
    readonly_fields = ['evenement', 'tamo_reference', 'paiement', 'charge_utile',
                       'signee_valide', 'traite', 'erreur', 'recu_le']

    def has_add_permission(self, request):
        return False  # journal technique, écrit par le webhook uniquement
