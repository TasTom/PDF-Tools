"""Lit les journaux de construction et d'execution d'un Space HuggingFace.

`space_info` ne dit que « RUNNING » ou « in error » : pour savoir POURQUOI, il
faut l'endpoint de journaux, que `huggingface_hub` n'expose pas. L'interface web
le lit par un flux SSE, et affiche « SSE is not enabled » quand le flux n'est pas
consomme en streaming — d'ou l'ouverture explicite ci-dessous.

Cet outil n'est pas un confort : c'est le seul moyen de distinguer un probleme de
code d'un probleme de secret. Il a servi a diagnostiquer deux pannes de
demarrage invisibles depuis l'exterieur, ou le Space repondait seulement
« 503 Your space is in error » :

  1. `ModuleNotFoundError: No module named 'psycopg2'` — DATABASE_URL fourni en
     forme synchrone, corrige en imposant le pilote async ;
  2. `TypeError: connect() got an unexpected keyword argument 'sslmode'` —
     options libpq a retirer de l'URL, corrige ;
  3. `InvalidPasswordError` — mot de passe de la base perime, qui ne se corrige
     que dans les reglages du Space.

Le jeton doit appartenir au PROPRIETAIRE du Space : un simple collaborateur, ou
le jeton d'un autre compte, recoit un 401 « Invalid username or password ». Ce
script utilise le jeton du cache local ; retirer HF_TOKEN de l'environnement si
un autre compte y est defini.

Usage :
    python hf_deploy/journaux_space.py [compte/espace]
"""
from __future__ import annotations

import json
import sys

import httpx
from huggingface_hub import get_token

ESPACE = sys.argv[1] if len(sys.argv) > 1 else "warult47/pdf-tools-api"
JETON = get_token() or ""

if not JETON:
    sys.exit("Aucun jeton HuggingFace. Lancer 'hf auth login' ou definir HF_TOKEN.")

print(f"jeton : {len(JETON)} caracteres")

for nature in ("build", "run"):
    url = f"https://huggingface.co/api/spaces/{ESPACE}/logs/{nature}"
    print(f"=========== journaux {nature} ===========", flush=True)
    try:
        with httpx.Client(timeout=httpx.Timeout(20.0, read=45.0)) as client:
            with client.stream(
                "GET",
                url,
                headers={
                    "Authorization": f"Bearer {JETON}",
                    "Accept": "text/event-stream",
                },
            ) as reponse:
                if reponse.status_code != 200:
                    print("  " + reponse.read().decode(errors="replace")[:300])
                    continue

                for numero, ligne in enumerate(reponse.iter_lines()):
                    if ligne.startswith("data:"):
                        contenu = ligne[5:].strip()
                        try:
                            charge = json.loads(contenu)
                            texte = charge.get("data") or charge.get("msg") or contenu
                        except Exception:
                            texte = contenu
                    elif ligne.strip():
                        texte = ligne
                    else:
                        continue

                    # La console Windows n'encode pas tout l'UTF-8 des journaux.
                    sur = str(texte).encode("ascii", "replace").decode("ascii")
                    print(f"  {sur[:240]}", flush=True)

                    if numero > 400:
                        print("  (flux tronque)")
                        break
    except Exception as exc:
        print(f"  erreur : {type(exc).__name__}: {str(exc)[:160]}")
    print()
