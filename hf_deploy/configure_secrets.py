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

3. `DATABASE_URL` : le Space avait herite de celle du gabarit de l'autre produit,
et son mot de passe est refuse par la base. Le script ne la genere pas — il ne
peut pas — mais il la **lit dans le `.env` local** et la pousse, ce qui evite
d'avoir a la coller dans une conversation ou un historique de commandes.

   Elle est verifiee avant d'etre appliquee : une URL illisible ou incomplete
   ferait echouer le demarrage du Space et rendrait le site indisponible, ce qui
   s'est deja produit trois fois.

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

from sqlalchemy.engine import make_url

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


# Noms dont la valeur ne doit JAMAIS etre affichee.
SECRETS = ("SECRET_KEY", "DATABASE_URL")


def resume(nom: str, valeur: str) -> str:
    """Apercu affichable d'une variable, sans jamais reveler un mot de passe."""
    if nom == "SECRET_KEY":
        return f"<{len(valeur)} caracteres>"
    if nom == "DATABASE_URL":
        # `hide_password` remplace le mot de passe par trois etoiles. L'hote et
        # le nom de base restent lisibles : c'est exactement ce qu'on veut
        # verifier avant d'ecraser le secret du Space.
        try:
            url = make_url(valeur)
            return f"{url.drivername} {url.host or '?'}/{url.database or '?'}"
        except Exception:
            return "<illisible>"
    return valeur


def verifier_url_base(url: str) -> str | None:
    """Renvoie un message d'erreur si l'URL ne peut pas etre utilisee, sinon None.

    Le but est d'echouer ICI, avec une explication, plutot que sur le Space par
    un `503 Your space is in error` qui ne dit rien. Chaque controle correspond a
    une panne deja rencontree.
    """
    if not url:
        return None  # absente : le secret existant du Space n'est pas touche

    if url != url.strip() or url.startswith(("'", '"')):
        return ("guillemets ou espaces autour de la valeur : ecrire "
                "DATABASE_URL=postgresql://... sans encadrement")

    try:
        analyse = make_url(url)
    except Exception as erreur:
        return (f"URL illisible ({erreur}). Cas le plus courant : un caractere "
                "special NON encode dans le mot de passe. Un '@' doit s'ecrire "
                "%40, un '#' %23, un '?' %3F, un '/' %2F, un '%' %25.")

    if not analyse.drivername.startswith(("postgres", "sqlite")):
        return f"moteur inattendu : {analyse.drivername}"

    # SQLite est un fichier : ni hote, ni base, ni mot de passe. Ces controles ne
    # valent que pour PostgreSQL, sinon une base locale de developpement serait
    # refusee a tort.
    if analyse.drivername.startswith("sqlite"):
        return None

    if not analyse.host:
        return "hote manquant : l'URL doit contenir @hote"
    if not analyse.database:
        return "nom de base manquant : l'URL doit se terminer par /nom_de_base"
    if not analyse.password:
        return "mot de passe manquant : la base refusera la connexion"
    if not analyse.username:
        return "nom d'utilisateur manquant"

    return None


def avertissements(url: str) -> list[str]:
    """Remarques qui ne bloquent pas, mais qui expliquent une panne a venir.

    Une avertissement n'est pas une erreur : le script continue. Mais le lire ici
    coute moins cher que de le decouvrir dans les journaux du Space, apres un
    redeploiement qui a rendu le site indisponible.
    """
    if not url.startswith("postgres"):
        return []

    try:
        analyse = make_url(url)
    except Exception:
        return []

    remarques = []

    # Neon publie deux chaines de connexion. Celle dont l'hote contient
    # « -pooler » passe par PgBouncer en mode transaction, qui ne supporte pas
    # les requetes preparees d'asyncpg : il faut alors desactiver son cache.
    # Celle sans « -pooler » est la connexion directe, qui fonctionne telle
    # quelle — c'est celle a privilegier ici.
    if analyse.host and "-pooler" in analyse.host:
        remarques.append(
            "l'hote contient « -pooler » (PgBouncer en mode transaction). "
            "asyncpg y echoue sur ses requetes preparees ; preferer la chaine "
            "SANS « -pooler » depuis la console Neon (bouton « Connect »)."
        )

    return remarques


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

    # --- Base de donnees ---
    url_base = entrees.get("DATABASE_URL", "").strip()
    if not url_base:
        print("\n=== base de donnees ===")
        print(f"  DATABASE_URL absente de {ENV.name} : le secret du Space est "
              "laisse tel quel (et il est refuse par la base).")
        print("  Pour la fournir : ajouter une ligne "
              "DATABASE_URL=postgresql://... dans .env, puis relancer ce script.")
    else:
        erreur = verifier_url_base(url_base)
        if erreur:
            # On s'arrete AVANT d'appliquer quoi que ce soit : un secret
            # invalide pousse sur le Space ferait echouer son demarrage.
            sys.exit(
                f"\nERREUR : DATABASE_URL inutilisable.\n  {erreur}\n\n"
                "  Rien n'a ete applique. Corriger la ligne DATABASE_URL de "
                f"{ENV.name}, puis relancer."
            )
        variables["DATABASE_URL"] = url_base
        print("\n=== base de donnees ===")
        print(f"  DATABASE_URL lue depuis {ENV.name} : {resume('DATABASE_URL', url_base)}")
        for avertissement in avertissements(url_base):
            print(f"  ATTENTION : {avertissement}")

    if args.dry_run:
        print("\n--dry-run : rien n'a ete applique.")
        print("  variables qui seraient definies :")
        for nom, valeur in variables.items():
            print(f"    {nom} = {resume(nom, valeur)}")
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
        print(f"  {ESPACE} <- {nom} = {resume(nom, valeur)}")

    print("\nLe Space redemarre pour prendre en compte les secrets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
