import hashlib
import hmac
import json
from datetime import timedelta
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from account.models import User
from core.models import Events
from tickets.models import TicketCategory, UserTicket

from . import tamo
from .models import Paiement, WebhookTamo
from .views import _donnees_depuis_reponse

TAMO_TEST = {
    'API_BASE': 'https://tamoapi.test/api/v1',
    'API_TOKEN': 'tok_test_public',
    'API_SECRET': 'secret_de_test',
    'WEBHOOK_SECRET': 'whsec_de_test',
    'PRODUCT_ID': '8e2616a9-0842-4e4a-898c-dfb77338fe1c',
    'DEVISE': 'XAF',
}

CORPS_EXEMPLE = (
    '{"product_id":"8e2616a9-0842-4e4a-898c-dfb77338fe1c","operator_code":"MTN_CG",'
    '"amount":5000,"phone_number":"+242060000000","merchant_reference":"CMD-10045"}'
)


def creer_utilisateur(nom, numero, email):
    return User.objects.create_user(
        username=nom, email=email, password='pass-1234', civilite='Homme', tel=numero)


def creer_evenement(organisateur, places=50, prix=1000):
    debut = timezone.now() + timedelta(days=5)
    evenement = Events.objects.create(
        organisateur=organisateur, titre='Concert de test', categorie='concert',
        date_debut=debut, nombre_de_places=places, statut='public', lieu='Brazzaville')
    categorie = TicketCategory.objects.create(
        event=evenement, nom='Standard', prix=prix, type_de_ticket='standard',
        quantite_disponible=places,
        date_debut_vente=timezone.now() - timedelta(days=1),
        date_fin_vente=debut,
    )
    return evenement, categorie


# ---------------------------------------------------------------------------
# Signature v2 et webhooks
# ---------------------------------------------------------------------------

