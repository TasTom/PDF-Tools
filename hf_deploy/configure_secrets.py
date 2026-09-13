"""Configure les secrets du Space PDF-Tools.

Deux problemes corriges ici :

1. `SECRET_KEY` : le Space a ete cree a partir du gabarit de l'autre produit
   (warult-tools.com) et a herite de sa cle. Les deux services signaient donc
   leurs jetons avec le meme secret, et un jeton emis par l'un etait accepte par
   l'autre. Le Space dedie recoit desormais sa propre cle.

2. Variables heritees (`STRIPE_*`, `GOOGLE_CLIENT_ID`, `FREE_DAILY_LIMIT`,
   `PRO_DAILY_LIMIT`) : elles concernent l'autre produit et ne sont lues par
   aucun code de ce depot. Elles sont laissees en place — les supprimer
   n'apporterait rien et ferait perdre la trace de l'historique du Space.

La valeur generee est ecrite dans le `.env` local (deja ignore par git) pour
qu'il reste une seule source de verite, puis poussee dans le Space. Le script
n'affiche jamais le secret : seulement son empreinte, pour verifier la
concordance sans le divulguer.

Usage :
    python hf_deploy/configure_secrets.py --dry-run
    python hf_deploy/configure_secrets.py
"""
from __future__ import annotations

import argparse
import hashlib
import re
import secrets
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
ENV = RACINE / ".env"

ESPACE = "warult47/pdf-tools-api"
DOMAINE = "https://pdf.warult-tools.com"

# 32 octets tires au sort, ecrits en hexadecimal : 64 caracteres, soit le double
# de ce qu'exige HS256. Le format hexa evite tout caractere a echapper dans un
# `.env`, un Dockerfile ou un formulaire web.
OCTETS_CLE = 32

# Marqueur ecrit a cote de la cle une fois qu'elle a ete generee ICI.
#
# Il est indispensable : le `.env` local contenait deja une SECRET_KEY, qui est
# peut-etre celle du gabarit commun aux deux produits. La reutiliser reviendrait
# a ne rien corriger du tout. Sans ce marqueur, la cle locale est donc consideree
# comme douteuse et remplacee.
MARQUEUR = "SECRET_KEY_DEDIEE"


def empreinte(valeur: str) -> str:
    """Empreinte courte : permet de comparer deux secrets sans les reveler."""
    return hashlib.sha256(valeur.encode()).hexdigest()[:12]


def lire_env() -> dict[str, str]:
    if not ENV.is_file():
        return {}
    entrees: dict[str, str] = {}
    for ligne in ENV.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        nom, _, valeur = ligne.partition("=")
        entrees[nom.strip()] = valeur.strip()
    return entrees


def ecrire_env(cle: str) -> None:
    """Ecrit la cle et son marqueur dans le `.env`, en preservant le reste."""
    lignes = ENV.read_text(encoding="utf-8").splitlines() if ENV.is_file() else []

    def remplacer(nom: str, valeur: str) -> bool:
        expression = re.compile(rf"^\s*{nom}\s*=")
        for index, ligne in enumerate(lignes):
            if expression.match(ligne):
                lignes[index] = valeur
                return True
        return False

    if not remplacer("SECRET_KEY", f"SECRET_KEY={cle}"):
        lignes.append(f"SECRET_KEY={cle}")
    if not remplacer(MARQUEUR, f"{MARQUEUR}=pdf-tools"):
        lignes.append(f"{MARQUEUR}=pdf-tools")

    ENV.write_text("\n".join(lignes).rstrip("\n") + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="afficher les changements sans rien appliquer")
    parser.add_argument("--rotate", action="store_true",
                        help="forcer une nouvelle cle meme si la locale est deja dediee")
    args = parser.parse_args()

    entrees = lire_env()
    locale = entrees.get("SECRET_KEY", "")
    dediee = entrees.get(MARQUEUR) == "pdf-tools"

    if args.rotate or not dediee or len(locale) < 32:
        neuve = secrets.token_hex(OCTETS_CLE)
        raison = ("--rotate demande" if args.rotate
                  else "nouvelle cle : la locale ne porte pas le marqueur dedie")
    else:
        neuve = locale
        raison = "cle locale deja dediee, conservee (pas de deconnexion de masse)"

    print("=== secret cible ===")
    print(f"  {raison}")
    print(f"  SECRET_KEY : {len(neuve)} caracteres, empreinte {empreinte(neuve)}")
    if locale:
        print(f"  (locale    : {len(locale)} caracteres, empreinte {empreinte(locale)})")

    variables = {
        "SECRET_KEY": neuve,
        # Explicite plutot que heritee du gabarit : le Space contient encore
        # FREE_DAILY_LIMIT et PRO_DAILY_LIMIT, qui ne sont PAS lus par ce code.
        "DAILY_LIMIT": "20",
        "CORS_ORIGINS": f"{DOMAINE},http://localhost:3000",
    }

    if args.dry_run:
        print("\n--dry-run : rien n'a ete applique.")
        print("  variables qui seraient definies :")
        for nom, valeur in variables.items():
            apercu = f"{len(valeur)} caracteres" if nom == "SECRET_KEY" else valeur
            print(f"    {nom} = {apercu}")
        return 0

    if neuve != locale:
        ecrire_env(neuve)
        print(f"\n  ecrit dans {ENV.name} (ignore par git)")

    try:
        from huggingface_hub import HfApi
    except ImportError:
        sys.exit("\nhuggingface_hub est absent. Installer : pip install huggingface_hub")

    api = HfApi()
    for nom, valeur in variables.items():
        api.add_space_secret(ESPACE, nom, valeur)
        apercu = f"{len(valeur)} caracteres" if nom == "SECRET_KEY" else valeur
        print(f"  {ESPACE} <- {nom} = {apercu}")

    print("\nLe Space redemarre pour prendre en compte les secrets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
