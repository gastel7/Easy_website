from django.db.models import F, Q, ProtectedError, Count, Max
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.db import transaction
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.contrib.auth.views import redirect_to_login
from django.utils import timezone
from django.utils.dateparse import parse_date

from datetime import datetime, time, timedelta

 
from .models import Events, Favoris


from .forms import EventForm
from .models import Events, Sponsors, Intervenants, Favoris, Commentaire

from account.models import EasyMember
from tickets.forms import TicketFormSet
from tickets.models import UserTicket


# Create your views here.
def index(request):
    user = request.user

    if user.is_superuser or getattr(user, 'role', None) == 'modérateur':
        evenements = Events.objects.all()
    elif user.is_authenticated:
        evenements = Events.objects.filter(Q(statut='public') | Q(statut='prive', organisateur=user))
    else:
        evenements = Events.objects.filter(statut='public')

    context = {
        'events': evenements.order_by('-created_at')[:2]
    }
    return render(request, 'core/index.html', context)

@login_required
def add_event(request):
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES)
        ticket_formset = TicketFormSet(request.POST)
 
        form_ok = form.is_valid()
        # Les billets sont vérifiés par rapport au nombre de places qui vient d'être envoyé
        ticket_formset.places_max = form.cleaned_data.get('nombre_de_places')
 
        if form_ok and ticket_formset.is_valid():
            # Tout ou rien : si l'enregistrement des billets échoue, l'événement n'est pas créé
            with transaction.atomic():
                event = form.save(commit=False)
                event.organisateur = request.user
                event.save()
 
                ticket_formset.instance = event
                ticket_formset.save()
            return render(request, 'core/easy/events/partials/event_success.html', {'event': event})
    else:
        form = EventForm()
        ticket_formset = TicketFormSet()
 
    return render(request, 'core/easy/events/new_event.html', {'form': form, 'ticket_formset': ticket_formset})
 
@login_required
def edit_event(request, event_id):
    event = get_object_or_404(Events, id=event_id)

    peut_gerer = request.user.is_superuser or getattr(request.user, 'role', None) == 'modérateur' or request.user == event.organisateur
    if not peut_gerer:
        raise PermissionDenied

    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES, instance=event)
        ticket_formset = TicketFormSet(request.POST, instance=event)
 
        form_ok = form.is_valid()
        ticket_formset.places_max = form.cleaned_data.get('nombre_de_places')
 
        if form_ok and ticket_formset.is_valid():
            with transaction.atomic():
                form.save()
                ticket_formset.save()
            return redirect("core:events-list")
    else:
        form = EventForm(instance=event)
        ticket_formset = TicketFormSet(instance=event)
 
    return render(request, 'core/easy/events/edit_event.html', {'form': form, 'ticket_formset': ticket_formset, 'event': event})
 
 
 



def evenements_visibles(user):
    """Les événements que cet utilisateur a le droit de voir."""
    if user.is_superuser or getattr(user, 'role', None) == 'modérateur':
        return Events.objects.all()
    if user.is_authenticated:
        return Events.objects.filter(Q(statut='public') | Q(statut='prive', organisateur=user))
    return Events.objects.filter(statut='public')



PERIODES = ('aujourdhui', 'weekend', 'semaine_prochaine', 'mois')
 
 
def intervalle_periode(periode):
    """Début et fin (heure locale) de la période demandée."""
    debut_jour = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
 
    if periode == 'aujourdhui':
        return debut_jour, debut_jour + timedelta(days=1)
 
    if periode == 'weekend':
        # Du samedi 0h au lundi 0h. Si on est dimanche, le week-end a commencé hier.
        jours = -1 if debut_jour.weekday() == 6 else 5 - debut_jour.weekday()
        samedi = debut_jour + timedelta(days=jours)
        return samedi, samedi + timedelta(days=2)
 
    if periode == 'semaine_prochaine':
        lundi = debut_jour + timedelta(days=7 - debut_jour.weekday())
        return lundi, lundi + timedelta(days=7)
 
    # 'mois' : d'aujourd'hui à la fin du mois
    debut_mois_suivant = (debut_jour.replace(day=1) + timedelta(days=32)).replace(day=1)
    return debut_jour, debut_mois_suivant
 
 
