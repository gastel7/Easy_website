# core/context_processors.py
from .models import Events

def banner_events(request):
    return {'banner_events': Events.objects.all()[:2]}