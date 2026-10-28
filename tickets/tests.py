from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from account.models import User
from core.models import Events
from payments.models import Paiement

from .models import TicketCategory, UserTicket


def creer_utilisateur(nom, numero, email):
    return User.objects.create_user(
        username=nom, email=email, password='pass-1234', civilite='Homme', tel=numero)


class BaseBilletterie(TestCase):
    def setUp(self):
        self.organisateur = creer_utilisateur('orga', '+242061111111', 'orga@tests.cg')
        self.acheteur = creer_utilisateur('acheteur', '+242062222222', 'acheteur@tests.cg')
        self.intrus = creer_utilisateur('intrus', '+242063333333', 'intrus@tests.cg')

        debut = timezone.now() + timedelta(days=5)
        self.evenement = Events.objects.create(
            organisateur=self.organisateur, titre='Concert', categorie='concert',
            date_debut=debut, nombre_de_places=10, statut='public')
        self.categorie_payante = TicketCategory.objects.create(
            event=self.evenement, nom='Standard', prix=1000, type_de_ticket='standard',
            quantite_disponible=10,
            date_debut_vente=timezone.now() - timedelta(days=1), date_fin_vente=debut)

    def reserver(self, quantite, categorie=None, user=None):
        categorie = categorie or self.categorie_payante
        user = user or self.acheteur
        self.client.force_login(user)
        return self.client.post(reverse('tickets:reserver', args=[self.evenement.id]),
                                {f'quantite_{categorie.id}': str(quantite)})


class ReservationTests(BaseBilletterie):

    def test_reservation_payante_cree_un_paiement_et_redirige(self):
        reponse = self.reserver(2)

        self.assertEqual(reponse.status_code, 302)
        paiement = Paiement.objects.get()
        self.assertEqual(reponse.url, reverse('payments:page', args=[paiement.reference]))
        self.assertEqual(paiement.montant, 2000)
        self.assertEqual(paiement.statut, 'en_attente')
        self.assertEqual(paiement.billets.count(), 2)
        self.assertEqual(UserTicket.objects.filter(statut='en_attente').count(), 2)

    def test_reservation_gratuite_sans_paiement(self):
        gratuite = TicketCategory.objects.create(
            event=self.evenement, nom='Gratuit', prix=0, type_de_ticket='gratuit',
            quantite_disponible=10,
            date_debut_vente=timezone.now() - timedelta(days=1),
            date_fin_vente=self.evenement.date_debut)

        reponse = self.reserver(1, categorie=gratuite)

        self.assertEqual(reponse.status_code, 302)
        self.assertNotIn('paiements', reponse.url)
        self.assertEqual(Paiement.objects.count(), 0)
        self.assertEqual(UserTicket.objects.filter(statut='valide').count(), 1)

    def test_stock_declare_non_decremente_a_la_creation(self):
        """Le stock reste la quantité déclarée : le nombre vendu est calculé par requête.

        (Regression : l'ancien signal retirait déjà 1 au moment de la création, et les vues
        retiraient encore les billets vendus → « Complet » affiché trop tôt.)"""
        self.reserver(3)

        self.categorie_payante.refresh_from_db()
        self.evenement.refresh_from_db()
        self.assertEqual(self.categorie_payante.quantite_disponible, 10)
        self.assertEqual(self.evenement.nombre_de_places, 10)

        reponse = self.client.get(reverse('core:detail-event', args=[self.evenement.id]))
        categorie = next(c for c in reponse.context['categories'] if c.id == self.categorie_payante.id)
        self.assertEqual(categorie.restantes, 7)
        self.assertEqual(reponse.context['places_restantes'], 7)

    def test_stock_epuise_refuse_la_commande(self):
        self.reserver(3)
        reponse = self.reserver(10)

        self.assertEqual(UserTicket.objects.count(), 3)  # rien n'a été créé
        self.assertEqual(Paiement.objects.count(), 1)
        self.assertEqual(reponse.status_code, 302)       # retour sur la page de l'événement
        self.assertContains(self.client.get(reponse.url), 'Il ne reste que')

    def test_limite_de_billets_par_commande(self):
        reponse = self.reserver(11)
        self.assertEqual(UserTicket.objects.count(), 0)
        self.assertEqual(reponse.status_code, 302)
        self.assertContains(self.client.get(reponse.url), '10 billets au maximum')

    def test_reservation_anonyme_redirige_vers_la_connexion(self):
        self.client.logout()
        reponse = self.client.post(reverse('tickets:reserver', args=[self.evenement.id]),
                                   {f'quantite_{self.categorie_payante.id}': '1'})
        self.assertEqual(reponse.status_code, 302)
        self.assertIn('login', reponse.url)
        self.assertEqual(UserTicket.objects.count(), 0)


class QrCodeTests(BaseBilletterie):

    def billet_valide(self):
        billet = UserTicket.objects.create(
            category=self.categorie_payante, user=self.acheteur, statut='valide')
        return billet

    def test_qr_code_reserve_au_proprietaire(self):
        billet = self.billet_valide()
        url = reverse('tickets:qr-code', args=[billet.id])

        self.client.force_login(self.intrus)
        self.assertEqual(self.client.get(url).status_code, 404)

        self.client.force_login(self.acheteur)
        reponse = self.client.get(url)
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, 'data:image/png;base64')
        self.assertContains(reponse, billet.code_unique)

    def test_qr_code_indisponible_tant_que_non_paye(self):
        billet = UserTicket.objects.create(
            category=self.categorie_payante, user=self.acheteur, statut='en_attente')
        self.client.force_login(self.acheteur)
        reponse = self.client.get(reverse('tickets:qr-code', args=[billet.id]))
        self.assertEqual(reponse.status_code, 302)
        self.assertIn('espace/billets', reponse.url)

    def test_page_de_verification_publique(self):
        billet = self.billet_valide()
        url = reverse('tickets:verifier', args=[billet.code_unique])

        reponse = self.client.get(url)  # sans connexion : c'est le lecteur à l'entrée
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, 'Billet valide')
        self.assertContains(reponse, self.evenement.titre)

    def test_page_de_verification_code_inconnu(self):
        self.assertEqual(self.client.get(reverse('tickets:verifier', args=['inconnu'])).status_code, 404)