def se_deroule_entre(evenements, debut, fin):
    """Les événements qui ont lieu (en partie) dans [debut, fin[, y compris ceux sur plusieurs jours."""
    return evenements.filter(
        Q(date_debut__lt=fin),
        Q(date_fin__gte=debut) | Q(date_fin__isnull=True, date_debut__gte=debut),
    )
 
 
def ids_favoris(user):
    if not user.is_authenticated:
        return set()
    return set(Favoris.objects.filter(user=user).values_list('event_id', flat=True))
 
 
def events_list(request):
    get = request.GET
    q = get.get('q', '').strip()[:100]
    ville = get.get('ville', '').strip()[:100]
    jour = get.get('date', '').strip()
    periode = get.get('periode', '')
    categorie = get.get('categorie', '')
    tri = get.get('tri', 'recents')
    organisateur = get.get('organisateur', '')
 
    # prix_max = le prix du billet le plus cher : > 0 = événement payant, 0 = gratuit, vide = pas de billet
    evenements = evenements_visibles(request.user).annotate(prix_max=Max('ticket_categories__prix'))
 
    if q:
        evenements = evenements.filter(
            Q(titre__icontains=q) | Q(lieu__icontains=q) | Q(ville__icontains=q)
            | Q(intervenants__nom_intervenant__icontains=q)
        ).distinct()
 
    if ville:
        evenements = evenements.filter(ville__icontains=ville)
 
    if categorie in dict(Events.CATEGORIE_CHOICES):
        evenements = evenements.filter(categorie=categorie)
    else:
        categorie = ''
 
    if organisateur.isdigit():
        evenements = evenements.filter(organisateur_id=int(organisateur))
    else:
        organisateur = ''
 
    if periode in PERIODES:
        evenements = se_deroule_entre(evenements, *intervalle_periode(periode))
    else:
        periode = ''
 
    try:
        un_jour = parse_date(jour) if jour else None
    except ValueError:
        un_jour = None
    if un_jour:
        debut = timezone.make_aware(datetime.combine(un_jour, time.min))
        evenements = se_deroule_entre(evenements, debut, debut + timedelta(days=1))
    else:
        jour = ''
 
    evenements = evenements.order_by('date_debut' if tri == 'date' else '-created_at', '-id')
    page_obj = Paginator(evenements, 12).get_page(get.get('page'))
 
    filtres_actifs = bool(q or ville or jour or periode or categorie or organisateur)
    maintenant = timezone.now()
    a_venir = evenements_visibles(request.user).filter(statut='public', date_debut__gte=maintenant)
    a_venir = a_venir.annotate(prix_max=Max('ticket_categories__prix'))
 
    # « À ne pas manquer » : les plus mis en favoris, puis les plus vus (seulement sans filtre, page 1)
    a_la_une = []
    if not filtres_actifs and page_obj.number == 1:
        a_la_une = a_venir.annotate(nb_favoris=Count('favoris', distinct=True)).order_by('-nb_favoris', '-nombre_de_vues', 'date_debut')[:6]
 
    context = {
        'events': page_obj,
        'page_obj': page_obj,
        'nb_resultats': page_obj.paginator.count,
        'categories': Events.CATEGORIE_CHOICES,
        'categorie': categorie,
        'periode': periode,
        'q': q,
        'ville': ville,
        'jour': jour,
        'tri': tri,
        'a_la_une': a_la_une,
        'ids_favoris': ids_favoris(request.user),
        'vue': 'liste' if get.get('vue') == 'liste' else 'grille',
        'base_template': 'account/profile/espace/base_espace.html' if request.user.is_authenticated else 'core/base.html',
    }
    return render(request, 'core/easy/events/events_list.html', context)


 
