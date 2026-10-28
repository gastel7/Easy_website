"""Client TamoAPI — https://tamo.tasa.pro (API REST v1, doc marchand TASA).

Règles reprises de la documentation :
  * lectures (GET)  : en-tête X-API-Token ;
  * écritures (POST) : X-API-Token + Idempotency-Key + signature v2 :
        X-Signature = hex(HMAC-SHA256(
            METHOD \\n URI \\n X-Timestamp \\n X-Nonce \\n Idempotency-Key \\n corps
            -- séparés par un saut de ligne -- , api_secret))
    URI = chemin + query, sans le domaine. Le corps est sérialisé UNE fois : on signe
    exactement les octets envoyés.
  * webhooks : X-Webhook-Signature = HMAC-SHA256(corps brut, secret du webhook), comparé
    à temps constant.
  * limites : 120 lectures / 30 écritures par minute (429 + Retry-After).
"""

import hashlib
import hmac
import json
import secrets
import time
from urllib.parse import urlparse

import requests
from django.conf import settings

# Chemins relatifs à l'API (doc TASA §3 : POST https://tamoapi.tasa.pro/api/v1/collections)
CHEMIN_COLLECTE = '/v1/collections'

# NOTE : le chemin exact de l'interrogation de statut n'est pas public dans la doc en ligne
# (« statut par UUID ou référence »). Il est surchargeable : TAMO_STATUT_PATH dans le .env.
CHEMIN_STATUT = settings.TAMO.get('STATUT_PATH', '/v1/collections/{identifiant}')

DELAI_TIMEOUT = 20  # secondes


class TamoError(Exception):
    """Erreur renvoyée par l'API (ou réseau)."""

    def __init__(self, message, status_code=None, requete_id=None, retry_after=None):
        super().__init__(message)
        self.status_code = status_code
        self.requete_id = requete_id
        self.retry_after = retry_after


def config():
    return settings.TAMO


def est_configure():
    """Prêt à encaisser : token, secret et produit collecte renseignés."""
    cfg = config()
    return bool(cfg['API_TOKEN'] and cfg['API_SECRET'] and cfg['PRODUCT_ID'])


def _uri(url):
    """Chemin + query, sans le domaine (objet de la signature)."""
    parties = urlparse(url)
    return parties.path + (f"?{parties.query}" if parties.query else '')


def signature_v2(method, uri, timestamp, nonce, idempotency_key, corps, secret):
    """hex(HMAC-SHA256(...)) — la chaîne signée, telle que décrite par TASA."""
    chaine = '\n'.join([
        method.upper(),
        uri,
        str(timestamp),
        nonce,
        idempotency_key or '',
        corps or '',
    ])
    return hmac.new(secret.encode('utf-8'), chaine.encode('utf-8'), hashlib.sha256).hexdigest()


def serialiser(payload):
    """Une seule sérialisation : les mêmes octets sont signés et envoyés."""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _entetes_ecriture(method, url, idempotency_key, corps):
    cfg = config()
    timestamp = int(time.time())
    nonce = secrets.token_hex(16)  # 16 caractères minimum
    return {
        'X-API-Token': cfg['API_TOKEN'],
        'Idempotency-Key': idempotency_key,
        'X-Signature-Version': '2',
        'X-Timestamp': str(timestamp),
        'X-Nonce': nonce,
        'X-Signature': signature_v2(method, _uri(url), timestamp, nonce, idempotency_key, corps,
                                    cfg['API_SECRET']),
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }


def _appeler(method, url, payload=None, idempotency_key=None, timeout=DELAI_TIMEOUT):
    cfg = config()
    corps = serialiser(payload) if payload is not None else ''

    entetes = {'X-API-Token': cfg['API_TOKEN'], 'Accept': 'application/json'}
    if idempotency_key:
        entetes.update(_entetes_ecriture(method, url, idempotency_key, corps))
    else:
        entetes['Content-Type'] = 'application/json'

    try:
        reponse = requests.request(
            method, url, headers=entetes,
            data=corps.encode('utf-8') if corps else None,
            timeout=timeout,
        )
    except requests.RequestException as erreur:
        raise TamoError(f"API Tamo injoignable : {erreur}") from erreur

    requete_id = reponse.headers.get('X-Request-Id')

    try:
        charge = reponse.json() if reponse.text else {}
    except ValueError:
        charge = {}

    if reponse.status_code == 429:
        raise TamoError("Limite d'appels Tamo atteinte, réessayez dans un instant.",
                        status_code=429, requete_id=requete_id,
                        retry_after=reponse.headers.get('Retry-After'))
    if reponse.status_code >= 400:
        detail = charge.get('message') or charge.get('error') or charge.get('detail') or reponse.text
        raise TamoError(f"Erreur Tamo ({reponse.status_code}) : {detail}",
                        status_code=reponse.status_code, requete_id=requete_id)
    return charge


def _donnees(charge):
    """La charge utile est tantôt sous « data », tantôt en racine."""
    data = charge.get('data')
    return data if isinstance(data, dict) else charge


def extraire_transaction(charge):
    """(référence, identifiant, statut) d'une réponse de collecte ou de statut."""
    data = _donnees(charge or {})
    reference = data.get('reference') or charge.get('reference') or ''
    identifiant = data.get('id') or data.get('uuid') or data.get('transaction_id') \
        or charge.get('id') or charge.get('uuid') or ''
    statut = data.get('status') or charge.get('status') or ''
    return str(reference), str(identifiant), str(statut)


def creer_collecte(montant, telephone, operateur, merchant_reference,
                   payer_name='', description='', metadata=None, idempotency_key=None):
    """POST /v1/collections — Cash In (produit collecte). HTTP 201 en cas de succès."""
    cfg = config()
    if not est_configure():
        raise TamoError("Le paiement Tamo n'est pas configuré (TAMO_API_TOKEN / "
                        "TAMO_API_SECRET / TAMO_PRODUCT_ID manquants).")

    payload = {
        'product_id': cfg['PRODUCT_ID'],
        'operator_code': operateur,
        'amount': int(montant),
        'phone_number': telephone,
        'merchant_reference': merchant_reference,
    }
    if payer_name:
        payload['payer_name'] = payer_name
    if description:
        payload['description'] = description
    if metadata:
        payload['metadata'] = metadata

    url = f"{cfg['API_BASE']}{CHEMIN_COLLECTE}"
    charge = _appeler('POST', url, payload=payload, idempotency_key=idempotency_key)
    reference, identifiant, statut = extraire_transaction(charge)
    return {'reference': reference, 'identifiant': identifiant, 'statut': statut or 'pending',
            'charge': charge}


def interroger_statut(identifiant):
    """GET — statut par UUID ou référence (doc TASA §5)."""
    cfg = config()
    if not identifiant:
        raise TamoError("Aucune référence de transaction à interroger.")
    url = f"{cfg['API_BASE']}{CHEMIN_STATUT.format(identifiant=identifiant)}"
    charge = _appeler('GET', url)
    reference, _, statut = extraire_transaction(charge)
    data = _donnees(charge or {})
    return {'reference': reference, 'statut': statut,
            'merchant_reference': data.get('merchant_reference', ''),
            'amount': data.get('amount'), 'charge': charge}


def verifier_signature_webhook(corps_brut, signature_recue, secret=None):
    """X-Webhook-Signature = HMAC-SHA256(corps brut, secret du webhook), comparé à temps constant."""
    secret = secret if secret is not None else config()['WEBHOOK_SECRET']
    if not secret or not signature_recue:
        return False
    attendue = hmac.new(secret.encode('utf-8'), corps_brut, hashlib.sha256).hexdigest()
    recue = str(signature_recue).strip()
    # Longueur d'abord, puis comparaison à temps constant
    if len(recue) != len(attendue):
        return False
    return hmac.compare_digest(recue, attendue)


def signature_webhook(corps_brut, secret):
    """Utilisé par les tests et pour préparer un appel de vérification côté Tamo."""
    return hmac.new(secret.encode('utf-8'), corps_brut, hashlib.sha256).hexdigest()