@override_settings(TAMO=TAMO_TEST)
class SignatureTests(TestCase):

    def test_signature_v2_reproduit_la_chaine_de_la_documentation(self):
        """hex(HMAC-SHA256(METHOD\\nURI\\ntimestamp\\nnonce\\nidempotency\\ncorps, api_secret))"""
        chaine = '\n'.join(['POST', '/api/v1/collections', '1767225600',
                            '9f86d081884c7d659a2feaa0c55ad015', 'collecte-CMD-10045', CORPS_EXEMPLE])
        attendue = hmac.new(b'secret_de_test', chaine.encode('utf-8'), hashlib.sha256).hexdigest()

        obtenue = tamo.signature_v2('POST', '/api/v1/collections', '1767225600',
                                    '9f86d081884c7d659a2feaa0c55ad015',
                                    'collecte-CMD-10045', CORPS_EXEMPLE, 'secret_de_test')
        self.assertEqual(obtenue, attendue)

    def test_entetes_ecriture_portent_tous_les_champs_requis(self):
        url = f"{TAMO_TEST['API_BASE']}{tamo.CHEMIN_COLLECTE}"
        corps = tamo.serialiser({'amount': 5000})
        entetes = tamo._entetes_ecriture('POST', url, 'easy-EASY-abc-1', corps)

        for champ in ('X-API-Token', 'Idempotency-Key', 'X-Signature-Version',
                      'X-Timestamp', 'X-Nonce', 'X-Signature'):
            self.assertIn(champ, entetes)
        self.assertEqual(entetes['X-Signature-Version'], '2')
        self.assertEqual(entetes['X-API-Token'], TAMO_TEST['API_TOKEN'])
        self.assertGreaterEqual(len(entetes['X-Nonce']), 16)

        # La signature doit se recalculer à partir des en-têtes envoyés
        chaine = '\n'.join(['POST', tamo._uri(url), entetes['X-Timestamp'], entetes['X-Nonce'],
                            'easy-EASY-abc-1', corps])
        attendue = hmac.new(TAMO_TEST['API_SECRET'].encode(), chaine.encode(), hashlib.sha256).hexdigest()
        self.assertEqual(entetes['X-Signature'], attendue)

    @mock.patch('payments.tamo.requests.request')
    def test_creation_collecte_signe_et_envoie_le_meme_corps_sur_la_route_documentee(self, requete):
        reponse = mock.Mock(status_code=201, headers={}, text='{"data":{}}')
        reponse.json.return_value = {'data': {'reference': 'TAMOC-1', 'id': 'uuid-1'}}
        requete.return_value = reponse

        tamo.creer_collecte(5000, '+242060000000', 'MTN_CG', 'CMD-10045',
                            idempotency_key='collecte-CMD-10045')

        args, kwargs = requete.call_args
        self.assertEqual(args, ('POST', 'https://tamoapi.test/api/v1/collections'))
        corps = kwargs['data'].decode('utf-8')
        self.assertEqual(json.loads(corps), json.loads(CORPS_EXEMPLE))
        self.assertEqual(kwargs['headers']['X-Signature-Version'], '2')
        self.assertEqual(kwargs['headers']['Idempotency-Key'], 'collecte-CMD-10045')
        signature = tamo.signature_v2(
            'POST', '/api/v1/collections', kwargs['headers']['X-Timestamp'],
            kwargs['headers']['X-Nonce'], 'collecte-CMD-10045',
            corps, TAMO_TEST['API_SECRET'])
        self.assertEqual(kwargs['headers']['X-Signature'], signature)

    @mock.patch('payments.tamo.requests.request')
    def test_statut_utilise_le_chemin_documente_et_encode_la_reference(self, requete):
        reponse = mock.Mock(status_code=200, headers={}, text='{"data":{"status":"pending"}}')
        reponse.json.return_value = {'data': {'reference': 'TAMOC/1', 'status': 'pending'}}
        requete.return_value = reponse

        tamo.interroger_statut('TAMOC/1')

        self.assertEqual(requete.call_args.args,
                         ('GET', 'https://tamoapi.test/api/v1/collections/status/TAMOC%2F1'))
        self.assertEqual(requete.call_args.kwargs['headers']['X-API-Token'], TAMO_TEST['API_TOKEN'])

    def test_ecriture_exige_une_cle_idempotence_de_1_a_190_caracteres(self):
        url = f"{TAMO_TEST['API_BASE']}{tamo.CHEMIN_COLLECTE}"
        for cle in ('', None, 'k' * 191):
            with self.subTest(cle=cle):
                with self.assertRaises(tamo.TamoError):
                    tamo._appeler('POST', url, payload={}, idempotency_key=cle)

    def test_collecte_refuse_un_montant_hors_format_tamo(self):
        for montant in (9, 500001, 10.5):
            with self.subTest(montant=montant):
                with self.assertRaises(tamo.TamoError) as erreur:
                    tamo.creer_collecte(montant, '+242060000000', 'MTN_CG', 'CMD',
                                        idempotency_key='cle-CMD')
                self.assertEqual(erreur.exception.status_code, 422)

    def test_serialisation_stable_et_signee_brute(self):
        payload = {'amount': 5000, 'phone_number': '+242068409872'}
        corps = tamo.serialiser(payload)
        self.assertEqual(corps, tamo.serialiser(payload))  # une seule écriture, la même à chaque fois
        self.assertIn('"amount":5000', corps)

    def test_verification_signature_webhook(self):
        corps = json.dumps({'event': 'collection.success', 'data': {'reference': 'TAMOC-1'}}).encode()
        bonne = tamo.signature_webhook(corps, TAMO_TEST['WEBHOOK_SECRET'])

        self.assertTrue(tamo.verifier_signature_webhook(corps, bonne))
        self.assertFalse(tamo.verifier_signature_webhook(corps, '0' * len(bonne)))
        self.assertFalse(tamo.verifier_signature_webhook(corps, bonne[:-1]))  # longueur différente
        self.assertFalse(tamo.verifier_signature_webhook(corps, ''))         # absente
        self.assertFalse(tamo.verifier_signature_webhook(corps, bonne, secret=''))  # secret absent

    def test_succes_sans_montant_ne_confirme_pas_le_paiement(self):
        paiement = Paiement(montant=5000)
        self.assertFalse(paiement.montant_confirme(None))
        self.assertFalse(paiement.montant_confirme(''))
        self.assertTrue(paiement.montant_confirme(5000))

    def test_montant_de_reponse_detaillee_est_extrait_des_montants_demandes(self):
        reponse = _donnees_depuis_reponse({
            'reference': 'TAMOC-1',
            'statut': 'success',
            'amounts': {'requested': 5000, 'fee': 100, 'net': 4900},
        })
        self.assertEqual(reponse['amount'], 5000)


