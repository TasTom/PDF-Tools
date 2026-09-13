# PDF Tools

Outils PDF gratuits en ligne — fusionner, découper, compresser, convertir et protéger vos fichiers PDF.

Gratuit, sans paiement, dans la limite d'un **quota quotidien par compte**. Un compte est
nécessaire parce que chaque opération est décomptée à quelqu'un. Les fichiers ne sont
jamais conservés : ils sont traités le temps de l'opération, puis oubliés.

## Stack technique

- **Backend**: FastAPI + pypdf + pikepdf + pypdfium2 + reportlab + Pillow
- **Comptes**: SQLAlchemy (asyncio) + PostgreSQL, JWT (python-jose) + bcrypt
- **Frontend**: Next.js 15 + Tailwind CSS
- **Déploiement**: Vercel (frontend) + HuggingFace Space (backend)

## Direction artistique

Le site n'a ni héros centré, ni cartes, ni dégradés, ni emoji. L'accueil **est** la
liste des dix outils, groupée par sens de la transformation (réunir, séparer,
retoucher, verrouiller) — la même logique que les schémas qui accompagnent chaque outil.

### Jetons

La palette est **fermée** : `theme.colors` remplace celle de Tailwind au lieu de
l'étendre, donc `bg-slate-700` ou `text-indigo-400` ne compilent plus. Toute couleur
doit être nommée dans `tailwind.config.js`.

| Jeton | Valeur | Rôle | Contraste sur le papier |
|---|---|---|---|
| `paper` | `#FAFAF8` | Fond. Blanc froid, jamais crème | — |
| `sunk` | `#F2F1EB` | Zone en creux | — |
| `ink` | `#14181F` | Texte principal, boutons | 17,0:1 |
| `ink-soft` | `#4A5260` | Texte secondaire | 7,5:1 |
| `ink-faint` | `#676E79` | Texte tertiaire, libellés | 4,9:1 |
| `accent` | `#A32B1C` | **État uniquement** | 6,9:1 |
| `rule` | `#E4E2DA` | Filets de séparation | — |

Tous les textes dépassent le seuil AA (4,5:1). `ink-faint` était à 4,40:1 avant
correction — c'est le genre d'écart qui ne se voit pas à l'œil.

### Règles

- **Deux fontes, deux rôles.** IBM Plex Sans pour le texte ; IBM Plex Mono pour tout
  ce qui est *mesuré* (tailles, noms de fichiers, numéros de page). La mono n'est pas
  décorative.
- **L'accent marque un état**, jamais une décoration : focus clavier, page courante,
  traitement en cours, erreur. Dans les schémas, il désigne ce que l'opération
  *ajoute* au document (le verrou de « protéger », le filigrane, les repères de coupe).
- **Les schémas ne sont pas des icônes.** Chacun montre un document avant, une flèche,
  un document après. Ils portent l'information, d'où `aria-hidden` : le titre juste à
  côté dit déjà la même chose.
- **Une seule animation** dans tout le site : la barre de progression pendant un
  traitement. `prefers-reduced-motion` la fige.
- **Aucun emoji.** Les dix pictogrammes d'origine ont été remplacés par les schémas.

Les dix outils sont décrits une seule fois, dans `src/lib/tools.ts` : sommaire,
index de l'en-tête, titre de page, champs et métadonnées de référencement en découlent.

## Outils disponibles

| Outil | Entrée | Sortie |
|---|---|---|
| Fusionner | 2 à 20 PDF | PDF |
| Découper | 1 PDF | PDF ou ZIP |
| Compresser | 1 PDF | PDF |
| PDF → Image | 1 PDF | PNG/JPEG ou ZIP |
| Image → PDF | 1 à 50 images | PDF |
| Protéger | 1 PDF | PDF chiffré |
| Déverrouiller | 1 PDF chiffré | PDF |
| Filigrane | 1 PDF | PDF |
| Pivoter | 1 PDF | PDF |
| Recadrer | 1 PDF | PDF |

### Les sorties portent le nom des entrées

Le fichier renvoyé reprend le nom de celui qui a été envoyé, suivi du suffixe de
l'opération : `facture-mars.pdf` devient `facture-mars-compresse.pdf`,
`facture-mars-pivote.pdf`, etc.

