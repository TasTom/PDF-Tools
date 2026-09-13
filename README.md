# PDF Tools

Outils PDF gratuits en ligne — fusionner, découper, compresser, convertir et protéger vos fichiers PDF.

Aucun compte, aucun paiement, aucune base de données : l'API est sans état et les fichiers
ne sont traités qu'en mémoire, le temps de l'opération.

## Stack technique

- **Backend**: FastAPI + pypdf + pikepdf + pypdfium2 + reportlab + Pillow
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

1. 📄 Fusionner PDF
2. ✂️ Découper PDF
3. 🗜️ Compresser PDF
4. 🖼️ PDF → Image
5. 📋 Image → PDF
6. 🔒 Protéger PDF
7. 🔓 Déverrouiller PDF
8. 💧 Filigrane PDF
9. 🔄 Pivoter PDF
10. ✂️ Recadrer PDF

### Comportement des sorties multiples

`split` et `to-image` renvoient **une archive ZIP** dès qu'ils produisent plusieurs
fichiers (`pages.zip`, chaque page nommée d'après son numéro d'origine : `page_1.pdf`),
et le fichier unique directement dans le cas contraire.

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

Vingt-cinq tests d'intégration couvrent les dix outils et leurs cas limites. Ils tournent
**en mémoire** (TestClient de Starlette) : aucun serveur à lancer, la suite complète prend
moins de quatre secondes.

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
| Le 21ᵉ appel rapproché renvoie `429` | La limite annoncée doit être réellement appliquée |
| Deux clients derrière le même proxy ne partagent pas de compteur | Le défaut mesuré en production : la clé était l'adresse du proxy, qui varie |
| `/health` n'est jamais limité | La sonde de déploiement ne doit pas être bloquée |

Les compteurs du limiteur sont remis à zéro avant chaque test : sans cela, le test de
débit ferait échouer tous les suivants.

## Référencement

`robots.txt` et `sitemap.xml` sont générés depuis `src/lib/tools.ts` — les dix outils y
figurent automatiquement, sans liste à maintenir. Chaque page déclare son URL canonique
(les dix pages se ressemblent beaucoup : sans canonique, elles peuvent être prises pour du
contenu dupliqué).

## Protection anti-abus

Pas de quota journalier ni de compte : la seule limite est un **débit par adresse IP**,
appliqué par `slowapi`, qui renvoie `429 Too Many Requests` au-delà.

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
`X-Forwarded-For` différent à chaque requête obtient un compteur neuf à chaque fois. La
limite protège donc des abus ordinaires, pas d'un attaquant déterminé. La corriger
demanderait une clé que le client ne contrôle pas — ce qui suppose une authentification,
laquelle n'existe pas ici par choix.

## Configuration

| Variable | Défaut | Rôle |
|---|---|---|
| `MAX_UPLOAD_MB` | `50` | Taille maximale d'un fichier envoyé |
| `RATE_LIMIT_LIGHT` | `20/minute` | Débit des opérations légères |
| `RATE_LIMIT_HEAVY` | `10/minute` | Débit des conversions lourdes |
| `CORS_ORIGINS` | `https://pdf.warult-tools.com,http://localhost:3000` | Origines autorisées, séparées par des virgules |
| `BACKEND_URL` | `http://localhost:8000` | Cible du rewrite `/api/*` du frontend |
| `PROXY_MAX_BODY_MB` | `100` | Corps **total** accepté par le proxy Next |
| `SITE_URL` | `https://pdf.warult-tools.com` | URL publique, pour les canoniques et le plan de site |

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
python -m pytest                                  # 25 tests, ~4 s
uvicorn app.main:app --reload --port 8000

# Frontend — http://localhost:3000
cd frontend
npm install
npm run dev
```

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

## Limites connues

- **Les compteurs de débit vivent en mémoire.** Ils repartent de zéro à chaque redémarrage
  et ne sont pas partagés entre instances.
- **Le déploiement lui-même n'est pas automatisé.** L'image est construite et vérifiée à la
  main ; il n'existe ni script de publication vers le Space, ni intégration continue. Le
  `Dockerfile` vit dans `hf_deploy/` alors que le contexte attendu est `backend/` : un Space
  HuggingFace exige le `Dockerfile` à la racine de son dépôt, donc `app/` et
  `requirements.txt` doivent y être copiés avant publication.
- **Les mots de passe sont affichés en clair** dans les champs Protéger / Déverrouiller :
  choix assumé, une faute de frappe sur le mot de passe d'un document est pire qu'un
  risque d'épaule.