# ---------------------------------------------------------------------------
# Webhook reçu par le serveur
# ---------------------------------------------------------------------------

@override_settings(TAMO=TAMO_TEST)
class WebhookTests(TestCase):

    def setUp(self):
        self.organisateur = creer_utilisateur('orga', '+242061111111', 'orga@test.cg')
        self.acheteur = creer_utilisateur('client', '+242062222222', 'client@test.cg')
        self.evenement, self.categorie = creer_evenement(self.organisateur, places=10, prix=5000)
        self.billet = UserTicket.objects.create(
            category=self.categorie, user=self.acheteur, statut='en_attente')
        self.paiement = Paiement.objects.create(
            user=self.acheteur, event=self.evenement, montant=5000)
        self.paiement.billets.set([self.billet])
        self.url = reverse('payments:webhook')

    def _payload(self, statut='success', montant=5000, event=None, reference='TAMOC-OP7Y-261002-M8XFKU'):
        event = event or f'collection.{statut}'
        return {
            'event': event,
            'timestamp': '2026-10-02T10:29:12.000000Z',
            'data': {
                'reference': reference,
                'merchant_reference': self.paiement.reference,
                'type': 'collection',
                'status': statut,
                'amount': montant,
                'currency': 'XAF',
                'phone_number': '+242060000000',
                'operator': 'MTN_CG',
            },
        }

    def _envoyer(self, payload, secret=TAMO_TEST['WEBHOOK_SECRET']):
        corps = json.dumps(payload).encode('utf-8')
        signature = tamo.signature_webhook(corps, secret)
        return self.client.post(self.url, data=corps, content_type='application/json',
                                HTTP_X_WEBHOOK_SIGNATURE=signature)

    def test_webhook_invalide_rejete(self):
        payload = self._payload()
        corps = json.dumps(payload).encode()
        reponse = self.client.post(self.url, data=corps, content_type='application/json',
                                   HTTP_X_WEBHOOK_SIGNATURE='a' * 64)
        self.assertEqual(reponse.status_code, 401)
        self.billet.refresh_from_db()
        self.assertEqual(self.billet.statut, 'en_attente')

    def test_webhook_success_valide_les_billets(self):
        reponse = self._envoyer(self._payload())
        self.assertEqual(reponse.status_code, 200)

        self.paiement.refresh_from_db()
        self.billet.refresh_from_db()
        self.assertEqual(self.paiement.statut, 'reussi')
        self.assertIsNotNone(self.paiement.paye_le)
        self.assertEqual(self.billet.statut, 'valide')
        self.assertEqual(WebhookTamo.objects.count(), 1)

    def test_webhook_en_double_est_deduplique(self):
        payload = self._payload()
        self.assertEqual(self._envoyer(payload).status_code, 200)
        self.assertEqual(self._envoyer(payload).status_code, 200)  # renvoi de Tamo

        self.assertEqual(WebhookTamo.objects.count(), 1)
        self.assertEqual(UserTicket.objects.filter(statut='valide').count(), 1)

    def test_webhook_montant_different_ne_valide_pas(self):
        reponse = self._envoyer(self._payload(statut='success', montant=4990))
        self.assertEqual(reponse.status_code, 200)

        self.paiement.refresh_from_db()
        self.billet.refresh_from_db()
        self.assertNotEqual(self.paiement.statut, 'reussi')
        self.assertEqual(self.billet.statut, 'en_attente')

    def test_webhook_ne_retourne_jamais_en_arriere(self):
        """Un statut définitif ne revient pas à un statut en cours (doc TASA §6)."""
        self._envoyer(self._payload(statut='success'))
        self._envoyer(self._payload(statut='pending'))

        self.paiement.refresh_from_db()
        self.assertEqual(self.paiement.statut, 'reussi')
        self.assertEqual(UserTicket.objects.filter(statut='valide').count(), 1)

    def test_webhook_failed_conserve_les_billets_en_attente(self):
        self._envoyer(self._payload(statut='failed'))
        self.paiement.refresh_from_db()
        self.billet.refresh_from_db()
        self.assertEqual(self.paiement.statut, 'echoue')
        self.assertEqual(self.billet.statut, 'en_attente')

    def test_webhook_refunded_annule_les_billets_deja_valides(self):
        self._envoyer(self._payload(statut='success'))
        self._envoyer(self._payload(statut='refunded'))

        self.paiement.refresh_from_db()
        self.billet.refresh_from_db()
        self.assertEqual(self.paiement.statut, 'rembourse')
        self.assertEqual(self.billet.statut, 'annule')

    def test_webhook_pour_un_autre_paiement_ignore(self):
        payload = self._payload()
        payload['data']['merchant_reference'] = 'EASY-autre-reference'
        payload['data']['reference'] = 'TAMOC-AUTRE'
        self._envoyer(payload)

        self.paiement.refresh_from_db()
        self.assertNotEqual(self.paiement.statut, 'reussi')

    def test_webhook_test_repond_200(self):
        reponse = self._envoyer({'event': 'webhook.test', 'timestamp': 'x', 'data': {'amount': 0}})
        self.assertEqual(reponse.status_code, 200)

    def test_evenement_de_transaction_sans_reference_est_refuse(self):
        reponse = self._envoyer({
            'event': 'collection.pending',
            'timestamp': '2026-10-02T10:29:12.000000Z',
            'data': {'status': 'pending'},
        })
        self.assertEqual(reponse.status_code, 400)

    def test_evenement_et_statut_webhook_doivent_correspondre(self):
        payload = self._payload(statut='pending', event='collection.success')
        reponse = self._envoyer(payload)
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(WebhookTamo.objects.count(), 0)


