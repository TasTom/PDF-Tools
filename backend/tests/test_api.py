"""Tests d'integration de l'API PDF Tools.

Ces tests tournent EN MEMOIRE via le TestClient de Starlette : aucun serveur a
lancer. Ils figent les comportements corriges a la main, qui autrement ne se
reverifieraient jamais :

- `split` et `to-image` renvoient une archive ZIP des qu'il y a plusieurs
  fichiers, et nomment chaque page d'apres son numero d'origine ;
- `to-image` rend reellement les pages (pypdfium2) et echoue franchement sur un
  fichier corrompu, au lieu de produire une image blanche indiscernable d'un
  succes ;
- `compress` reduit vraiment la taille et ne renvoie jamais plus gros que
  l'entree ;
- le limiteur de debit repond 429.

Lancer depuis `backend/` :
    .venv\\Scripts\\python.exe -m pytest
"""
import io
import os
import zipfile
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt
from PIL import Image
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.config import settings
from app.rate_limit import limiter

PDF_MIME = "application/pdf"

# Les fixtures `client` (authentifie), `anon_client` et la remise a zero des
# compteurs vivent dans `conftest.py`. Ne PAS les redefinir ici : une fixture
# locale masque celle de conftest, et le client perdrait son authentification.


# --------------------------------------------------------------------------
# Fabriques de documents de test
# --------------------------------------------------------------------------

def make_pdf(pages: int = 3, label: str = "DOC") -> bytes:
    """PDF de texte, avec un contenu verifiable a l'oeil."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    for index in range(pages):
        c.setFont("Helvetica-Bold", 26)
        c.drawString(70, 740, f"{label} page {index + 1}")
        c.setFont("Helvetica", 12)
        for line in range(20):
            c.drawString(60, 700 - line * 20, f"Ligne {line + 1} de la page {index + 1}")
        c.showPage()
    c.save()
    return buffer.getvalue()


def make_noisy_pdf(pages: int = 2, side: int = 1400) -> bytes:
    """PDF d'images bruitees : de la matiere pour la compression.

    1400 x 1400 = 1,96 Mpx, soit AU-DESSUS du plafond de `low` (1 Mpx) et en
    dessous de celui de `high` (6 Mpx). Ce choix est volontaire : il rend le
    niveau de qualite observable, ce qui ne serait pas le cas avec une image
    deja petite (aucune recompression) ou enorme (tous les niveaux agiraient).
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    for _ in range(pages):
        image = Image.frombytes("RGB", (side, side), os.urandom(side * side * 3))
        encoded = io.BytesIO()
        image.save(encoded, format="JPEG", quality=90)
        encoded.seek(0)
        c.drawImage(ImageReader(encoded), 40, 60, width=515, height=760)
        c.showPage()
    c.save()
    return buffer.getvalue()


