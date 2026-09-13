"""Instance partagee du limiteur de debit.

Ce module existe pour eviter un import circulaire : `main.py` importe les
routeurs, et les routeurs ont besoin du limiteur. Le definir dans `main.py`
obligerait les routeurs a importer `main`, qui les importe deja.

La cle de comptage est l'IP reelle du client, lue dans `X-Forwarded-For`.
Voir `client_key` pour le motif : `get_remote_address` de slowapi lit
`request.client.host`, qui derriere un hebergeur est l'adresse du PROXY, et
cette adresse varie d'une requete a l'autre.
"""
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def client_key(request: Request) -> str:
    """Cle de limitation de debit : l'adresse IP reelle du client.

    `get_remote_address` lit `request.client.host`, qui est l'adresse du PROXY
    quand le service est heberge. Mesure en production derriere le proxy
    HuggingFace : cette adresse varie d'une requete a l'autre, donc le compteur
    etait reparti sur plusieurs cles — 100 appels d'affilee n'ont declenche que
    45 refus, au lieu d'un mur des le 21e.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # Un proxy ajoute son entree a la suite : la PREMIERE est le client.
        client = forwarded.split(",")[0].strip()
        if client:
            return client
    return get_remote_address(request)


limiter = Limiter(key_func=client_key)
