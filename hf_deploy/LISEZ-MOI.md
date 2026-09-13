# Déploiement — backend PDF-Tools

## État au 2026-09-13

| Élément | État | Adresse |
|---|---|---|
| **A** — correctif dans `tuilter/bg-remover-api` | appliqué (n'est plus utilisé par le site) | — |
| **B** — Space dédié | ✅ **en service** | `warult47/pdf-tools-api.hf.space` |
| **Frontend** | ✅ **redéployé** sur Vercel | `pdf.warult-tools.com` |
| **C** — passer `tuilter` en privé | ⛔ **IMPOSSIBLE** | voir plus bas |
| **D** — comptes + quota | ⚠️ **code prêt, non déployé** | voir « Blocage base de données » |

---

## Le site tourne désormais sur le Space dédié

`pdf.warult-tools.com` n'utilise **plus** `tuilter`. La bascule a été faite :

1. Ajout de la variable `BACKEND_URL` sur le projet Vercel **`pdf-tools`**
   → `https://warult47-pdf-tools-api.hf.space`
2. Déploiement du frontend (`vercel deploy --prod` depuis `frontend/`)

⚠️ `BACKEND_URL` est lue **au moment de la construction** (`next.config.js` est
évalué au build, car le rewrite en dépend). **Toute modification de cette
variable exige donc un nouveau déploiement** pour prendre effet.

### Vérifié en production

| Contrôle | Résultat |
|---|---|
| Les dix outils via `pdf.warult-tools.com` | **17/17** |
| Nouvelle direction artistique servie | oui (titre, `WARULT`, `Réunir`, `Verrouiller`) |
| Marqueurs de l'ancienne version | **0** (plus d'emoji, de dégradé, de page Tarifs) |
| `/sitemap.xml`, `/robots.txt`, `/icon.svg` | `200` |
| `/pricing` | `404` (retirée, comme voulu) |

### Taille d'envoi : la limite de Vercel ne s'applique pas

Vercel plafonne normalement le corps des requêtes à 4,5 Mo pour les fonctions
serverless. Mesuré : **ce n'est pas le cas ici**, le rewrite `/api/*` passe par
le proxy et non par une fonction.

| Envoi | Résultat |
|---|---|
| 2,6 Mo | `200` |
| 7,7 Mo | `200` |
| 16,3 Mo | `200` |
| 37,8 Mo | `200` (23,5 s) |
| 60,3 Mo | `400 Fichier trop volumineux (max 50MB)` |
| 68,9 Mo | `400 Fichier trop volumineux (max 50MB)` |

La limite de 50 Mo est donc appliquée **exactement** comme documentée, de bout en
bout. Reproduire :

```bash
python hf_deploy/check_body_limit.py https://pdf.warult-tools.com
```

---

## ⛔ C — passer `tuilter/bg-remover-api` en privé est impossible

**Ce n'est pas un problème de droits : c'est une dépendance.**

`warult-tools.com` — l'autre produit (suppression de fond, 14 outils image) —
appelle ce Space **directement depuis le navigateur**. Preuve : l'URL
`tuilter-bg-remover-api.hf.space` figure dans le bundle
`layout-6454ad7614eda900.js`, via la variable Vercel `NEXT_PUBLIC_API_URL`.

Or un Space privé répond `404` aux requêtes anonymes (mesuré). Le passer en privé
**casserait le produit principal**, pas seulement les PDF.

### Ce qu'il faudrait pour y arriver

Créer un **second** Space dédié à `warult-tools.com` (il lui faut rembg, OpenCV,
onnxruntime, Stripe, une base PostgreSQL — pas notre backend PDF). Or la création
d'un Space est refusée en `402` sur les deux comptes.

**En l'état, `tuilter/bg-remover-api` doit rester public.**

---

## A — Correctif appliqué à `tuilter/bg-remover-api`

Publié le 2026-09-13, avant la bascule. Trois fichiers remplacés :
`app/services/pdf_processing.py`, `app/routers/pdf_tools.py` et `requirements.txt`.
Le reste du Space (suppression de fond, facturation, comptes, outils image)
n'a **pas** été touché.

Ce correctif reste utile si `warult-tools.com` venait à exposer des outils PDF,
mais **le site PDF ne passe plus par là**.

Pour le rejouer (si le Space était restauré à une version antérieure) :

```bash
python hf_deploy/apply_patch_tuilter.py     # lit le jeton depuis .env
```

---

## B — Space dédié `warult47/pdf-tools-api`

