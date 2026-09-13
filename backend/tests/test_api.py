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

import pytest
from PIL import Image
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from starlette.testclient import TestClient

from app.config import settings
from app.main import app, limiter

PDF_MIME = "application/pdf"


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """Remet les compteurs a zero : sans cela, les tests dependraient de l'ordre.

    Le limiteur compte par adresse IP et le TestClient est toujours la meme :
    sans reinitialisation, le test de limite ferait echouer tous les suivants.
    """
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


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
    assert "merged.pdf" in response.headers["content-disposition"]

    # Le contenu doit suivre l'ordre d'envoi : A1, A2, puis B1. Sans cette
    # verification, une inversion d'ordre passerait inapercue.
    reader = PdfReader(io.BytesIO(response.content))
    texts = [page.extract_text() for page in reader.pages]
    assert "AAA page 1" in texts[0]
    assert "AAA page 2" in texts[1]
    assert "BBB page 1" in texts[2]


def test_merge_needs_at_least_two_files(client):
    response = client.post("/api/pdf/merge", files=[("files", as_pdf(make_pdf(1), "a.pdf"))])
    assert response.status_code == 400
    assert "2 fichiers" in response.json()["detail"]


def test_split_returns_zip_named_after_original_pages(client):
    response = client.post("/api/pdf/split", files={"file": as_pdf(make_pdf(3))})

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "pages.zip" in response.headers["content-disposition"]

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

def test_rate_limit_returns_429_past_the_threshold(client):
    """La limite annoncee dans le README doit etre vraiment appliquee."""
    payload = {"file": as_pdf(make_pdf(1))}
    codes = [
        client.post("/api/pdf/crop", files=payload, data={"x": "0", "y": "0", "w": "595", "h": "842"}).status_code
        for _ in range(21)
    ]

    allowed = int(settings.RATE_LIMIT_LIGHT.split("/")[0])
    assert codes[:allowed] == [200] * allowed
    assert codes[allowed] == 429


def test_rate_limit_counts_per_forwarded_client_not_per_proxy(client):
    """Deux clients distincts derriere un meme proxy ne partagent pas de compteur.

    Ce test vient d'un defaut constate EN PRODUCTION : la cle etait
    `request.client.host` (l'adresse du proxy), qui variait d'une requete a
    l'autre. Le compteur se repartissait donc sur plusieurs cles et la limite
    effective etait multipliee d'autant — mesure : 100 appels d'affilee ne
    declenchaient que 45 refus.

    Le comportement corrige est verifie sur DEUX aspects :
    - des `X-Forwarded-For` differents sont comptes separement ;
    - un `X-Forwarded-For` qui varie ne fait PAS repartir le compteur.
    """
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
