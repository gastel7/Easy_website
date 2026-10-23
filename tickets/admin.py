from django.contrib import admin
from .models import TicketCategory, UserTicket


admin.site.register(TicketCategory)
admin.site.register(UserTicket)