Sans cela, le service répondait `compressed.pdf`, `rotated.pdf`… et l'utilisateur devait
renommer chaque résultat à la main, alors que le nom d'origine est justement
l'information qu'il connaît déjà.

Le radical est réduit à de l'ASCII sûr : un nom accentué ou contenant un guillemet
casserait l'en-tête `Content-Disposition` (un guillemet non échappé le scinde en deux).
Quand plusieurs fichiers sont envoyés (fusion, assemblage d'images), c'est **le premier**
qui donne la base — c'est celui que l'utilisateur a choisi en premier.

### Comportement des sorties multiples

`split` et `to-image` renvoient **une archive ZIP** dès qu'ils produisent plusieurs
fichiers (`<nom>-pages.zip`, chaque page nommée d'après son numéro d'origine :
`page_1.pdf`), et le fichier unique directement dans le cas contraire.

### Compression

`compress` réduit le poids via pikepdf (qpdf embarqué, aucun binaire système), par **deux
leviers indépendants** :

| Levier | Effet |
|---|---|
| **Définition** | une image dépassant le plafond du niveau est redimensionnée |
| **Qualité** | une image déjà en JPEG est réencodée à la qualité du niveau |

| Niveau | Résolution visée | Qualité JPEG | Gain mesuré sur un scan A4 à 150 ppp |
|---|---|---|---|
| `low` | ~100 ppp | 55 | **−88 %** |
| `medium` | ~160 ppp | 72 | **−56 %** |
| `high` | ~250 ppp | 85 | **−42 %** |

**Pourquoi deux leviers.** Un scan A4 à 150 ppp pèse 2,17 Mpx, soit *moins* que le plafond
de `medium` (2,5 Mpx). Avec le seul redimensionnement, le niveau **par défaut** n'avait
donc aucun effet sur la résolution la plus courante : l'utilisateur recevait un fichier
identique et pouvait croire l'outil cassé. Mesuré avant correction : `medium` → **0 %**.

Le levier de qualité est **auto-limité** : réencoder une image déjà fortement compressée
la fait grossir, et la modification est alors abandonnée. Une image sans perte (PNG, Flate)
n'est convertie en JPEG que si elle est aussi redimensionnée — sinon on dégraderait du
texte sans gain garanti.

La sortie n'est **jamais plus grosse que l'entrée** : à défaut de gain, le fichier
d'origine est renvoyé inchangé.

### Conversion en image

`to-image` utilise **pypdfium2**, qui embarque PDFium (le moteur de rendu de Chrome)
dans son wheel. Aucune dépendance système : le rendu se comporte à l'identique sur un
poste de développement Windows et dans le conteneur.

C'est le motif du choix, face aux deux alternatives :

| Solution | Licence | Dépendance système |
|---|---|---|
| **pypdfium2** (retenu) | BSD-3-Clause | aucune |
| pdf2image + poppler | MIT | binaire `pdftoppm` à installer |
| PyMuPDF | **AGPL-3.0** | aucune |

PyMuPDF aurait aussi supprimé la dépendance, mais l'AGPL impose de publier le code
source de tout service en ligne qui l'utilise.

## Tests

**44 tests** d'intégration couvrent les dix outils, les comptes, le quota et leurs cas
limites. Ils tournent **en mémoire** (TestClient de Starlette) : aucun serveur à lancer,
la suite complète prend moins de dix secondes.

```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest
```

Ce qu'ils figent, et qui autrement ne se revérifierait jamais :

| Comportement | Pourquoi il est testé |
|---|---|
| `split` et `to-image` renvoient un ZIP au-delà d'une page | Ils ne renvoyaient silencieusement que la première |
| `page_3` reste `page_3` après extraction de `1,3` | La numérotation d'origine doit survivre à la sélection |
| `to-image` rend un contenu non blanc | Une page blanche passait le test de statut HTTP |
| `to-image` refuse un fichier corrompu en `422` | Le comportement d'avant : une image blanche en silence |
| `compress` réduit de plus de 30 % un PDF d'images | La fonction ne compressait rien du tout |
| **chaque** niveau agit sur un scan A4 à 150 ppp | Le niveau par défaut n'avait aucun effet sur le cas le plus courant |
| `low` produit un fichier plus petit que `medium`, lui-même plus petit que `high` | Sinon le sélecteur de l'interface est un mensonge |
| `merge` respecte l'ordre d'envoi | Une inversion d'ordre produirait un PDF valide |
| `rotate` n'applique l'angle qu'aux pages visées | Une rotation de toutes les pages resterait valide |
| `watermark` écrit réellement le texte | Compter les pages ne prouverait rien |
| `compress` ne renvoie jamais plus gros que l'entrée | Garantie explicite du service |
| La sortie porte le nom de l'entrée, mis en forme | Un accent ou un guillemet laissé tel quel scinde l'en-tête |
| Le 21ᵉ appel rapproché renvoie `429` | La limite annoncée doit être réellement appliquée |
| Deux clients derrière le même proxy ne partagent pas de compteur | Le défaut mesuré en production : la clé était l'adresse du proxy, qui varie |
| `/health` n'est jamais limité | La sonde de déploiement ne doit pas être bloquée |
| Les dix outils refusent un appel sans compte | Le quota repose sur l'identité |
| Un mot de passe faible ou un email déjà pris est refusé | 8 caractères, une majuscule, un chiffre |
| Un email inconnu et un mauvais mot de passe donnent le **même** message | Sinon on peut énumérer les comptes |
| Un jeton signé avec la même clé mais émis par un **autre service** est refusé | Le cas réel : `SECRET_KEY` partagée avec l'autre produit |
| Un fichier refusé ne consomme pas d'opération | Valider avant de compter |
| Le quota est **global**, pas par outil | Sinon il suffirait de changer d'outil |
| Une URL de base en forme synchrone reçoit son pilote async | Panne de démarrage réelle en production |
| Les options libpq (`sslmode`) quittent l'URL | Deuxième panne réelle, masquée par la première |

Les compteurs du limiteur et le quota sont remis à zéro avant chaque test : sans cela, le
test de débit ferait échouer tous les suivants.

⚠️ Une variable d'environnement qui traîne (`DAILY_LIMIT=1` laissé dans un terminal) fait
échouer quatre tests en `429`. Vérifier l'environnement avant de conclure à une régression.

## Référencement

`robots.txt` et `sitemap.xml` sont générés depuis `src/lib/tools.ts` — les dix outils y
figurent automatiquement, sans liste à maintenir. Chaque page déclare son URL canonique
(les dix pages se ressemblent beaucoup : sans canonique, elles peuvent être prises pour du
contenu dupliqué).

## Protection anti-abus

Trois mécanismes indépendants : un **compte**, un **quota quotidien par compte**, et un
**débit par adresse IP**. Aucun n'est payant ; il n'y a pas de monétisation.

### 1. Un compte est nécessaire

Chaque opération est décomptée à quelqu'un, donc il faut savoir à qui. Les dix outils
exigent un jeton Bearer obtenu par `/api/auth/register` ou `/api/auth/login` ; sans lui,
l'API répond `401` et le frontend propose de créer un compte en conservant l'outil demandé.

| Route | Limite | Remarque |
|---|---|---|
| `POST /api/auth/register` | `5/minute` | Mot de passe : 8 caractères minimum, une majuscule, un chiffre |
| `POST /api/auth/login` | `10/minute` | **Même message** pour un email inconnu et un mauvais mot de passe, sinon on peut énumérer les comptes |
| `GET /api/auth/me` | — | Relit le profil et le quota du jour |

Le mot de passe est haché par `bcrypt` (`passlib`). Le jeton est un JWT HS256, valable
24 h, qui ne porte que l'identifiant : **l'utilisateur est relu en base à chaque appel**,
donc désactiver un compte prend effet immédiatement.

### 2. Quota quotidien, global

`DAILY_LIMIT` opérations par jour et par compte, **toutes opérations confondues** : un
quota par outil se contournerait en changeant d'outil. Au-delà, l'API répond `429` avec un
message explicite, et le bouton du formulaire est désactivé (« Quota atteint »).

| Point | Décision |
|---|---|
| Le compteur est incrémenté | **après** validation du fichier — un fichier refusé ne coûte pas d'opération |
| L'incrément | est atomique (`UPDATE … WHERE operations_count < limit RETURNING`), donc deux requêtes simultanées ne peuvent pas dépasser la limite |
| La remise à zéro | se fait à minuit, par date, sans tâche planifiée : c'est la ligne du jour qui compte |

### 3. Débit par adresse IP

Appliqué par `slowapi`, qui renvoie `429 Too Many Requests` au-delà.

| Type d'endpoint | Endpoints | Limite par défaut |
|---|---|---|
| Léger | `merge`, `split`, `compress`, `protect`, `unprotect`, `watermark`, `rotate`, `crop` | `20/minute` |
| Lourd (CPU) | `to-image`, `from-images` | `10/minute` |

Les deux valeurs se règlent sans toucher au code (`RATE_LIMIT_LIGHT`, `RATE_LIMIT_HEAVY`).
Le stockage est en mémoire : voir « Limites connues ».

### La clé de comptage n'est pas l'adresse du proxy

`get_remote_address` de slowapi lit `request.client.host`. **Derrière un hébergeur, cette
adresse est celle du proxy, pas celle du client** — et elle peut varier d'une requête à
l'autre. Mesuré en production : le compteur se répartissait alors sur plusieurs clés, donc
sur plusieurs limites.

| 100 appels d'affilée | Comportement |
|---|---|
| Avec `request.client.host` | 55 × `200`, puis 45 × `429` — premier refus au **42ᵉ** appel |
| Avec `X-Forwarded-For` (corrigé) | 20 × `200`, puis un mur de `429` dès le **21ᵉ** appel |

La clé est donc lue dans `X-Forwarded-For`, dont la **première** entrée porte le client
d'origine (les suivantes sont ajoutées par les proxys).

⚠️ **Cette valeur est déclarable par le client.** Un appelant qui envoie un
`X-Forwarded-For` différent à chaque requête obtient un compteur neuf à chaque fois. Le
débit par IP protège donc des abus ordinaires, pas d'un attaquant déterminé. C'est
désormais **le quota par compte qui porte la limite réelle** : lui ne dépend pas d'un
en-tête, puisque le compte est authentifié. Le débit par IP ne sert plus qu'à amortir les
rafales avant qu'elles n'atteignent le quota.

### Le jeton porte son émetteur et son destinataire

Le jeton contient `iss=pdf-tools` et `aud=pdf-tools-api`, tous deux **vérifiés à la
lecture**. Ce n'est pas décoratif : ce Space a été créé à partir du gabarit d'un autre
produit et avait hérité de sa `SECRET_KEY`. Tant que les deux clés sont identiques, un
jeton émis par l'autre service est déchiffrable ici — et comme les deux bases peuvent être
la même, il ouvrirait le compte portant le même identifiant. Ces deux champs font échouer
ce jeton-là. Une clé dédiée a depuis été définie, et les deux protections se cumulent.

## Configuration

| Variable | Défaut | Rôle |
|---|---|---|
| `SECRET_KEY` | — | **Obligatoire**, 32 caractères minimum. Le service refuse de démarrer sinon |
| `DATABASE_URL` | SQLite local | Base des comptes et des quotas. PostgreSQL en production |
| `DAILY_LIMIT` | `20` | Opérations par compte et par jour, tous outils confondus |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Durée de vie du jeton |
| `MAX_UPLOAD_MB` | `50` | Taille maximale d'un fichier envoyé |
| `RATE_LIMIT_LIGHT` | `20/minute` | Débit des opérations légères |
| `RATE_LIMIT_HEAVY` | `10/minute` | Débit des conversions lourdes |
| `RATE_LIMIT_LOGIN` | `10/minute` | Débit des tentatives de connexion |
| `RATE_LIMIT_REGISTER` | `5/minute` | Débit des créations de compte |
| `CORS_ORIGINS` | `https://pdf.warult-tools.com,http://localhost:3000` | Origines autorisées, séparées par des virgules |
| `BACKEND_URL` | `http://localhost:8000` | Cible du rewrite `/api/*` du frontend |
| `PROXY_MAX_BODY_MB` | `100` | Corps **total** accepté par le proxy Next |
| `SITE_URL` | `https://pdf.warult-tools.com` | URL publique, pour les canoniques et le plan de site |

### Le pilote de base est imposé par le code, pas par le secret

`DATABASE_URL` est défini ailleurs — réglages du Space, Railway, Neon — et il y arrive
presque toujours **sous sa forme synchrone**, `postgresql://…?sslmode=require`. Or un
moteur asynchrone en déduit le pilote `psycopg2` et refuse de démarrer, et `sslmode` est
un paramètre libpq qu'`asyncpg` transmet à `connect()`, où il n'existe pas. Les deux
échecs ont eu lieu en production, dans cet ordre, le second masqué par le premier :

```
ModuleNotFoundError: No module named 'psycopg2'
TypeError: connect() got an unexpected keyword argument 'sslmode'
```

`app/database.py` normalise donc l'URL : ajout du pilote async (`url_asynchrone`), puis
traduction de `sslmode` en `ssl` et retrait des options libpq (`_nettoyer`). Le choix du
pilote décrit une contrainte **de ce code**, pas de la base : il n'a pas à être imposé à
celui qui remplit le secret. Une URL qui nomme déjà son pilote n'est pas touchée.

Le service journalise au démarrage sa cible (pilote, hôte, base — jamais le mot de passe),
ce qui rend ce genre de panne lisible en une ligne.


### Deux plafonds d'envoi, pas un

Le service refuse un **fichier** au-delà de `MAX_UPLOAD_MB` (50 Mo). Mais le proxy de
Next plafonne le **corps total** de la requête à 10 Mo par défaut
(`DEFAULT_BODY_CLONE_SIZE_LIMIT`) : au-delà, il ne transmet qu'un corps tronqué, la
requête part malformée et échoue en `500` après trente secondes.

Mesuré sur cette machine, avant correction :

| Envoi de 13,9 Mo | Résultat |
|---|---|
| En direct sur le service | `200`, 2,3 s |
| À travers le proxy Next | `500` après 30,0 s — le fichier n'atteignait jamais le service |

Après correction (`experimental.middlewareClientMaxBodySize: '100mb'`) : `200` en 2,6 s,
puis `400 Fichier trop volumineux (max 50MB)` sur un fichier de 69 Mo — le message précis
du service atteint bien l'utilisateur.

`PROXY_MAX_BODY_MB` dépasse volontairement `MAX_UPLOAD_MB`, sinon un fichier hors limite
serait tronqué par le proxy et l'utilisateur lirait « transfert échoué » au lieu de
« Fichier trop volumineux ».

⚠️ Next **bufferise ce corps en mémoire**, par requête en cours. Baisser
`PROXY_MAX_BODY_MB` est le premier levier si l'hébergeur manque de mémoire. À noter pour
`merge`, qui accepte plusieurs fichiers : la limite porte sur leur somme.

Le fichier `.env` est lu à la racine du dépôt.

## Développement

```bash
# Backend — http://localhost:8000
cd backend
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest                                  # 44 tests, ~10 s
uvicorn app.main:app --reload --port 8000

# Frontend — http://localhost:3000
cd frontend
npm install
npm run dev
```

Le backend refuse de démarrer sans `SECRET_KEY` d'au moins 32 caractères : c'est
volontaire, un JWT signé avec une clé devinable laisse n'importe qui se faire passer pour
n'importe quel compte. En développement, `DATABASE_URL` retombe sur un fichier SQLite dans
`backend/data/`, dont le dossier est créé au premier lancement.

### Vérifier une version de production

```bash
cd frontend
npm run build && npm start
```

⚠️ Le projet est configuré en `output: 'standalone'`, pour lequel Next déconseille
`npm start` et recommande `node .next/standalone/server.js`. `npm start` fonctionne
malgré l'avertissement, mais c'est cette commande-là qu'il faut utiliser dans un
conteneur.

Ne jamais mesurer les performances sur `next dev` : le code n'y est pas minifié et les
chiffres sont faussés. Les scores de ce dépôt ont été relevés sur un `next build` servi
par `next start`.

### État vérifié le 2026-09-13

Build de production, Lighthouse :

| Page | Accessibilité | Bonnes pratiques | SEO | Performance |
|---|---|---|---|---|
| Accueil | 100 | 100 | 100 | 99 |
| Page d'outil | 100 | 100 | 100 | 99 |

Aucun audit en échec. Les seules pistes restantes viennent des polyfills de Next lui-même
(11 à 20 Kio), et non du code de ce dépôt.

## Déploiement

Le contexte de construction est le dossier **`backend/`**, pas `hf_deploy/` :

```bash
docker build -f hf_deploy/Dockerfile -t pdf-tools-api backend/
docker run -p 8000:8000 pdf-tools-api
```

L'image construit en 25 s et pèse 359 Mo. Elle tourne en utilisateur non-root (uid 1000),
comme l'exige un Space HuggingFace, et embarque une `HEALTHCHECK` qui interroge `/health` :
un conteneur défaillant est donc détecté de l'intérieur.

Le `Dockerfile` copie `requirements.txt` et `app/` nommément, jamais `COPY . .` : le dossier
`backend/` contient un virtualenv de développement de plus de 100 Mo, qui n'a rien à faire
dans une image Linux. Le `.dockerignore` associé ramène le contexte de 103 Mo à 0,03 Mo.

### Scripts

Un Space exige le `Dockerfile` à la racine de son dépôt, alors que celui-ci vit dans
`hf_deploy/`. Les scripts assemblent donc le contenu à la demande, dans un dossier
temporaire, depuis les fichiers déjà versionnés — plutôt que d'en dupliquer une copie dans
le dépôt, qui dériverait.

| Script | Rôle |
|---|---|
| `hf_deploy/deploy_space.py --space <id> --clean` | Assemble et publie. `--clean` supprime les fichiers absents du paquet, sans quoi l'ancienne application reste dans l'image |
| `hf_deploy/rollback_space.py --space <id> --revision <sha>` | Republie le contenu d'une révision antérieure. `--liste N` les affiche, en signalant celles qui précèdent l'ajout des comptes |
| `hf_deploy/configure_secrets.py [--dry-run\|--rotate]` | Définit `SECRET_KEY`, `DAILY_LIMIT` et `CORS_ORIGINS` sur le Space |
| `hf_deploy/journaux_space.py` | Lit les journaux de construction et d'exécution par le flux SSE |

### Deux comptes HuggingFace, un seul peut écrire

Le Space `warult47/pdf-tools-api` appartient au compte **`warult47`**. Le jeton du fichier
`.env` (`hf_tuilter_token`) appartient à **`tuilter`**, qui n'a que la lecture : publier
avec lui échoue en `403`, et gérer les secrets est de toute façon réservé au propriétaire.
Les scripts utilisent donc le jeton du cache local (`hf auth whoami`) et **ne doivent pas**
recevoir `HF_TOKEN` s'il désigne l'autre compte. `deploy_space.py` affiche désormais le
compte utilisé et alerte si le Space ne lui appartient pas.

### Lire les journaux d'un Space

`space_info` ne dit que « RUNNING » ou « in error », et l'interface web affiche
« SSE is not enabled » : le seul moyen de connaître la cause d'un échec de démarrage est
`hf_deploy/journaux_space.py`. C'est ce qui a permis de diagnostiquer trois pannes
successives de connexion à la base, invisibles depuis l'extérieur.

## Limites connues

- **Les compteurs de débit vivent en mémoire.** Ils repartent de zéro à chaque redémarrage
  et ne sont pas partagés entre instances. Le **quota**, lui, est en base : il survit aux
  redémarrages, ce qui est indispensable sur un Space dont le disque est éphémère.
- **Les tables portent le préfixe `pdf_`** (`pdf_users`, `pdf_daily_usage`). Ce n'est pas
  cosmétique : la base de ce service a d'abord été celle d'un autre produit, et le préfixe
  garantit que les comptes et les quotas ne se mélangent pas si les deux la partagent.
- **Le déploiement lui-même n'est pas automatisé.** Aucun projet Vercel n'est relié à
  GitHub : un `git push` ne déclenche rien. Le frontend se publie par
  `cd frontend && vercel deploy --prod --yes --project pdf-tools`, le backend par
  `hf_deploy/deploy_space.py`.
- **`BACKEND_URL` est lue au build**, et non à l'exécution, puisque le rewrite en dépend :
  la changer exige un redéploiement du frontend.
- **Les mots de passe sont affichés en clair** dans les champs Protéger / Déverrouiller :
  choix assumé, une faute de frappe sur le mot de passe d'un document est pire qu'un
  risque d'épaule.
