from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from account.models import EasyMember

from .forms import EventForm
from .models import Event


def index(request):
    featured_events = Event.objects.filter(is_published=True).order_by('-event_date')[:3]
    context = {'featured_events': featured_events}
    return render(request, 'core/index.html', context)


def a_propos(request):
    users = EasyMember.objects.all()
    context = {'users': users}
    return render(request, 'core/easy/a_propos.html', context)


def event_list(request):
    events = Event.objects.filter(is_published=True).order_by('event_date')
    paginator = Paginator(events, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context = {'page_obj': page_obj, 'events': page_obj.object_list}
    return render(request, 'core/event/event_list.html', context)


def event_detail(request, slug):
    event = get_object_or_404(Event, slug=slug)
    return render(request, 'core/event/event_detail.html', {'event': event})


@login_required
def event_create(request):
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES)
        if form.is_valid():
            event = form.save(commit=False)
            event.organizer = request.user
            event.save()
            messages.success(request, 'L\'événement a été créé avec succès.')
            return redirect('core:event-detail', slug=event.slug)
    else:
        form = EventForm()
    return render(request, 'core/event/event_form.html', {'form': form, 'title': 'Créer un événement'})


@login_required
def event_update(request, pk):
    event = get_object_or_404(Event, pk=pk)
    if request.user != event.organizer and not request.user.is_superuser and request.user.role != 'modérateur':
        messages.error(request, 'Vous n\'êtes pas autorisé à modifier cet événement.')
        return redirect('core:event-list')

    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, 'L\'événement a été mis à jour.')
            return redirect('core:event-detail', slug=event.slug)
    else:
        form = EventForm(instance=event)

    return render(request, 'core/event/event_form.html', {'form': form, 'event': event, 'title': 'Modifier un événement'})


@login_required
def event_delete(request, pk):
    event = get_object_or_404(Event, pk=pk)
    if request.user != event.organizer and not request.user.is_superuser and request.user.role != 'modérateur':
        messages.error(request, 'Vous n\'êtes pas autorisé à supprimer cet événement.')
        return redirect('core:event-list')

    if request.method == 'POST':
        event.delete()
        messages.success(request, 'L\'événement a été supprimé.')
        return redirect('core:event-list')

    return render(request, 'core/event/event_confirm_delete.html', {'event': event})
