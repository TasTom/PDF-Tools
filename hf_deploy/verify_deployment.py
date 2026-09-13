"""Verifie que le paquet du Space se comporte correctement une fois deploye.

On teste le paquet EXACT qui sera publie : meme Dockerfile, meme contenu, meme
port. Si tout passe ici, le Space fonctionnera a l'identique.

Le script S'INSCRIT d'abord : depuis l'ajout des comptes, les dix outils exigent
un jeton Bearer. Sans cette etape, toutes les verifications suivantes mesureraient
des 401 et le script conclurait a tort que le deploiement est casse.

Usage :
    python hf_deploy/verify_deployment.py https://warult47-pdf-tools-api.hf.space
    python hf_deploy/verify_deployment.py https://pdf.warult-tools.com

Le compte cree reste en base. C'est assume : le supprimer demanderait un acces
base que ce script n'a pas, et un compte nomme `verif-*` se repere au premier
coup d'oeil dans la console.
"""
import io
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
import zipfile

from PIL import Image
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8200"
resultats = []
JETON = ""


def pdf(pages=3, label="DOC"):
    b = io.BytesIO()
    c = canvas.Canvas(b, pagesize=A4)
    for i in range(pages):
        c.setFont("Helvetica-Bold", 24)
        c.drawString(70, 740, f"{label} page {i + 1}")
        for ligne in range(10):
            c.setFont("Helvetica", 12)
            c.drawString(60, 690 - ligne * 26, f"Ligne {ligne + 1}")
        c.showPage()
    c.save()
    return b.getvalue()


def scan(pages=1):
    b = io.BytesIO()
    c = canvas.Canvas(b, pagesize=A4)
    for _ in range(pages):
        img = Image.frombytes("RGB", (1240, 1754), os.urandom(1240 * 1754 * 3))
        enc = io.BytesIO()
        img.save(enc, format="JPEG", quality=90)
        enc.seek(0)
        c.drawImage(ImageReader(enc), 20, 20, width=555, height=802)
        c.showPage()
    c.save()
    return b.getvalue()


def post(path, files, fields=None):
    boundary = "----t" + uuid.uuid4().hex
    body = b""
    for k, v in (fields or {}).items():
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    for name, fname, content in files:
        body += (
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; '
            f'filename="{fname}"\r\nContent-Type: application/octet-stream\r\n\r\n'
        ).encode() + content + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(BASE + path, data=body, method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Authorization": f"Bearer {JETON}",
        })
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def post_anon(path, files, fields=None):
    """Meme appel, sans jeton : sert a verifier que l'acces est bien refuse."""
    global JETON
    garde, JETON = JETON, ""
    try:
        return post(path, files, fields)
    finally:
        JETON = garde


def appel_json(path, charge):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(charge).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, {"detail": e.read().decode()[:200]}


def inscrire() -> int:
    """Cree un compte de verification et garde son jeton."""
    global JETON
    identifiant = uuid.uuid4().hex[:10]
    statut, corps = appel_json("/api/auth/register", {
        "email": f"verif-{identifiant}@example.com",
        "username": f"verif{identifiant}",
        "password": "MotDePasse1",
    })
    if statut == 201:
        JETON = corps["access_token"]
    else:
        print(f"    detail : {corps.get('detail')}")
    return statut


def ok(label, condition, detail=""):
    resultats.append(bool(condition))
    print(f"  [{'OK ' if condition else 'ECHEC'}] {label}{(' — ' + detail) if detail else ''}")


doc3 = pdf(3, "BASE")

print("=== sante ===")
# /health n'est PAS sous /api/ : il n'est donc pas relaye quand BASE est un
# domaine qui ne reecrit que /api/* (cas de pdf.warult-tools.com). On le tente,
# et son absence n'est pas un echec.
try:
    with urllib.request.urlopen(BASE + "/health", timeout=30) as r:
        corps = r.read().decode()
        print(f"  /health -> {r.status} {corps}")
except urllib.error.HTTPError as e:
    if e.code == 404:
        print("  /health -> 404 (normal si BASE ne reecrit que /api/* ; tester le Space directement)")
    else:
        print(f"  /health -> HTTP {e.code}")
except Exception as exc:
    print(f"  /health -> {type(exc).__name__}")

print("\n=== compte ===")
# Sans jeton, tout ce qui suit ne mesurerait que des 401.
refus = post_anon("/api/pdf/rotate", [("file", "a.pdf", doc3)], {"angle": "90"})
ok("un visiteur sans compte est refuse", refus[0] == 401, f"HTTP {refus[0]}")

statut = inscrire()
ok("inscription acceptee", statut == 201, f"HTTP {statut}")
if not JETON:
    print("\nAucun jeton : la suite ne mesurerait que des 401. Arret.")
    sys.exit(1)

print("\n=== merge ===")
s, data, _ = post("/api/pdf/merge", [
    ("files", "a.pdf", pdf(3, "AAA")),
    ("files", "b.pdf", pdf(1, "BBB")),
])
pages = len(PdfReader(io.BytesIO(data)).pages) if data[:4] == b"%PDF" else -1
textes = [p.extract_text() for p in PdfReader(io.BytesIO(data)).pages] if pages > 0 else []
ok("4 pages dans l'ordre", s == 200 and pages == 4 and "AAA page 1" in textes[0], f"{pages} pages")

