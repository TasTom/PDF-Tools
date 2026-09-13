# Correctif A — porter les corrections PDF dans `tuilter/bg-remover-api`

Ce dossier contient les **deux fichiers** à remplacer dans le Space existant, plus
la modification des dépendances. Le reste du Space (suppression de fond,
facturation, comptes, outils image) n'est **pas touché**.

## Ce que ça corrige

Le `pdf_processing.py` déployé est identique à la version d'origine de
`PDF-Tools` : il portait donc les mêmes défauts, mesurés avant correction.

| Défaut | Comportement actuel en production | Après correctif |
|---|---|---|
| `compress` ne compresse pas | **0 %** sur un PDF d'images, et le même résultat pour `low`, `medium` et `high` — le sélecteur ne sert à rien | −88 % (low), −56 % (medium), −42 % (high) |
| `to-image` échoue en silence | Une **page blanche** en A4 est renvoyée à la place du document, sans erreur | Erreur `422` explicite |
| `split` et `to-image` tronquent | Seule la **première** page est renvoyée | Archive ZIP `pages.zip`, chaque page nommée d'après son numéro d'origine |
| `watermark` | Fusionne la page avant de l'attacher au document de sortie (pypdf qualifie cette approche de *unreliable*) | `add_page` puis `merge_page` |
| Bibliothèque PDF | `PyPDF2`, déprécié | `pypdf` |

## Marche à suivre

### 1. Remplacer deux fichiers

```
app/services/pdf_processing.py   <- app/services/pdf_processing.py
app/routers/pdf_tools.py         <- app/routers/pdf_tools.py
```

### 2. Modifier `requirements.txt`

Retirer :

```
PyPDF2>=3.0
pdf2image>=1.16
```

Ajouter :

```
pypdf>=5.0
pikepdf>=9.0
pypdfium2>=4.30
```

`pdf2image` disparaît parce que le rendu passe désormais par `pypdfium2`, qui
embarque PDFium dans son wheel : **plus aucune dépendance système**. C'est un
avantage direct ici, puisque le `Dockerfile` de ce Space installe déjà
`libgl1`, `libglib2.0-0` et compagnie pour OpenCV, et n'a plus besoin de poppler.

> `PyMuPDF` aurait aussi convenu, mais sa licence **AGPL-3.0** imposerait de
> publier le code source du service. `pypdfium2` est en BSD-3-Clause.

### 3. Publier

Connectez-vous avec le compte **`tuilter`** (le Space lui appartient ; le jeton
`warult47` reçoit un `403`) :

```bash
hf auth login                  # se connecter en tant que tuilter
cd <dossier du Space cloné>
cp <ce_dossier>/app/services/pdf_processing.py app/services/pdf_processing.py
cp <ce_dossier>/app/routers/pdf_tools.py       app/routers/pdf_tools.py
# ... puis modifier requirements.txt comme ci-dessus
git add app/services/pdf_processing.py app/routers/pdf_tools.py requirements.txt
git commit -m "fix(pdf): real compression, ZIP output, explicit conversion errors"
git push
```

Le Space reconstruit son image automatiquement.

### 4. Vérifier

```bash
# Doit renvoyer {"status":"ok"} sans "db" ni "db_type"
curl https://tuilter-bg-remover-api.hf.space/health

# to-image sur un PDF de 3 pages doit renvoyer une archive ZIP
curl -s -X POST https://pdf.warult-tools.com/api/pdf/to-image \
     -F "file=@rapport.pdf" -F "format=png" -F "dpi=150" \
     -D - -o /dev/null | grep -i content-type
# Attendu : application/zip
```

## Points d'attention

- **`/health` ne doit plus mentionner la base de données.** Le service PDF corrigé
  n'en utilise pas ; la base de données du Space reste utilisée par ses autres
  domaines (comptes, facturation) et n'est pas concernée.
- **Le `Dockerfile` du Space n'a pas besoin de changer.** Sauf si vous voulez
  retirer `poppler-utils` : il n'est plus nécessaire, mais le retirer est
  facultatif et sans risque fonctionnel.
- **Les limites de débit restent inchangées** (`20/minute`, `10/minute` codés en
  dur). Les rendre configurables est possible mais n'était pas l'objet de ce
  correctif — je ne touche pas au reste, comme convenu.

## Ce que ce correctif ne fait pas

- Il ne modifie **aucune** autre route (`remove-bg`, `tools/*`, `auth/*`,
  `billing/*`).
- Il ne touche ni à la base de données, ni à Stripe, ni à l'authentification.
- Il ne change pas le `Dockerfile`.