✅ En service, utilisé par `pdf.warult-tools.com`.

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
python hf_deploy/verify_deployment.py https://pdf.warult-tools.com
```

17 vérifications couvrant les dix outils : archive ZIP, numérotation d'origine
des pages, compression effective à chaque niveau, refus d'un PDF corrompu,
filigrane réellement posé, sens de rotation.

⚠️ Depuis l'ajout des comptes, ces vérifications exigent un **jeton** : sans lui
l'API répond `401`, ce qui n'est pas un échec du déploiement.

---

## D — Comptes et quota : code prêt, déploiement bloqué

### Ce qui est prêt

Auth JWT + quota quotidien global, tables `pdf_users` / `pdf_daily_usage`
(préfixe `pdf_` : la base peut être partagée avec l'autre produit).
42 tests backend passent, le parcours complet a été validé dans le navigateur
(inscription depuis un outil, retour à l'outil, opération décomptée, quota
atteint, déconnexion, reconnexion).

### Secrets configurés

```bash
python hf_deploy/configure_secrets.py --dry-run   # montrer
python hf_deploy/configure_secrets.py             # appliquer
```

| Secret | Valeur | Pourquoi |
|---|---|---|
| `SECRET_KEY` | 64 caractères, **propre à ce Space** | Il avait hérité de celle du gabarit de l'autre produit : un jeton émis par `warult-tools.com` était déchiffrable ici |
| `DAILY_LIMIT` | `20` | Le Space contient encore `FREE_DAILY_LIMIT` et `PRO_DAILY_LIMIT`, qui ne sont **pas** lus par ce code |
| `CORS_ORIGINS` | `https://pdf.warult-tools.com,http://localhost:3000` | Explicite, plutôt qu'héritée |

Le script refuse de réutiliser la clé locale tant qu'elle ne porte pas le marqueur
`SECRET_KEY_DEDIEE=pdf-tools` — sans quoi il aurait « remplacé » la clé partagée par
elle-même.

### Blocage base de données

Le Space a hérité d'un `DATABASE_URL` du gabarit de l'autre produit. **Trois pannes
successives**, chacune masquant la suivante ; les deux premières se corrigent en code,
la troisième non :

| # | Erreur au démarrage | Cause | Traitement |
|---|---|---|---|
| 1 | `ModuleNotFoundError: No module named 'psycopg2'` | URL en forme **synchrone** (`postgresql://`) : SQLAlchemy en déduit psycopg2, refusé par un moteur async | `url_asynchrone()` dans `app/database.py` |
| 2 | `TypeError: connect() got an unexpected keyword argument 'sslmode'` | L'URL Neon contient `?sslmode=require&channel_binding=require`, qu'asyncpg transmet à `connect()` | `_nettoyer()` : `sslmode` traduit en `ssl`, options libpq retirées |
| 3 | `InvalidPasswordError: password authentication failed for user 'neondb_owner'` | **Mot de passe périmé** dans le secret | ⛔ Nécessite un `DATABASE_URL` valide |

Indice utile : `https://tuilter-bg-remover-api.hf.space/health` répond
`{"status":"ok","db":"connected"}` — Neon fonctionne, seul le secret de **ce** Space
est périmé.

### Retour arrière effectué

Le 2026-09-13, le déploiement du code avec comptes a laissé le site en `503`
(le service ne démarrait pas). `pdf.warult-tools.com` a été rétabli en revenant à la
révision `752673dd2a`, la dernière sans comptes :

```bash
python hf_deploy/rollback_space.py --space warult47/pdf-tools-api --liste 8
python hf_deploy/rollback_space.py --space warult47/pdf-tools-api --revision 752673dd2a
```

Vérifié après retour arrière : `POST /api/pdf/rotate` → `200`, 932 octets, en direct et
via `pdf.warult-tools.com`.

### Lire les journaux d'un Space — indispensable

`space_info` ne dit que `RUNNING` ou `in error`, et l'interface web affiche
« SSE is not enabled ». Les trois pannes ci-dessus n'ont été identifiées que par :

```bash
python hf_deploy/journaux_space.py warult47/pdf-tools-api
```

Le jeton doit appartenir au **propriétaire** du Space : sinon `401 Invalid username or
password`. Ne pas définir `HF_TOKEN` s'il désigne l'autre compte.

---

## Le frontend

Le projet Vercel **`pdf-tools`** sert `pdf.warult-tools.com`. Il n'est **pas
relié à GitHub** : un `git push` ne déclenche aucun déploiement. Publier
demande :

```bash
cd frontend
vercel deploy --prod --yes --project pdf-tools
```

Retour arrière immédiat si besoin :

```bash
vercel rollback --project pdf-tools
```

### Deux projets Vercel à ne pas confondre

| Projet | Site | Dépôt |
|---|---|---|
| `pdf-tools` | `pdf.warult-tools.com` | **ce dépôt** (`PDF-Tools`) |
| `warult-tools` | `warult-tools.com` | `Background_remover` |

---

## Ce qui a été vérifié

| Contrôle | Résultat |
|---|---|
| Les dix outils en production | **17/17** |
| Nouvelle DA servie | oui |
| Limite de 50 Mo de bout en bout | exacte |
| Space dédié | `RUNNING`, 12 routes, aucun résidu |
| Ratios de compression Windows / Linux | identiques (−88 / −56 / −42 %) |
| Compilation du frontend | 14 pages, types validés |
| Retour arrière du Space | `503` → `200` sur une opération PDF réelle |
| Tests backend | **44**, tous verts |

### Ce qui n'a pas été vérifié

Le temps de démarrage réel côté HuggingFace après une mise en veille. Le
conteneur, lui, démarre et répond en moins de dix secondes en local.
