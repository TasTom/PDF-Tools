# Déploiement — backend PDF-Tools

## État au 2026-09-13

| Voie | État |
|---|---|
| **A** — correctif dans `tuilter/bg-remover-api` | ✅ **DÉPLOYÉ ET VÉRIFIÉ EN PRODUCTION** |
| **B** — Space dédié `*/pdf-tools-api` | ⛔ préparé et testé, **bloqué** : création de Space refusée en `402` |

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

Backend autonome, sans base de données ni authentification, prêt à servir
`pdf.warult-tools.com`.

**Tout est préparé et vérifié de bout en bout. Seule la création du Space est
refusée :**

| Compte | Space privé | Space public |
|---|---|---|
| `warult47` | `402 Payment Required` | `402 Payment Required` |
| `tuilter` | `402 Payment Required` | `402 Payment Required` |

`isPro: False` et `canPay: False` sur les deux comptes. HuggingFace facture
désormais la création de Spaces. Les jetons **peuvent** écrire dans un dépôt
existant (un modèle et un dataset privés ont été créés puis supprimés pour le
prouver) : le blocage porte bien sur la création de Spaces.

Un Space **existant** peut être utilisé : passer `--space` au Space de votre choix.

### Publier

```bash
# 1. Verifier ce qui partira (rien n'est publie)
python hf_deploy/deploy_space.py --space <compte>/pdf-tools-api --dry-run

# 2. Publier (--create si le Space n'existe pas encore)
python hf_deploy/deploy_space.py --space <compte>/pdf-tools-api --create
```

Le script assemble le contenu à la demande depuis les fichiers versionnés :

```
backend/app/                 -> app/
backend/requirements.txt     -> requirements.txt
hf_deploy/Dockerfile         -> Dockerfile
hf_deploy/space_README.md    -> README.md
```

Aucune duplication dans le dépôt, donc aucune dérive possible entre le code
testé et le code déployé.

### Vérifier après publication

```bash
python hf_deploy/verify_deployment.py https://<compte>-pdf-tools-api.hf.space
```

17 vérifications couvrant les dix outils, y compris les pièges : archive ZIP,
numérotation d'origine des pages, compression effective à chaque niveau, refus
d'un PDF corrompu, filigrane réellement posé, sens de rotation.

### Public ou privé ?

**Un Space privé ne peut pas servir le site.** Mesuré :

| Space | Accès anonyme |
|---|---|
| `warult47/bg-remover-api` (privé) | **HTTP 404** |
| `tuilter/bg-remover-api` (public) | HTTP 200 |

Le `rewrite` de Vercel qui expose `/api/*` sur `pdf.warult-tools.com` est
**anonyme** : il n'envoie aucun jeton. Un backend privé rendrait donc les dix
outils inaccessibles.

C'est sans conséquence ici : le code de PDF-Tools est **déjà public** sur
`github.com/TasTom/PDF-Tools`. Et si le déploiement reste sur
`tuilter/bg-remover-api`, il n'y a rien de neuf à exposer — ce Space est déjà
public par nécessité.

> Si vous tenez au privé, il faut remplacer le `rewrite` de Vercel par un *Route
> Handler* qui ajoute l'en-tête `Authorization` — les rewrites de Next.js ne
> permettent pas d'injecter un en-tête.

---

## Ce qui a été vérifié

### Le correctif A, en production

17/17 via `https://pdf.warult-tools.com`, plus les 5 contrôles spécifiques au
correctif.

### Le paquet B, avant publication

Construit et exécuté dans un conteneur, avec le même `Dockerfile` et le même
contenu que ceux qui seraient publiés :

| Contrôle | Résultat |
|---|---|
| Construction de l'image | OK |
| Conteneur | `Up (healthy)` |
| Les dix outils | **18/18** |
| Compression (low / medium / high) | −88 % / −56 % / −42 % |
| Ratios identiques au poste local | oui |
| Poids du paquet | 31 Ko, 8 fichiers |

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
