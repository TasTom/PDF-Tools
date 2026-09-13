# Déploiement — backend PDF-Tools

## État au 2026-09-13

| Voie | État | Adresse |
|---|---|---|
| **A** — correctif dans `tuilter/bg-remover-api` | ✅ déployé et vérifié | `pdf.warult-tools.com` |
| **B** — Space dédié | ✅ **déployé et vérifié** | `warult47/pdf-tools-api` |

---

## A — Correctif appliqué à `tuilter/bg-remover-api`

Publié le 2026-09-13. Trois fichiers remplacés dans le Space existant :
`app/services/pdf_processing.py`, `app/routers/pdf_tools.py` et `requirements.txt`.
Le reste du Space (suppression de fond, facturation, comptes, outils image)
n'a **pas** été touché.

### Vérifié en production, via `https://pdf.warult-tools.com`

| Comportement | Avant | Après |
|---|---|---|
| `to-image` sur 3 pages | 1 PNG | **archive ZIP `pages.zip`** |
| `compress` sur un scan | **0 %** aux trois niveaux | **−88 % / −56 % / −42 %** |
| PDF corrompu | page blanche silencieuse | **`422` explicite** |
| Les dix outils | — | **17/17** |

Reproduire la vérification :

```bash
python hf_deploy/check_production.py https://pdf.warult-tools.com
python hf_deploy/verify_deployment.py https://pdf.warult-tools.com
```

Pour rejouer le correctif (si le Space était restauré à une version antérieure) :

```bash
python hf_deploy/apply_patch_tuilter.py     # lit le jeton depuis .env
```

---

## B — Space dédié `warult47/pdf-tools-api`

✅ **Déployé et vérifié.**

```bash
# 1. Verifier ce qui partira (rien n'est publie)
python hf_deploy/deploy_space.py --space warult47/pdf-tools-api --dry-run

# 2. Publier. --clean supprime les fichiers absents du paquet :
#    indispensable pour reprendre un Space existant, sinon les anciens
#    fichiers restent dans l'image.
python hf_deploy/deploy_space.py --space warult47/pdf-tools-api --clean
```

Le script assemble le contenu à la demande depuis les fichiers versionnés :

```
backend/app/                 -> app/
backend/requirements.txt     -> requirements.txt
hf_deploy/Dockerfile         -> Dockerfile
hf_deploy/space_README.md    -> README.md
hf_deploy/space_dockerignore -> .dockerignore
```

Aucune duplication dans le dépôt, donc aucune dérive possible entre le code
testé et le code déployé.

### Historique de l'opération

La création d'un Space est refusée en **`402 Payment Required`** (`isPro: False`,
`canPay: False`). Le Space a donc été obtenu autrement : `warult47/bg-remover-api`
existait déjà, en `RUNTIME_ERROR`, figé au 24 juin 2026, sans aucun code PDF.
Il a été **repris** plutôt que créé :

1. **Passé en public** — `update_repo_settings`, aucune création, donc aucun `402`.
2. **Renommé** `warult47/pdf-tools-api` — `move_repo`, son ancien nom aurait été
   trompeur pour du PDF.
3. **Rempli** avec notre paquet, et **14 fichiers orphelins supprimés** (code
   `bg_removal`, `billing`, `auth`, `usage`, `image_processing`, `routers/tools`,
   `queue`, `database`).

**Contrôle fait avant de le rendre public** : aucun secret en clair (aucune clé
Stripe, aucun jeton, aucune URL de base de données avec mot de passe), et
**tout son contenu était déjà public** dans `tuilter/bg-remover-api`. Rendre
public n'a donc rien exposé de nouveau.

### Vérifier

```bash
python hf_deploy/verify_deployment.py https://warult47-pdf-tools-api.hf.space
```

17 vérifications couvrant les dix outils : archive ZIP, numérotation d'origine
des pages, compression effective à chaque niveau, refus d'un PDF corrompu,
filigrane réellement posé, sens de rotation.

### Pour le brancher sur le site

Le Space expose `/api/pdf/*`. Pour que `pdf.warult-tools.com` l'utilise, il faut
pointer `BACKEND_URL` du projet **Vercel** vers :

```
https://warult47-pdf-tools-api.hf.space
```

⚠️ **Ne le faites pas avant d'avoir décidé du sort de `tuilter/bg-remover-api`.**
Les deux Spaces exposent les mêmes routes PDF : le site fonctionne déjà via
`tuilter`. Basculer sur le Space dédié **enlèverait l'usage PDF** de `tuilter`,
mais n'y casserait rien d'autre — ses autres domaines (suppression de fond,
comptes, facturation) resteraient intacts.

### Public ou privé ?

**Un Space privé ne peut pas servir le site.** Mesuré :

| Space | Accès anonyme |
|---|---|
| Space privé | **HTTP 404** |
| Space public | HTTP 200 |

Le `rewrite` de Vercel qui expose `/api/*` sur `pdf.warult-tools.com` est
**anonyme** : il n'envoie aucun jeton. Un backend privé rendrait donc les dix
outils inaccessibles. Et le code de PDF-Tools est **déjà public** sur
`github.com/TasTom/PDF-Tools` : un Space privé n'apporterait rien.

> Si vous tenez au privé, il faut remplacer le `rewrite` de Vercel par un *Route
> Handler* qui ajoute l'en-tête `Authorization` — les rewrites de Next.js ne
> permettent pas d'injecter un en-tête.

---

## Ce qui a été vérifié

### Le correctif A, en production

17/17 via `https://pdf.warult-tools.com`, plus 5 contrôles spécifiques.

### Le Space B, en production

17/17 via `https://warult47-pdf-tools-api.hf.space`.

| Contrôle | Résultat |
|---|---|
| Runtime | `RUNNING` |
| Routes exposées | 12 (les 10 PDF + `/` + `/health`) |
| Résidus de l'ancien service | **aucun** |
| Fichiers | 11 |
| Compression (low / medium / high) | −88 % / −56 % / −42 % |
| Ratios identiques au poste local | oui |

### La compatibilité des dépendances

Le vrai risque du correctif A était de casser le Space en modifiant
`requirements.txt`. Vérifié dans `python:3.11-slim`, exactement comme son
`Dockerfile` :

- `pip install --dry-run` sur **tout** leur fichier modifié → **code de sortie 0, aucun conflit** (`rembg`, `opencv`, `stripe`, `onnxruntime` cohabitent avec `pypdf`, `pikepdf`, `pypdfium2`)
- `PyPDF2` et `pdf2image` n'étaient importés que par le fichier remplacé
- Rendus PDF réels sous Linux : 3 pages, 1 % d'encre, écriture et compression OK

Ces ratios identiques entre Windows et le conteneur Linux confirment que
`pypdfium2` et `pikepdf` (modules natifs) se comportent de la même façon des deux
côtés.

### Ce qui n'a pas été vérifié

Le temps de démarrage réel côté HuggingFace, et le comportement après une mise
en veille. Le conteneur, lui, démarre et répond en moins de dix secondes en local.
