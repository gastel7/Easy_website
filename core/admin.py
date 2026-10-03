from django.contrib import admin

from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'event_date', 'location', 'price', 'is_published')
    list_filter = ('category', 'is_published', 'status')
    search_fields = ('title', 'location', 'description')
    prepopulated_fields = {'slug': ('title',)}
