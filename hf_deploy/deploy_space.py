"""Assemble et publie le backend PDF-Tools dans un Space HuggingFace.

Le Space attend une structure plate, avec le Dockerfile a la racine. Plutot que
de dupliquer `app/` dans le depot (source de derive), ce script assemble le
contenu a la demande dans un dossier temporaire, depuis les fichiers deja
versionnes :

    backend/app/                  -> app/
    backend/requirements.txt      -> requirements.txt
    hf_deploy/Dockerfile          -> Dockerfile
    hf_deploy/space_README.md     -> README.md

Usage :
    python hf_deploy/deploy_space.py --space warult47/pdf-tools-api --dry-run
    python hf_deploy/deploy_space.py --space warult47/pdf-tools-api

`--dry-run` assemble et affiche le contenu sans rien publier : a faire en premier
pour verifier ce qui partirait.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
BACKEND = RACINE / "backend"
DOCKERFILE = RACINE / "hf_deploy" / "Dockerfile"
SPACE_README = RACINE / "hf_deploy" / "space_README.md"

# Fichiers exclus de l'image : ils ne servent qu'au developpement.
EXCLUS = {"__pycache__", ".pytest_cache", "tests", "conftest.py", "pytest.ini",
          "requirements-dev.txt", ".venv", ".dockerignore"}


def assemble(destination: Path) -> list[str]:
    """Construit le contenu du Space et renvoie la liste des fichiers ecrits."""
    if not BACKEND.is_dir():
        sys.exit(f"Dossier introuvable : {BACKEND}")
    for requis in (DOCKERFILE, SPACE_README):
        if not requis.is_file():
            sys.exit(f"Fichier introuvable : {requis}")

    destination.mkdir(parents=True, exist_ok=True)

    # app/ : copie recursive, sans les caches.
    cible_app = destination / "app"
    cible_app.mkdir(exist_ok=True)
    for source in (BACKEND / "app").rglob("*"):
        if any(partie in EXCLUS for partie in source.parts):
            continue
        relative = source.relative_to(BACKEND / "app")
        if source.is_dir():
            (cible_app / relative).mkdir(parents=True, exist_ok=True)
        else:
            (cible_app / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, cible_app / relative)

    shutil.copy2(BACKEND / "requirements.txt", destination / "requirements.txt")
    shutil.copy2(DOCKERFILE, destination / "Dockerfile")
    shutil.copy2(SPACE_README, destination / "README.md")

    return sorted(
        str(chemin.relative_to(destination)).replace("\\", "/")
        for chemin in destination.rglob("*")
        if chemin.is_file()
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Publie le backend PDF dans un Space HuggingFace.")
    parser.add_argument("--space", required=True, help="identifiant du Space, ex. warult47/pdf-tools-api")
    parser.add_argument("--dry-run", action="store_true", help="assembler sans publier")
    parser.add_argument("--create", action="store_true",
                        help="creer le Space s'il n'existe pas (exige un plan payant)")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="pdf-tools-space-") as temporaire:
        destination = Path(temporaire)
        fichiers = assemble(destination)

        print(f"=== contenu assemble ({len(fichiers)} fichiers) ===")
        for nom in fichiers:
            taille = (destination / nom).stat().st_size
            print(f"  {taille:>8} o  {nom}")

        total = sum((destination / nom).stat().st_size for nom in fichiers)
        print(f"\n  total : {total / 1024:.0f} Ko")

        # Le contexte ne doit evidemment pas contenir l'environnement virtuel.
        lourds = [n for n in fichiers if ".venv" in n or n.endswith((".pyc", ".db"))]
        if lourds:
            sys.exit(f"\nERREUR : fichiers indesirables dans le paquet : {lourds}")
        print("  controle : aucun environnement virtuel, cache ni base de donnees")

        if args.dry_run:
            print("\n--dry-run : rien n'a ete publie.")
            return

        try:
            from huggingface_hub import HfApi
        except ImportError:
            sys.exit("\nhuggingface_hub est absent. Installer : pip install huggingface_hub")

        api = HfApi()

        try:
            info = api.space_info(args.space)
            print(f"\nSpace existant : {args.space} (prive={info.private})")
        except Exception:
            if not args.create:
                sys.exit(
                    f"\nLe Space '{args.space}' est introuvable.\n"
                    "Le creer d'abord (attention : HuggingFace facture la creation de Spaces) :\n"
                    f"  hf repos create {args.space} --repo-type space --space-sdk docker\n"
                    "Ou relancer avec --create."
                )
            print(f"\nCreation du Space {args.space}...")
            api.create_repo(args.space, repo_type="space", space_sdk="docker", exist_ok=True)

        print(f"Publication de {len(fichiers)} fichiers...")
        api.upload_folder(
            folder_path=str(destination),
            repo_id=args.space,
            repo_type="space",
            commit_message="deploy: PDF Tools backend",
        )
        print(f"\nPublie : https://huggingface.co/spaces/{args.space}")
        print("Le Space construit son image automatiquement ; suivre les journaux sur la page.")


if __name__ == "__main__":
    main()