# ---------------------------------------------------------------------------
# Vues de paiement
# ---------------------------------------------------------------------------

@override_settings(TAMO=TAMO_TEST)
class VuesPaiementTests(TestCase):

    def setUp(self):
        self.organisateur = creer_utilisateur('orga2', '+242063333333', 'orga2@test.cg')
        self.acheteur = creer_utilisateur('client2', '+242064444444', 'client2@test.cg')
        self.intrus = creer_utilisateur('intrus', '+242065555555', 'intrus@test.cg')
        self.evenement, self.categorie = creer_evenement(self.organisateur, places=10, prix=5000)
        self.billet = UserTicket.objects.create(
            category=self.categorie, user=self.acheteur, statut='en_attente')
        self.paiement = Paiement.objects.create(
            user=self.acheteur, event=self.evenement, montant=5000)
        self.paiement.billets.set([self.billet])

    def _url(self, nom):
        return reverse(nom, args=[self.paiement.reference])

    def test_page_paiement_reservee_au_proprietaire(self):
        self.client.force_login(self.intrus)
        self.assertEqual(self.client.get(self._url('payments:page')).status_code, 404)

        self.client.force_login(self.acheteur)
        reponse = self.client.get(self._url('payments:page'))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, self.paiement.reference)
        self.assertContains(reponse, 'Numéro Mobile Money')

    @mock.patch('payments.tamo.creer_collecte')
    def test_lancer_collecte_passe_en_cours_en_reutilisant_la_cle(self, creer):
        creer.return_value = {'reference': 'TAMOC-1', 'identifiant': 'uuid-1',
                              'statut': 'pending', 'charge': {}}
        self.client.force_login(self.acheteur)

        donnees = {'telephone': '068409872', 'operateur': ''}
        premiere = self.client.post(self._url('payments:lancer'), donnees,
                                    HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(premiere.status_code, 200, premiere.content)

        self.paiement.refresh_from_db()
        self.assertEqual(self.paiement.statut, 'en_cours')
        self.assertEqual(self.paiement.telephone, '+242068409872')  # normalisé
        self.assertEqual(self.paiement.operateur, 'MTN_CG')         # déduit du +242
        self.assertEqual(self.paiement.tamo_reference, 'TAMOC-1')
        cle = self.paiement.cle_idempotence
        self.assertTrue(cle)

        # Rejeu de la même opération : même clé d'idempotence (aucun double débit possible)
        self.client.post(self._url('payments:lancer'), donnees,
                         HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.paiement.refresh_from_db()
        self.assertEqual(self.paiement.cle_idempotence, cle)
        self.assertEqual(self.paiement.tentative, 1)

        kwargs = creer.call_args.kwargs
        self.assertEqual(kwargs['idempotency_key'], cle)
        self.assertEqual(kwargs['merchant_reference'], self.paiement.reference)
        self.assertEqual(kwargs['montant'], 5000)

    @mock.patch('payments.tamo.creer_collecte')
    def test_rejeu_avec_un_numero_different_est_refuse(self, creer):
        creer.return_value = {'reference': 'TAMOC-1', 'identifiant': 'uuid-1',
                              'statut': 'pending', 'charge': {}}
        self.client.force_login(self.acheteur)
        premiere = self.client.post(
            self._url('payments:lancer'),
            {'telephone': '068409872', 'operateur': ''},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(premiere.status_code, 200)

        changement = self.client.post(
            self._url('payments:lancer'),
            {'telephone': '+242061234567', 'operateur': 'MTN_CG'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(changement.status_code, 409)
        self.assertEqual(creer.call_count, 1)

        self.paiement.refresh_from_db()
        self.assertEqual(self.paiement.telephone, '+242068409872')

    @mock.patch('payments.tamo.creer_collecte')
    def test_lancer_collecte_erreur_4xx_remonte_le_message(self, creer):
        creer.side_effect = tamo.TamoError('Erreur Tamo (400) : numéro invalide', status_code=400)
        self.client.force_login(self.acheteur)

        reponse = self.client.post(self._url('payments:lancer'),
                                   {'telephone': '+242068409872', 'operateur': 'MTN_CG'},
                                   HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(reponse.status_code, 400)
        self.paiement.refresh_from_db()
        self.assertEqual(self.paiement.statut, 'en_attente')
        self.assertEqual(self.paiement.cle_idempotence, '')  # nouvelle tentative = nouvelle clé

    @mock.patch('payments.tamo.interroger_statut')
    def test_statut_paiement_valide_les_billets(self, interroger):
        interroger.return_value = {
            'reference': 'TAMOC-1', 'statut': 'success',
            'merchant_reference': self.paiement.reference, 'amount': 5000, 'charge': {},
        }
        self.client.force_login(self.acheteur)
        self.paiement.tamo_reference = 'TAMOC-1'
        self.paiement.statut = 'en_cours'
        self.paiement.save()

        reponse = self.client.get(self._url('payments:statut'))
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(reponse.json()['paye'])

        self.billet.refresh_from_db()
        self.assertEqual(self.billet.statut, 'valide')

    def test_lien_payer_depuis_un_billet_cree_le_paiement(self):
        self.client.force_login(self.acheteur)
        # Billet réservé avant l'intégration : aucun paiement lié
        self.paiement.delete()
        reponse = self.client.get(reverse('payments:billet', args=[self.billet.id]))
        self.assertEqual(reponse.status_code, 302)

        paiement = Paiement.objects.get()
        self.assertEqual(paiement.montant, self.billet.prix_achat)
        self.assertEqual(list(paiement.billets.all()), [self.billet])
