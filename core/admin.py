from django.contrib import admin
from .models import Events, Sponsors, Intervenants, Commentaire, Favoris


admin.site.register(Events)
admin.site.register(Sponsors)
admin.site.register(Intervenants)
admin.site.register(Commentaire)
admin.site.register(Favoris)