print("\n=== split ===")
s, data, h = post("/api/pdf/split", [("file", "a.pdf", doc3)])
if zipfile.is_zipfile(io.BytesIO(data)):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        noms = z.namelist()
    ok("archive ZIP de 3 pages", noms == ["page_1.pdf", "page_2.pdf", "page_3.pdf"], str(noms))
else:
    ok("archive ZIP", False, h.get("Content-Type", "?"))

s, data, _ = post("/api/pdf/split", [("file", "a.pdf", doc3)], {"pages": "1,3"})
if zipfile.is_zipfile(io.BytesIO(data)):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        noms = z.namelist()
    ok("numerotation d'origine conservee", noms == ["page_1.pdf", "page_3.pdf"], str(noms))

s, data, _ = post("/api/pdf/split", [("file", "a.pdf", doc3)], {"pages": "2"})
ok("page unique -> PDF direct", s == 200 and data[:4] == b"%PDF")

print("\n=== compress (chaque niveau agit) ===")
sc = scan()
print(f"  entree : {len(sc) / 1024 / 1024:.2f} Mo")
tailles = {}
for niveau in ("low", "medium", "high"):
    s, data, _ = post("/api/pdf/compress", [("file", "s.pdf", sc)], {"quality": niveau})
    gain = 1 - len(data) / len(sc) if s == 200 else 0
    tailles[niveau] = len(data)
    ok(f"{niveau:6} -> -{gain:.0%}", s == 200 and gain > 0.1, f"{len(data) / 1024 / 1024:.2f} Mo")
ok("niveaux ordonnes", tailles["low"] < tailles["medium"] < tailles["high"])

print("\n=== to-image (rendu reel) ===")
s, data, h = post("/api/pdf/to-image", [("file", "a.pdf", doc3)], {"format": "png", "dpi": "150"})
if s == 200 and zipfile.is_zipfile(io.BytesIO(data)):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        rendu = Image.open(io.BytesIO(z.read("page_1.png"))).convert("L")
    hist = rendu.histogram()
    encre = sum(hist[:200]) / sum(hist)
    ok(f"page non vide ({encre:.2%} d'encre)", encre > 0.002, str(rendu.size))
else:
    ok("conversion en images", False, h.get("Content-Type", "?"))

s, _, _ = post("/api/pdf/to-image", [("file", "f.pdf", b"pas un PDF")], {"format": "png", "dpi": "150"})
ok("fichier corrompu refuse en 422", s == 422, f"HTTP {s}")

print("\n=== watermark ===")
s, data, _ = post("/api/pdf/watermark", [("file", "a.pdf", doc3)], {"text": "CONFIDENTIEL", "opacity": "0.5"})
textes = [p.extract_text() for p in PdfReader(io.BytesIO(data)).pages] if s == 200 else []
ok("texte pose sur les 3 pages", len(textes) == 3 and all("CONFIDENTIEL" in t for t in textes))

print("\n=== protect / unprotect ===")
s, protege, _ = post("/api/pdf/protect", [("file", "a.pdf", doc3)], {"password": "secret123"})
ok("chiffre", s == 200 and PdfReader(io.BytesIO(protege)).is_encrypted)
s, ouvert, _ = post("/api/pdf/unprotect", [("file", "p.pdf", protege)], {"password": "secret123"})
ok("dechiffre", s == 200 and len(PdfReader(io.BytesIO(ouvert)).pages) == 3)
s, _, _ = post("/api/pdf/unprotect", [("file", "p.pdf", protege)], {"password": "mauvais"})
ok("mauvais mot de passe refuse", s == 400, f"HTTP {s}")

print("\n=== rotate / crop ===")
s, data, _ = post("/api/pdf/rotate", [("file", "a.pdf", doc3)], {"angle": "90", "pages": "2"})
rots = [int(p.get("/Rotate", 0)) for p in PdfReader(io.BytesIO(data)).pages] if s == 200 else []
ok("seule la page 2 tourne", rots == [0, 90, 0], str(rots))

s, data, _ = post("/api/pdf/crop", [("file", "a.pdf", doc3)], {"x": "0", "y": "0", "w": "300", "h": "400"})
p = PdfReader(io.BytesIO(data)).pages[0] if s == 200 else None
ok("boite 300x400", p is not None and abs(float(p.mediabox.width) - 300) < 1)

print("\n=== from-images ===")
def png(couleur):
    b = io.BytesIO()
    Image.new("RGB", (300, 200), couleur).save(b, format="PNG")
    return b.getvalue()

s, data, _ = post("/api/pdf/from-images", [
    ("files", "un.png", png((200, 40, 40))),
    ("files", "deux.png", png((40, 200, 40))),
])
ok("2 pages creees", s == 200 and len(PdfReader(io.BytesIO(data)).pages) == 2)

print(f"\n=== BILAN : {sum(resultats)}/{len(resultats)} verifications reussies ===")
sys.exit(0 if all(resultats) else 1)
