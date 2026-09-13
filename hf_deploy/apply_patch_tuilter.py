"""Applique le correctif A : met a jour les fichiers PDF du Space tuilter.

Le jeton est lu depuis .env et n'est jamais affiche.

Ce script remplace TROIS fichiers dans le Space existant :
    app/services/pdf_processing.py
    app/routers/pdf_tools.py
    requirements.txt

Rien d'autre n'est touche : la suppression de fond, la facturation, les comptes
et les outils image restent identiques.
"""
from __future__ import annotations

import sys
from pathlib import Path

from huggingface_hub import HfApi

RACINE = Path(__file__).resolve().parent.parent
PATCH = Path(__file__).resolve().parent / "patch-tuilter"
ESPACE = "tuilter/bg-remover-api"

# Les trois fichiers a publier : source locale -> destination dans le Space.
FICHIERS = {
    "app/services/pdf_processing.py": PATCH / "app/services/pdf_processing.py",
    "app/routers/pdf_tools.py": PATCH / "app/routers/pdf_tools.py",
    "requirements.txt": PATCH / "requirements.txt",
}


def lire_jeton() -> str:
    """Lit le jeton depuis .env, sans jamais l'afficher."""
    env = RACINE / ".env"
    if not env.is_file():
        sys.exit(f"Fichier introuvable : {env}")
    for ligne in env.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if ligne.startswith("#") or "=" not in ligne:
            continue
        cle, valeur = ligne.split("=", 1)
        if cle.strip() == "hf_tuilter_token":
            return valeur.strip().strip('"').strip("'")
    sys.exit("La cle 'hf_tuilter_token' est absente de .env")


def main() -> None:
    # --- Controles avant tout envoi ---
    manquants = [str(chemin) for chemin in FICHIERS.values() if not chemin.is_file()]
    if manquants:
        sys.exit(f"Fichiers du patch introuvables :\n  " + "\n  ".join(manquants))

    print("=== fichiers a publier ===")
    for destination, source in FICHIERS.items():
        print(f"  {source.stat().st_size:>7} o  {destination}")

    # Le nouveau service doit exposer tout ce que le routeur importe.
    service = FICHIERS["app/services/pdf_processing.py"].read_text(encoding="utf-8")
    routeur = FICHIERS["app/routers/pdf_tools.py"].read_text(encoding="utf-8")
    attendus = [
        "merge_pdfs", "split_pdf", "compress_pdf", "pdf_to_images", "images_to_pdf",
        "protect_pdf", "unprotect_pdf", "add_watermark_to_pdf", "rotate_pdf", "crop_pdf",
        "build_zip", "PdfConversionError",
    ]
    absents = [nom for nom in attendus if f"def {nom}" not in service and f"class {nom}" not in service]
    if absents:
        sys.exit(f"\nERREUR : le service n'expose pas : {absents}")
    print(f"\n  controle : le service expose les {len(attendus)} symboles attendus")

    if "router = APIRouter" not in routeur:
        sys.exit("\nERREUR : le routeur n'expose pas 'router' (attendu par app/main.py)")
    print("  controle : le routeur expose bien 'router'")

    api = HfApi(token=lire_jeton())

    compte = api.whoami().get("name")
    if compte != "tuilter":
        sys.exit(f"\nERREUR : le jeton appartient a '{compte}', pas a 'tuilter'")
    print(f"  controle : jeton valide pour '{compte}'")

    # --- Envoi ---
    print("\n=== publication ===")
    for destination, source in FICHIERS.items():
        api.upload_file(
            path_or_fileobj=str(source),
            path_in_repo=destination,
            repo_id=ESPACE,
            repo_type="space",
            commit_message=f"fix(pdf): {Path(destination).name} — compression reelle, ZIP, erreurs explicites",
        )
        print(f"  envoye : {destination}")

    print(f"\nPublie sur https://huggingface.co/spaces/{ESPACE}")
    print("Le Space reconstruit son image automatiquement.")


if __name__ == "__main__":
    main()
