"""Revenir a une revision anterieure d'un Space.

Publier une version qui ne demarre pas laisse le service indisponible : le
retour arriere doit donc etre aussi simple qu'un deploiement. Le contenu de la
revision visee est telecharge, puis republie tel quel — ce qui remet aussi les
fichiers supprimes depuis, sans avoir a les re-lister a la main.

Usage :
    python hf_deploy/rollback_space.py --space warult47/pdf-tools-api --revision <sha>

Sans `--revision`, le script liste les revisions et signale celles qui ne
contiennent pas le module d'authentification : ce sont les versions anterieures
a l'ajout des comptes.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

PRESERVES = {".gitattributes", ".gitignore"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--space", required=True)
    parser.add_argument("--revision", help="revision (SHA) a restaurer")
    parser.add_argument("--liste", type=int, default=0, metavar="N",
                        help="afficher les N dernieres revisions puis s'arreter")
    args = parser.parse_args()

    try:
        from huggingface_hub import HfApi, snapshot_download
    except ImportError:
        sys.exit("huggingface_hub est absent. Installer : pip install huggingface_hub")

    api = HfApi()
    print(f"Compte HuggingFace : {api.whoami().get('name', '?')}")

    if args.liste:
        print(f"\n=== {args.liste} dernieres revisions de {args.space} ===")
        for commit in api.list_repo_commits(args.space, repo_type="space")[: args.liste]:
            fichiers = api.list_repo_files(args.space, repo_type="space", revision=commit.commit_id)
            comptes = "avec comptes" if any(f.startswith("app/auth/") for f in fichiers) else "sans comptes"
            date = commit.created_at.strftime("%H:%M:%S") if commit.created_at else "?"
            print(f"  {commit.commit_id[:10]}  {date}  {comptes:<13}  {commit.title[:50]}")
        return 0

    if not args.revision:
        sys.exit("Indiquer --revision <sha>, ou --liste N pour voir les revisions.")

    with tempfile.TemporaryDirectory(prefix="rollback-") as temporaire:
        destination = Path(temporaire)
        print(f"\nTelechargement de {args.revision[:10]}...")
        snapshot_download(
            repo_id=args.space,
            repo_type="space",
            revision=args.revision,
            local_dir=str(destination),
            # `local_dir` fait ecrire un dossier de metadonnees `.cache` DANS la
            # destination. Sans ce filtre, il se retrouve liste avec les fichiers
            # du Space et brouille le contenu du paquet.
            ignore_patterns=[".cache/*"],
        )
        fichiers = sorted(
            str(chemin.relative_to(destination)).replace("\\", "/")
            for chemin in destination.rglob("*")
            if chemin.is_file()
        )
        print(f"  {len(fichiers)} fichiers recuperes")
        for nom in fichiers:
            print(f"    {nom}")

        print("\nRepublication...")
        api.upload_folder(
            folder_path=str(destination),
            repo_id=args.space,
            repo_type="space",
            commit_message=f"revert: restaurer {args.revision[:10]}",
        )

        presents = set(api.list_repo_files(args.space, repo_type="space"))
        orphelins = sorted(presents - set(fichiers) - PRESERVES)
        for nom in orphelins:
            api.delete_file(
                path_in_repo=nom,
                repo_id=args.space,
                repo_type="space",
                commit_message=f"revert: retirer {nom}",
            )
        print(f"  {len(orphelins)} fichier(s) hors de la revision supprime(s)")

    print(f"\nRevision {args.revision[:10]} restauree. Le Space reconstruit son image.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
