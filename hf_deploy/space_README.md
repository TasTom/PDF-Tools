---
title: PDF Tools API
emoji: 📄
colorFrom: gray
colorTo: red
sdk: docker
app_port: 8000
pinned: false
license: mit
short_description: Dix opérations sur un document PDF, sans compte ni stockage.
---

# PDF Tools API

API de traitement de fichiers PDF : dix opérations, aucune base de données,
aucun compte, aucun stockage. Les fichiers sont traités en mémoire, le temps de
l'opération, puis oubliés.

## Outils

| Opération | Endpoint | Limite de débit |
|---|---|---|
| Fusionner | `POST /api/pdf/merge` | 20/minute |
| Découper | `POST /api/pdf/split` | 20/minute |
| Compresser | `POST /api/pdf/compress` | 20/minute |
| Convertir en images | `POST /api/pdf/to-image` | 10/minute |
| Assembler des images | `POST /api/pdf/from-images` | 10/minute |
| Protéger | `POST /api/pdf/protect` | 20/minute |
| Déverrouiller | `POST /api/pdf/unprotect` | 20/minute |
| Filigrane | `POST /api/pdf/watermark` | 20/minute |
| Pivoter | `POST /api/pdf/rotate` | 20/minute |
| Recadrer | `POST /api/pdf/crop` | 20/minute |

`GET /health` renvoie `{"status": "ok"}`.

## Comportement des résultats

- Un seul fichier produit → le fichier directement.
- Plusieurs fichiers → une archive ZIP (`pages.zip`), chaque entrée nommée
  d'après le numéro de sa page d'origine (`page_3.pdf` reste `page_3`).
- Un PDF illisible → erreur `422` explicite, **jamais** une page blanche.

## Compression

Deux leviers indépendants : la **définition** (images au-dessus du plafond du
niveau) et la **qualité** (réencodage JPEG). Le second est indispensable : un scan
A4 à 150 ppp pèse 2,17 Mpx, soit moins que le plafond de `medium` (2,5 Mpx).

| Niveau | Résolution | Gain mesuré sur un scan A4 à 150 ppp |
|---|---|---|
| `low` | ≈ 100 ppp | −88 % |
| `medium` | ≈ 160 ppp | −56 % |
| `high` | ≈ 250 ppp | −42 % |

La sortie n'est **jamais plus grosse que l'entrée**.

## Dépendances

- `pypdf` — lecture et écriture PDF (PyPDF2 est déprécié)
- `pikepdf` — compression (qpdf embarqué)
- `pypdfium2` — rendu en image (PDFium embarqué, **aucune dépendance système**)
- `reportlab` — filigrane et création de PDF
- `slowapi` — limites de débit, en mémoire, par adresse IP

## Limites connues

- **Les compteurs de débit vivent en mémoire.** Ils repartent de zéro à chaque
  redémarrage et ne sont pas partagés entre instances.
- **Un Space en veille se réveille en quelques secondes.** Le premier appel après
  une période d'inactivité peut donc être lent.
- **Le texte du filigrane et les mots de passe sont limités à l'alphabet
  Helvetica**, la police standard des PDF.