def make_scan_pdf(pages: int = 1) -> bytes:
    """Simule un scan A4 a 150 ppp : 1240 x 1754 px, soit 2,17 Mpx.

    Cette resolution est choisie parce qu'elle est la plus courante en pratique
    ET qu'elle tombe JUSTE SOUS le plafond de « medium » (2,5 Mpx). Un test qui
    n'utiliserait qu'une tres grande image ne verifierait donc pas le cas le plus
    frequent, et c'est precisement celui qui etait casse.
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    for _ in range(pages):
        image = Image.frombytes("RGB", (1240, 1754), os.urandom(1240 * 1754 * 3))
        encoded = io.BytesIO()
        image.save(encoded, format="JPEG", quality=90)
        encoded.seek(0)
        c.drawImage(ImageReader(encoded), 20, 20, width=555, height=802)
        c.showPage()
    c.save()
    return buffer.getvalue()


def make_png(width: int = 400, height: int = 300, color=(30, 60, 120)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, format="PNG")
    return buffer.getvalue()


def as_pdf(data: bytes, name: str = "fichier.pdf"):
    return (name, data, PDF_MIME)


def in_zip(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def page_count(data: bytes) -> int:
    return len(PdfReader(io.BytesIO(data)).pages)


def looks_like_png(data: bytes) -> bool:
    return data[:8] == b"\x89PNG\r\n\x1a\n"


def ink_ratio(data: bytes) -> float:
    """Part de pixels non blancs : detecte une page vide, meme silencieuse.

    Passe par l'histogramme plutot que par `getdata`, deprecie dans Pillow 12.
    """
    image = Image.open(io.BytesIO(data)).convert("L")
    histogram = image.histogram()  # 256 classes de gris
    dark = sum(histogram[:200])  # tout ce qui est plus sombre que 200/255
    return dark / sum(histogram)


# --------------------------------------------------------------------------
# Sante et rejet des entrees invalides
# --------------------------------------------------------------------------

def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_root_announces_service(client):
    body = client.get("/").json()
    assert body["service"] == "PDF Tools API"
    assert "version" in body


def test_rejects_unsupported_extension(client):
    response = client.post("/api/pdf/rotate", files={"file": ("notes.txt", b"texte", "text/plain")})
    assert response.status_code == 400
    assert "Format non supporté" in response.json()["detail"]


def test_rejects_file_over_the_limit(client, monkeypatch):
    # On abaisse la limite plutot que de fabriquer 51 Mo : le test reste rapide
    # et verifie la meme branche de code.
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 0)
    response = client.post("/api/pdf/rotate", files={"file": as_pdf(make_pdf(1))})
    assert response.status_code == 400
    assert "trop volumineux" in response.json()["detail"]


# --------------------------------------------------------------------------
# Les dix outils
# --------------------------------------------------------------------------

def test_merge_combines_pages_in_order(client):
    response = client.post(
        "/api/pdf/merge",
        files=[
            ("files", as_pdf(make_pdf(2, "AAA"), "a.pdf")),
            ("files", as_pdf(make_pdf(1, "BBB"), "b.pdf")),
        ],
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == PDF_MIME
    assert page_count(response.content) == 3
    # Le nom du resultat reprend celui du PREMIER fichier envoye.
    assert "a-fusionne.pdf" in response.headers["content-disposition"]

    # Le contenu doit suivre l'ordre d'envoi : A1, A2, puis B1. Sans cette
    # verification, une inversion d'ordre passerait inapercue.
    reader = PdfReader(io.BytesIO(response.content))
    texts = [page.extract_text() for page in reader.pages]
    assert "AAA page 1" in texts[0]
    assert "AAA page 2" in texts[1]
    assert "BBB page 1" in texts[2]


def test_every_tool_names_its_output_after_the_input(client):
    """Le fichier renvoye porte le nom de celui envoye, pas « output.pdf ».

    Repondre systematiquement « compressed.pdf » obligeait l'utilisateur a
    renommer le resultat a la main, alors que le nom d'origine est justement
    l'information qu'il connait deja.

    Les cas choisis verifient aussi la mise en forme : espace, accent, et
    absence d'extension exploitable. Un espace ou un accent laisse tel quel
    casserait l'en-tete `Content-Disposition`.
    """
    cas = (
        ("compress", {"file": as_pdf(make_pdf(1), "facture-mars.pdf")},
         {"quality": "medium"}, "facture-mars-compresse.pdf"),
        ("rotate", {"file": as_pdf(make_pdf(1), "scan 2026.pdf")},
         {"angle": "90"}, "scan-2026-pivote.pdf"),
        ("protect", {"file": as_pdf(make_pdf(1), "ete 2026.pdf")},
         {"password": "secret"}, "ete-2026-protege.pdf"),
    )

    for outil, fichiers, donnees, attendu in cas:
        reponse = client.post(f"/api/pdf/{outil}", files=fichiers, data=donnees)
        assert reponse.status_code == 200, outil
        entete = reponse.headers["content-disposition"]
        assert attendu in entete, f"{outil} : {entete}"
        # Exactement deux guillemets : un nom mal echappe scinderait l'en-tete.
        assert entete.count('"') == 2, entete
        assert " " not in entete.split("filename=")[-1], f"espace laisse dans le nom : {entete}"


def test_an_unusable_name_falls_back_to_a_neutral_one(client):
    """Un nom reduit a neant ne doit pas produire « -compresse.pdf ».

    « ***.pdf » passe la validation (l'extension est bonne) mais son radical ne
    contient aucun caractere conservable : il ne doit pas rester de tiret orphelin.
    """
    reponse = client.post(
        "/api/pdf/compress",
        files={"file": as_pdf(make_pdf(1), "***.pdf")},
        data={"quality": "medium"},
    )
    assert reponse.status_code == 200
    assert "document-compresse.pdf" in reponse.headers["content-disposition"]


def test_merge_needs_at_least_two_files(client):
    response = client.post("/api/pdf/merge", files=[("files", as_pdf(make_pdf(1), "a.pdf"))])
    assert response.status_code == 400
    assert "2 fichiers" in response.json()["detail"]


def test_split_returns_zip_named_after_original_pages(client):
    response = client.post("/api/pdf/split", files={"file": as_pdf(make_pdf(3))})

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "fichier-pages.zip" in response.headers["content-disposition"]

    pages = in_zip(response.content)
    assert list(pages) == ["page_1.pdf", "page_2.pdf", "page_3.pdf"]
    # Chaque page extraite doit etre un PDF valide d'une seule page.
    for content in pages.values():
        assert page_count(content) == 1


def test_split_keeps_original_page_numbers_when_selecting(client):
    response = client.post(
        "/api/pdf/split",
        files={"file": as_pdf(make_pdf(5))},
        data={"pages": "1,3"},
    )
    # La page 3 doit rester `page_3`, pas devenir `page_2`.
    assert list(in_zip(response.content)) == ["page_1.pdf", "page_3.pdf"]


def test_split_single_page_returns_a_pdf_not_an_archive(client):
    response = client.post(
        "/api/pdf/split",
        files={"file": as_pdf(make_pdf(4))},
        data={"pages": "2"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == PDF_MIME
    assert response.content[:4] == b"%PDF"


def test_compress_shrinks_an_image_pdf(client):
    original = make_noisy_pdf()
    response = client.post(
        "/api/pdf/compress",
        files={"file": as_pdf(original)},
        data={"quality": "low"},
    )

    assert response.status_code == 200
    assert page_count(response.content) == 2
    reduction = 1 - len(response.content) / len(original)
    assert reduction > 0.3, f"compression insuffisante : {reduction:.1%}"


def test_compress_quality_level_changes_the_result(client):
    """Sans quoi le selecteur affiche dans l'interface serait un mensonge."""
    original = make_noisy_pdf()
    light = client.post(
        "/api/pdf/compress", files={"file": as_pdf(original)}, data={"quality": "low"}
    ).content
    heavy = client.post(
        "/api/pdf/compress", files={"file": as_pdf(original)}, data={"quality": "high"}
    ).content
    assert len(light) < len(heavy)


def test_every_compress_level_shrinks_a_typical_scan(client):
    """Chaque niveau doit agir sur un scan A4 a 150 ppp, y compris celui par defaut.

    Ce test vient d'un defaut reel : l'image d'un scan a 150 ppp (2,17 Mpx) est
    SOUS le plafond de « medium » (2,5 Mpx). Comme seul le redimensionnement
    etait applique et jamais le re-encodage, le niveau par defaut n'avait aucun
    effet sur le document le plus courant — l'utilisateur voyait un fichier
    identique et pouvait croire l'outil casse.
    """
    original = make_scan_pdf()

    sizes = {}
    for level in ("low", "medium", "high"):
        response = client.post(
            "/api/pdf/compress",
            files={"file": as_pdf(original)},
            data={"quality": level},
        )
        assert response.status_code == 200
        sizes[level] = len(response.content)

    for level, size in sizes.items():
        reduction = 1 - size / len(original)
        assert reduction > 0.1, f"niveau {level} : seulement {reduction:.1%} de gain"

    # Les niveaux doivent rester ordonnes, du plus agressif au plus doux.
    assert sizes["low"] < sizes["medium"] < sizes["high"]


def test_compress_never_returns_a_bigger_file(client):
    original = make_pdf(20)
    response = client.post(
        "/api/pdf/compress",
        files={"file": as_pdf(original)},
        data={"quality": "medium"},
    )
    assert response.status_code == 200
    assert len(response.content) <= len(original)


def test_to_image_renders_pages_instead_of_blank_sheets(client):
    response = client.post(
        "/api/pdf/to-image",
        files={"file": as_pdf(make_pdf(3))},
        data={"format": "png", "dpi": "150"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    images = in_zip(response.content)
    assert list(images) == ["page_1.png", "page_2.png", "page_3.png"]

    with Image.open(io.BytesIO(images["page_1.png"])) as rendered:
        # A4 a 150 ppp : 595 points / 72 * 150 = 1240 px de large.
        assert 1200 < rendered.size[0] < 1290
        assert 1700 < rendered.size[1] < 1790
    # Le vrai piege : une page blanche passerait un test de statut HTTP.
    assert ink_ratio(images["page_1.png"]) > 0.002


def test_to_image_single_page_is_a_direct_png(client):
    response = client.post(
        "/api/pdf/to-image",
        files={"file": as_pdf(make_pdf(1))},
        data={"format": "png", "dpi": "72"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert looks_like_png(response.content)


def test_to_image_jpeg_honours_format(client):
    response = client.post(
        "/api/pdf/to-image",
        files={"file": as_pdf(make_pdf(1))},
        data={"format": "jpeg", "dpi": "72"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.content[:3] == b"\xff\xd8\xff"


def test_to_image_on_corrupt_file_fails_loudly(client):
    """Le comportement d'avant : une image blanche renvoyee en silence."""
    response = client.post(
        "/api/pdf/to-image",
        files={"file": as_pdf(b"ceci n'est pas un PDF")},
        data={"format": "png", "dpi": "150"},
    )
    assert response.status_code == 422
    assert "corrompu" in response.json()["detail"]


def test_from_images_assembles_one_page_per_image(client):
    response = client.post(
        "/api/pdf/from-images",
        files=[
            ("files", ("une.png", make_png(color=(200, 40, 40)), "image/png")),
            ("files", ("deux.png", make_png(color=(40, 200, 40)), "image/png")),
        ],
    )
    assert response.status_code == 200
    assert page_count(response.content) == 2


def test_protect_then_unprotect_round_trip(client):
    original = make_pdf(2)

    protected = client.post(
        "/api/pdf/protect", files={"file": as_pdf(original)}, data={"password": "secret123"}
    )
    assert protected.status_code == 200

    reader = PdfReader(io.BytesIO(protected.content))
    assert reader.is_encrypted

    unlocked = client.post(
        "/api/pdf/unprotect",
        files={"file": as_pdf(protected.content)},
        data={"password": "secret123"},
    )
    assert unlocked.status_code == 200
    assert page_count(unlocked.content) == 2


def test_unprotect_with_wrong_password_is_refused(client):
    protected = client.post(
        "/api/pdf/protect", files={"file": as_pdf(make_pdf(1))}, data={"password": "bon"}
    )
    response = client.post(
        "/api/pdf/unprotect",
        files={"file": as_pdf(protected.content)},
        data={"password": "mauvais"},
    )
    assert response.status_code == 400
    assert "Mot de passe incorrect" in response.json()["detail"]


def test_watermark_is_actually_applied(client):
    """Le filigrane doit etre REELLEMENT pose, pas seulement annonce.

    Compter les pages ne prouverait rien : un filigrane jamais applique
    passerait un test qui se contente de verifier le nombre de pages.
    """
    response = client.post(
        "/api/pdf/watermark",
        files={"file": as_pdf(make_pdf(2))},
        data={"text": "CONFIDENTIEL", "opacity": "0.5"},
    )
    assert response.status_code == 200
    assert page_count(response.content) == 2

    reader = PdfReader(io.BytesIO(response.content))
    texts = [page.extract_text() for page in reader.pages]
    for index, text in enumerate(texts, start=1):
        assert "CONFIDENTIEL" in text, f"filigrane absent de la page {index}"
        # Le contenu d'origine doit avoir survecu a la fusion.
        assert f"DOC page {index}" in text


def test_rotate_keeps_all_pages(client):
    response = client.post(
        "/api/pdf/rotate", files={"file": as_pdf(make_pdf(3))}, data={"angle": "90"}
    )
    assert response.status_code == 200
    assert page_count(response.content) == 3


def test_rotate_can_target_a_subset_of_pages(client):
    response = client.post(
        "/api/pdf/rotate",
        files={"file": as_pdf(make_pdf(4))},
        data={"angle": "180", "pages": "2"},
    )
    assert response.status_code == 200
    assert page_count(response.content) == 4


def test_rotate_applies_the_angle_to_the_right_pages(client):
    """Verifie le SENS et la CIBLE de la rotation, pas seulement le nombre de pages.

    C'est le genre de detail qui change silencieusement lors d'un changement de
    bibliotheque PDF : une inversion de sens produirait toujours un PDF valide.
    """
    response = client.post(
        "/api/pdf/rotate",
        files={"file": as_pdf(make_pdf(3))},
        data={"angle": "90", "pages": "2"},
    )
    assert response.status_code == 200

    rotations = [
        int(page.get("/Rotate", 0)) for page in PdfReader(io.BytesIO(response.content)).pages
    ]
    # Seule la page 2 tourne : les autres restent a 0.
    assert rotations == [0, 90, 0]


def test_crop_applies_the_requested_box(client):
    response = client.post(
        "/api/pdf/crop",
        files={"file": as_pdf(make_pdf(1))},
        data={"x": "0", "y": "0", "w": "300", "h": "400"},
    )
    assert response.status_code == 200

    page = PdfReader(io.BytesIO(response.content)).pages[0]
    assert float(page.mediabox.width) == pytest.approx(300, abs=1)
    assert float(page.mediabox.height) == pytest.approx(400, abs=1)


# --------------------------------------------------------------------------
# Protection anti-abus
# --------------------------------------------------------------------------

def test_rate_limit_returns_429_past_the_threshold(client, monkeypatch):
    """La limite de debit annoncee dans le README doit etre vraiment appliquee.

    Le quota quotidien est releve pour que l'échec n'ait qu'une seule cause
    possible : sans cela, les deux mecanismes refusent au meme moment et le test
    ne prouve rien sur le limiteur.
    """
    monkeypatch.setattr(settings, "DAILY_LIMIT", 10_000)
    payload = {"file": as_pdf(make_pdf(1))}
    codes = [
        client.post("/api/pdf/crop", files=payload, data={"x": "0", "y": "0", "w": "595", "h": "842"}).status_code
        for _ in range(21)
    ]

    allowed = int(settings.RATE_LIMIT_LIGHT.split("/")[0])
    assert codes[:allowed] == [200] * allowed
    assert codes[allowed] == 429


def test_rate_limit_counts_per_forwarded_client_not_per_proxy(client, monkeypatch):
    """Deux clients distincts derriere un meme proxy ne partagent pas de compteur.

    Ce test vient d'un defaut constate EN PRODUCTION : la cle etait
    `request.client.host` (l'adresse du proxy), qui variait d'une requete a
    l'autre. Le compteur se repartissait donc sur plusieurs cles et la limite
    effective etait multipliee d'autant — mesure : 100 appels d'affilee ne
    declenchaient que 45 refus.

    Le comportement corrige est verifie sur DEUX aspects :
    - des `X-Forwarded-For` differents sont comptes separement ;
    - un `X-Forwarded-For` qui varie ne fait PAS repartir le compteur.

    Le quota quotidien est volontairement releve : sans cela, il bloquerait la
    suite du test et on ne saurait pas lequel des deux mecanismes a refuse.
    """
    monkeypatch.setattr(settings, "DAILY_LIMIT", 10_000)
    payload = {"file": as_pdf(make_pdf(1))}
    formulaire = {"x": "0", "y": "0", "w": "595", "h": "842"}
    allowed = int(settings.RATE_LIMIT_LIGHT.split("/")[0])

    # Un client derriere une chaine de proxys : seule la PREMIERE entree compte.
    entete = {"X-Forwarded-For": "203.0.113.7, 70.41.3.18, 150.172.238.178"}
    codes = [
        client.post("/api/pdf/crop", files=payload, data=formulaire, headers=entete).status_code
        for _ in range(allowed + 1)
    ]
    assert codes[:allowed] == [200] * allowed
    assert codes[allowed] == 429, "les entrees ajoutees par les proxys ne doivent pas scinder le compteur"

    limiter.reset()

    # Un AUTRE client ne doit pas heriter du compteur du premier.
    autre = {"X-Forwarded-For": "198.51.100.42"}
    premier = [client.post("/api/pdf/crop", files=payload, data=formulaire, headers=entete).status_code
               for _ in range(allowed)]
    reponse = client.post("/api/pdf/crop", files=payload, data=formulaire, headers=autre)
    assert all(code == 200 for code in premier)
    assert reponse.status_code == 200, "un client different doit avoir son propre compteur"


def test_health_is_not_rate_limited(client):
    """La sonde de deploiement ne doit jamais etre bloquee par le limiteur."""
    assert all(client.get("/health").status_code == 200 for _ in range(30))


# --------------------------------------------------------------------------
# Authentification
# --------------------------------------------------------------------------

def test_tools_require_an_account(raw_client):
    """Les outils ne doivent pas repondre a un visiteur sans compte.

    C'est le changement de fond de cette version : le quota quotidien est indexe
    sur le compte, donc sans compte il n'y a rien a compter.
    """
    for chemin, donnees in [
        ("/api/pdf/merge", {"files": as_pdf(make_pdf(1))}),
        ("/api/pdf/split", {"file": as_pdf(make_pdf(1))}),
        ("/api/pdf/compress", {"file": as_pdf(make_pdf(1))}),
        ("/api/pdf/rotate", {"file": as_pdf(make_pdf(1))}),
        ("/api/pdf/crop", {"file": as_pdf(make_pdf(1))}),
        ("/api/pdf/watermark", {"file": as_pdf(make_pdf(1))}),
    ]:
        reponse = raw_client.post(chemin, files=donnees,
                                  data={"text": "X", "password": "abc", "angle": "90",
                                        "x": "0", "y": "0", "w": "595", "h": "842"})
        assert reponse.status_code == 401, f"{chemin} a repondu {reponse.status_code} sans compte"

    assert raw_client.get("/api/usage").status_code == 401


def test_register_returns_a_usable_token(raw_client):
    identifiant = os.urandom(4).hex()
    reponse = raw_client.post("/api/auth/register", json={
        "email": f"nouveau-{identifiant}@example.com",
        "username": f"nouveau{identifiant}",
        "password": "MotDePasse1",
    })
    assert reponse.status_code == 201, reponse.text
    corps = reponse.json()
    assert corps["token_type"] == "bearer"
    assert corps["user"]["daily_usage"] == 0
    assert corps["user"]["daily_limit"] == settings.DAILY_LIMIT

    # Le jeton doit reellement ouvrir une session.
    profil = raw_client.get("/api/auth/me", headers={"Authorization": f"Bearer {corps['access_token']}"})
    assert profil.status_code == 200
    assert profil.json()["email"] == f"nouveau-{identifiant}@example.com"


def test_register_refuses_a_weak_password(raw_client):
    """Un mot de passe faible doit etre refuse AVANT de creer le compte."""
    for mot_de_passe, raison in [
        ("court1A", "moins de 8 caracteres"),
        ("sansmajuscule1", "aucune majuscule"),
        ("SansChiffre", "aucun chiffre"),
    ]:
        reponse = raw_client.post("/api/auth/register", json={
            "email": f"faible-{os.urandom(3).hex()}@example.com",
            "username": f"faible{os.urandom(3).hex()}",
            "password": mot_de_passe,
        })
        assert reponse.status_code == 422, f"{raison} : accepte a tort"


def test_register_refuses_a_duplicate_email_or_username(raw_client):
    identifiant = os.urandom(4).hex()
    donnees = {
        "email": f"double-{identifiant}@example.com",
        "username": f"double{identifiant}",
        "password": "MotDePasse1",
    }
    assert raw_client.post("/api/auth/register", json=donnees).status_code == 201

    meme_email = {**donnees, "username": f"autre{identifiant}"}
    assert raw_client.post("/api/auth/register", json=meme_email).status_code == 409

    meme_nom = {**donnees, "email": f"autre-{identifiant}@example.com"}
    assert raw_client.post("/api/auth/register", json=meme_nom).status_code == 409


def test_login_accepts_the_right_password_and_refuses_the_wrong_one(raw_client):
    identifiant = os.urandom(4).hex()
    email = f"connexion-{identifiant}@example.com"
    raw_client.post("/api/auth/register", json={
        "email": email,
        "username": f"connexion{identifiant}",
        "password": "MotDePasse1",
    })

    bon = raw_client.post("/api/auth/login", json={"email": email, "password": "MotDePasse1"})
    assert bon.status_code == 200
    assert bon.json()["access_token"]

    faux = raw_client.post("/api/auth/login", json={"email": email, "password": "MauvaisMot1"})
    assert faux.status_code == 401

    inconnu = raw_client.post("/api/auth/login", json={
        "email": f"jamais-vu-{identifiant}@example.com", "password": "MotDePasse1",
    })
    # Meme code que pour un mauvais mot de passe : sinon on peut enumerer les
    # comptes existants.
    assert inconnu.status_code == 401
    assert inconnu.json()["detail"] == faux.json()["detail"]


def test_a_forged_token_is_refused(raw_client):
    for mauvais in ("pas-un-jeton", "eyJhbGciOiJIUzI1NiJ9.faux.signature"):
        reponse = raw_client.get("/api/auth/me", headers={"Authorization": f"Bearer {mauvais}"})
        assert reponse.status_code == 401, f"jeton falsifie accepte : {mauvais}"


def test_a_token_from_another_service_is_refused(raw_client):
    """Un jeton signe avec la MEME cle mais emis par un autre service.

    C'est le cas reel de ce deploiement : le Space a herite de la SECRET_KEY du
    gabarit commun aux deux produits. Sans controle de l'emetteur et du
    destinataire, un compte cree sur l'autre site ouvrirait ici le compte portant
    le meme identifiant, puisque les deux services signent avec la meme cle.
    """
    identifiant = str(abs(hash(("autre-service", settings.SECRET_KEY))) % 10**6)
    email = f"autre-{identifiant}@example.com"
    inscrit = raw_client.post("/api/auth/register", json={
        "email": email, "username": f"autre{identifiant}", "password": "MotDePasse1",
    })
    assert inscrit.status_code == 201
    vrai_jeton = inscrit.json()["access_token"]
    assert raw_client.get("/api/auth/me", headers={"Authorization": f"Bearer {vrai_jeton}"}).status_code == 200

    maintenant = datetime.now(timezone.utc)
    commun = {"sub": inscrit.json()["user"]["id"], "exp": maintenant + timedelta(hours=1), "iat": maintenant}

    sans_audience = jwt.encode(commun, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    audience_etrangere = jwt.encode(
        {**commun, "iss": "warult-tools", "aud": "bg-remover-api"},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    for etranger in (sans_audience, audience_etrangere):
        reponse = raw_client.get("/api/auth/me", headers={"Authorization": f"Bearer {etranger}"})
        assert reponse.status_code == 401, "jeton d'un autre service accepte"


# --------------------------------------------------------------------------
# Quota quotidien
# --------------------------------------------------------------------------

def test_usage_reports_the_quota(client):
    reponse = client.get("/api/usage")
    assert reponse.status_code == 200
    corps = reponse.json()
    assert set(corps) == {"daily_usage", "daily_limit", "remaining"}
    assert corps["daily_limit"] == settings.DAILY_LIMIT
    assert corps["remaining"] == settings.DAILY_LIMIT - corps["daily_usage"]


def test_an_operation_is_counted(client):
    avant = client.get("/api/usage").json()["daily_usage"]
    reponse = client.post("/api/pdf/rotate", files={"file": as_pdf(make_pdf(1))}, data={"angle": "90"})
    assert reponse.status_code == 200
    apres = client.get("/api/usage").json()["daily_usage"]
    assert apres == avant + 1


def test_a_refused_file_does_not_cost_an_operation(client):
    """Valider AVANT de compter : un fichier refuse ne doit pas consommer le quota."""
    avant = client.get("/api/usage").json()["daily_usage"]
    reponse = client.post("/api/pdf/rotate", files={"file": ("notes.txt", b"texte", "text/plain")})
    assert reponse.status_code == 400
    assert client.get("/api/usage").json()["daily_usage"] == avant


def test_the_quota_stops_the_operations(client, monkeypatch):
    """Une fois le quota atteint, l'API refuse et le dit clairement."""
    monkeypatch.setattr(settings, "DAILY_LIMIT", 3)

    for index in range(3):
        reponse = client.post("/api/pdf/rotate", files={"file": as_pdf(make_pdf(1))}, data={"angle": "90"})
        assert reponse.status_code == 200, f"operation {index + 1} refusee a tort"

    refus = client.post("/api/pdf/rotate", files={"file": as_pdf(make_pdf(1))}, data={"angle": "90"})
    assert refus.status_code == 429
    assert "Limite quotidienne" in refus.json()["detail"]

    # Et le refus ne fait pas repartir le compteur.
    assert client.get("/api/usage").json()["remaining"] == 0


def test_the_quota_is_global_not_per_tool(client, monkeypatch):
    """Le quota couvre TOUTES les operations, pas une seule.

    Sinon il suffirait de changer d'outil pour le contourner : c'est justement
    ce que faisait l'ancienne limitation, qui comptait 20/minute par endpoint.
    """
    monkeypatch.setattr(settings, "DAILY_LIMIT", 3)

    # Trois outils DIFFERENTS consomment le meme quota.
    assert client.post("/api/pdf/rotate", files={"file": as_pdf(make_pdf(1))}, data={"angle": "90"}).status_code == 200
    assert client.post("/api/pdf/crop", files={"file": as_pdf(make_pdf(1))},
                       data={"x": "0", "y": "0", "w": "300", "h": "400"}).status_code == 200
    assert client.post("/api/pdf/watermark", files={"file": as_pdf(make_pdf(1))},
                       data={"text": "X", "opacity": "0.3"}).status_code == 200

    # Un quatrieme outil, encore jamais utilise, doit etre refuse.
    quatrieme = client.post("/api/pdf/compress", files={"file": as_pdf(make_pdf(1))},
                            data={"quality": "medium"})
    assert quatrieme.status_code == 429, "le quota ne couvre pas tous les outils"


# --------------------------------------------------------------------------
# Connexion a la base de donnees
# --------------------------------------------------------------------------

def test_the_database_url_receives_an_async_driver():
    """Le secret DATABASE_URL arrive en forme synchrone, le pilote est impose ici.

    Cas reel : le Space a herite d'un `DATABASE_URL` en `postgresql://...`.
    SQLAlchemy en deduisait `psycopg2`, absent de l'image, et le service ne
    demarrait plus — sans que rien n'indique que le prefixe etait en cause.
    """
    from app.database import url_asynchrone

    assert url_asynchrone("postgresql://u:p@h/db") == "postgresql+asyncpg://u:p@h/db"
    assert url_asynchrone("postgres://u:p@h/db") == "postgresql+asyncpg://u:p@h/db"
    assert url_asynchrone("sqlite:///./data/app.db") == "sqlite+aiosqlite:///./data/app.db"
    assert url_asynchrone("  postgresql://u:p@h/db  ") == "postgresql+asyncpg://u:p@h/db"

    # Une URL qui nomme deja son pilote est laissee intacte : la reecrire
    # reviendrait a decider a la place de celui qui l'a remplie.
    for deja in ("postgresql+asyncpg://u:p@h/db", "sqlite+aiosqlite:///./x.db"):
        assert url_asynchrone(deja) == deja


def test_libpq_options_are_removed_from_the_url():
    """asyncpg refuse les options libpq : elles doivent quitter l'URL.

    Deuxieme panne reelle du meme deploiement : l'URL Neon contient
    `?sslmode=require&channel_binding=require`, et asyncpg les transmet comme
    arguments de `connect()`, d'ou
    « connect() got an unexpected keyword argument 'sslmode' ».
    """
    from app.database import _nettoyer

    propre, options = _nettoyer(
        "postgresql+asyncpg://u:p@h/db?sslmode=require&channel_binding=require"
    )
    assert "sslmode" not in propre
    assert "channel_binding" not in propre
    assert options["ssl"] is True
    # Une URL nettoyee ne sert a rien si le mot de passe a disparu au passage.
    assert "p@h" in propre

    # « disable » demande explicitement une connexion en clair.
    _, sans_tls = _nettoyer("postgresql+asyncpg://u:p@h/db?sslmode=disable")
    assert sans_tls["ssl"] is False

    # Les autres parametres ne sont pas touches : ils peuvent porter du sens.
    conserve, _ = _nettoyer("postgresql+asyncpg://u:p@h/db?application_name=pdf")
    assert "application_name=pdf" in conserve

    # SQLite ne passe pas par ce chemin et ressort inchange.
    inchange, vide = _nettoyer("sqlite+aiosqlite:///./data/app.db")
    assert inchange == "sqlite+aiosqlite:///./data/app.db"
    assert vide == {}