def detail_event(request, event_id):
    event = get_object_or_404(Events.objects.select_related('organisateur'), id=event_id)
    user = request.user
    peut_gerer = user.is_superuser or getattr(user, 'role', None) == 'modérateur' or user == event.organisateur
 
    if event.statut == 'prive' and not peut_gerer:
        raise Http404
 
    # Une vue par session, sans compter la gestion de l'événement
    cle_session = f'event_vu_{event.id}'
    if not peut_gerer and not request.session.get(cle_session):
        Events.objects.filter(pk=event.pk).update(nombre_de_vues=F('nombre_de_vues') + 1)
        request.session[cle_session] = True
        event.refresh_from_db(fields=['nombre_de_vues'])
 
    categories = list(event.ticket_categories.annotate(
        vendus=Count('user_tickets', filter=~Q(user_tickets__statut='annule')),
    ).annotate(
        restantes=F('quantite_disponible') - F('vendus'),
    ).order_by('id'))
 
    # Pour chaque billet : peut-on l'acheter maintenant ?
    maintenant = timezone.now()
    for categorie in categories:
        categorie.restantes = max(categorie.restantes, 0)
        categorie.max_achat = min(categorie.restantes, 10)
        if categorie.restantes == 0:
            categorie.etat_vente = 'complet'
        elif maintenant < categorie.date_debut_vente:
            categorie.etat_vente = 'bientot'
        elif maintenant > categorie.date_fin_vente:
            categorie.etat_vente = 'termine'
        else:
            categorie.etat_vente = 'ouvert'
 
    places_vendues = sum(categorie.vendus for categorie in categories)
    places_restantes = event.nombre_de_places - places_vendues
 
    similaires = (
        evenements_visibles(user)
        .filter(statut='public', categorie=event.categorie, date_debut__gte=maintenant)
        .exclude(pk=event.pk)
        .annotate(prix_max=Max('ticket_categories__prix'))
        .order_by('date_debut')[:4]
    )
 
    context = {
        'event': event,
        'categories': categories,
        'places_restantes': places_restantes,
        'nb_interesses': event.favoris.count(),
        'nb_evenements_organisateur': Events.objects.filter(organisateur=event.organisateur, statut='public').count(),
        'intervenants': event.intervenants.exclude(nom_intervenant=''),
        'galerie': [image for image in (event.image_2, event.image_3, event.image_4, event.image_5) if image],
        'adresse_carte': ', '.join(filter(None, [event.lieu, event.adresse, event.ville, event.pays])),
        'url_partage': request.build_absolute_uri(),
        'similaires': similaires,
        'ids_favoris': ids_favoris(user),
        'login_url': redirect_to_login(request.get_full_path()).url,
        'base_template': 'account/profile/espace/base_espace.html' if user.is_authenticated else 'core/base.html',
    }
    return render(request, 'core/easy/events/detail_event.html', context)
 
 
@require_POST
def toggle_favori(request, event_id):
    """Ajoute ou retire l'événement des favoris. Répond en JSON (appelé par favoris.js)."""
    if not request.user.is_authenticated:
        return JsonResponse({'login_url': redirect_to_login(request.META.get('HTTP_REFERER') or '/').url}, status=401)
 
    event = get_object_or_404(evenements_visibles(request.user), pk=event_id)
    favori, cree = Favoris.objects.get_or_create(user=request.user, event=event)
    if not cree:
        favori.delete()
 
    return JsonResponse({'favori': cree})



@login_required
@require_POST
def delete_event(request, event_id):
    event = get_object_or_404(Events, id=event_id)

    peut_gerer = request.user.is_superuser or getattr(request.user, 'role', None) == 'modérateur' or request.user == event.organisateur
    if not peut_gerer:
        raise PermissionDenied

    titre = event.titre

    if UserTicket.objects.filter(category__event=event).exists():
        messages.error(
            request,
            f"L'événement « {titre} » ne peut pas être supprimé, car des billets ont déjà été réservés. "
            "Vous pouvez le passer en « annulé »."
        )
        return redirect('core:events-list')

    try:
        event.delete()
    except ProtectedError:
        messages.error(request, f"L'événement « {titre} » ne peut pas être supprimé pour le moment.")
        return redirect('core:events-list')

    messages.success(request, f"L'événement « {titre} » a bien été supprimé.")
    return redirect('core:events-list')



 
 
def a_propos(request):
    # Liste simple de tous tes membres
    users = EasyMember.objects.all()[:5]
 
    context = {
        'users': users
    }
 
    return render(request, 'core/easy/a_propos.html', context)

def contact(request):
    return render(request, 'core/easy/contact.html')


def faq(request):
    return render(request, 'core/easy/faq.html')
