FROM python:3.11-slim

# Space HuggingFace : le conteneur doit tourner en utilisateur non-root.
RUN useradd -m -u 1000 user

WORKDIR /app

# Contexte de construction attendu : le dossier `backend/`.
#     docker build -f hf_deploy/Dockerfile backend/
#
# On copie explicitement, fichier par fichier, et jamais `COPY . .` : le dossier
# backend contient un virtualenv de developpement (plus de 100 Mo) qui n'a rien
# a faire dans une image Linux. Tests et caches sont exclus pour la meme raison.
COPY --chown=user requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user app ./app

USER user

# Sortie non bufferisee : les journaux arrivent sans attendre dans la console du Space.
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
ENV PORT=8000

# Sonde interne : /health doit repondre, sinon l'orchestrateur redemarre.
# On passe par Python, deja present, plutot que d'installer curl.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

# Forme JSON, et non « exec uvicorn ... » : avec la forme shell, Docker lance un
# shell intermediaire qui ne relaie pas SIGTERM. Le conteneur n'arreterait alors
# pas proprement le serveur, et les requetes en cours seraient coupees au lieu
# d'etre terminees.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
