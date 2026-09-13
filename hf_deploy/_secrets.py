"""Liste les secrets du Space existant (NOMS seulement, jamais les valeurs).

But : savoir quels secrets sont necessaires pour que notre backend PDF demarre,
sans jamais afficher leur contenu.
"""
from huggingface_hub import HfApi

api = HfApi()

for espace in ("tuilter/bg-remover-api", "warult47/pdf-tools-api"):
    print(f"=== {espace} ===")
    try:
        secrets = api.get_space_secrets(espace)
        if not secrets:
            print("  aucun secret configure")
        for secret in secrets:
            # Selon la version, la liste contient des noms ou des dictionnaires.
            nom = secret if isinstance(secret, str) else secret.get("key", "?")
            print(f"  {nom}")
    except Exception as exc:
        print(f"  erreur : {type(exc).__name__}: {str(exc)[:120]}")
    print()

print("=== variables non secretes (publiques) du Space dedie ===")
try:
    for variable in api.get_space_variables("warult47/pdf-tools-api"):
        nom = variable if isinstance(variable, str) else variable.get("key")
        valeur = None if isinstance(variable, str) else variable.get("value")
        print(f"  {nom}" + (f" = {valeur}" if valeur is not None else ""))
except Exception as exc:
    print(f"  erreur : {type(exc).__name__}")
