"""Configuration des tests.

Deux choses doivent etre faites AVANT tout import de `app` :

1. rendre le paquet `app` importable, quel que soit le repertoire d'ou pytest
   est lance ;
2. definir `SECRET_KEY` (le service refuse de demarrer sans) et `DATABASE_URL`
   (une base jetable, pour ne jamais toucher a une base reelle).
"""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

# --- Environnement, avant le premier import de `app` ---
os.environ.setdefault("SECRET_KEY", "cle-de-test-uniquement-32-caracteres-minimum")
# Base jetable : chaque execution de la suite repart d'un schema vide.
_BASE_TEST = Path(tempfile.gettempdir()) / "pdf_tools_tests.db"
for suffixe in ("", "-wal", "-shm"):
    fichier = Path(str(_BASE_TEST) + suffixe)
    if fichier.exists():
        fichier.unlink()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_BASE_TEST}"

import pytest  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from app.main import app, limiter  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """Remet les compteurs de debit a zero : sans cela, les tests dependraient de l'ordre.

    Le limiteur compte par adresse IP et le TestClient est toujours la meme :
    sans reinitialisation, le test de limite ferait echouer tous les suivants.
    """
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture(autouse=True)
def _reset_quota():
    """Vide le compteur quotidien avant chaque test.

    Le quota est GLOBAL et persistant : sans cette remise a zero, le premier
    test consommerait le quota de tous les suivants, et la suite deviendrait
    sensible a son ordre d'execution.

    On passe par une connexion SQLite directe plutot que par le moteur async de
    l'application : celui-ci est lie a la boucle d'evenements du TestClient, et
    l'ouvrir depuis une autre boucle est une source d'erreurs subtiles.
    """
    def vider():
        try:
            with sqlite3.connect(_BASE_TEST) as connexion:
                connexion.execute("DELETE FROM pdf_daily_usage")
                connexion.commit()
        except sqlite3.OperationalError:
            # Table pas encore creee (premier test) : rien a vider.
            pass

    vider()
    yield
    vider()


@pytest.fixture(scope="module")
def anon_client():
    """Client SANS authentification : pour tester les refus."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def raw_client():
    """Client neuf, sans aucun en-tete.

    Distinct de `anon_client` : celui-ci ne sert qu'une fois que la fixture
    `client` a pose un en-tete d'authentification sur `anon_client`, qui est
    module-scoped et donc partage.
    """
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def client(anon_client):
    """Client AUTHENTIFIE.

    Un compte est cree une fois par module et son jeton pose en en-tete par
    defaut : les outils exigent desormais un compte, donc tous les tests
    d'outils passent par cette fixture.
    """
    identifiant = os.urandom(4).hex()
    reponse = anon_client.post(
        "/api/auth/register",
        json={
            "email": f"tests-{identifiant}@example.com",
            "username": f"tests{identifiant}",
            "password": "MotDePasse1",
        },
    )
    assert reponse.status_code == 201, reponse.text
    anon_client.headers.update({"Authorization": f"Bearer {reponse.json()['access_token']}"})
    yield anon_client
    anon_client.headers.pop("Authorization", None)

