import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberFormat


def normalize_phone(raw):
    """
    Transforme un numéro saisi avec son indicatif international
    (ex. '+242 06 123 4567') en format E.164 ('+242061234567').
    Renvoie None si le numéro ne commence pas par '+' ou s'il est invalide.

    phonenumbers gère les spécificités de chaque pays : en France le 0 initial
    disparaît (+33 06... -> +336...), au Congo il fait partie du numéro.
    """
    raw = (raw or "").strip()
    if not raw.startswith("+"):
        return None 

    try:
        number = phonenumbers.parse(raw, None)
    except NumberParseException:
        return None

    if not phonenumbers.is_valid_number(number):
        return None

    return phonenumbers.format_number(number, PhoneNumberFormat.E164)