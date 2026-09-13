"""Verifie que le correctif A est bien actif en production.

C'est LE test qui distingue l'ancienne de la nouvelle version :

- `to-image` sur un PDF de 3 pages renvoyait un seul PNG nomme `page_1.png`.
  La version corrigee renvoie une archive ZIP `pages.zip`.
- `compress` ne reduisait rien (0 %) sur un PDF d'images, avec le meme resultat
  aux trois niveaux. La version corrigee reduit, et differemment par niveau.
"""
import io
import sys
import urllib.error
import urllib.request
import uuid
import zipfile

from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://pdf.warult-tools.com"
resultats = []


def pdf(pages=3, label="DOC"):
    b = io.BytesIO()
    c = canvas.Canvas(b, pagesize=A4)
    for i in range(pages):
        c.setFont("Helvetica-Bold", 24)
        c.drawString(70, 740, f"{label} page {i + 1}")
        c.showPage()
    c.save()
    return b.getvalue()


def scan(pages=1):
    b = io.BytesIO()
    c = canvas.Canvas(b, pagesize=A4)
    for _ in range(pages):
        img = Image.frombytes("RGB", (1240, 1754), __import__("os").urandom(1240 * 1754 * 3))
        enc = io.BytesIO()
        img.save(enc, format="JPEG", quality=90)
        enc.seek(0)
        c.drawImage(ImageReader(enc), 20, 20, width=555, height=802)
        c.showPage()
    c.save()
    return b.getvalue()


def post(path, files, fields=None, base=BASE):
    boundary = "----v" + uuid.uuid4().hex
    body = b""
    for k, v in (fields or {}).items():
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    for name, fname, content in files:
        body += (
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; '
            f'filename="{fname}"\r\nContent-Type: application/octet-stream\r\n\r\n'
        ).encode() + content + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(base + path, data=body, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def ok(label, condition, detail=""):
    resultats.append(bool(condition))
    print(f"  [{'OK ' if condition else 'ECHEC'}] {label}{(' — ' + detail) if detail else ''}")


doc3 = pdf(3, "BASE")

print("=== /health (direct sur le Space) ===")
try:
    with urllib.request.urlopen("https://tuilter-bg-remover-api.hf.space/health", timeout=60) as r:
        corps = r.read().decode()
    print(f"  -> {r.status} {corps}")
    # `db` reste present : ce champ vient de app/main.py, volontairement NON
    # modifie. La base sert encore aux comptes et a la facturation de ce Space.
    # On verifie donc seulement que le service repond.
    ok("service en ligne", r.status == 200 and '"status":"ok"' in corps, corps)
except Exception as exc:
    print(f"  echec : {exc}")
    ok("sante", False)

print("\n=== to-image : PNG unique (ancien) ou ZIP (nouveau) ? ===")
s, data, h = post("/api/pdf/to-image", [("file", "a.pdf", doc3)], {"format": "png", "dpi": "150"})
ct = h.get("Content-Type", "?")
print(f"  HTTP {s}  Content-Type: {ct}")
if zipfile.is_zipfile(io.BytesIO(data)):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        noms = z.namelist()
    print(f"  -> ARCHIVE ZIP : {noms}")
    ok("CORRECTIF ACTIF : archive ZIP de 3 pages", noms == ["page_1.png", "page_2.png", "page_3.png"])
else:
    print(f"  -> reponse non-archive ({len(data)} octets) : la version ANCIENNE est encore servie")
    ok("CORRECTIF ACTIF", False, "toujours l'ancienne version")

print("\n=== compress : les niveaux agissent-ils differemment ? ===")
sc = scan()
print(f"  entree : {len(sc) / 1024 / 1024:.2f} Mo")
tailles = {}
for niveau in ("low", "medium", "high"):
    s, data, _ = post("/api/pdf/compress", [("file", "s.pdf", sc)], {"quality": niveau})
    gain = 1 - len(data) / len(sc) if s == 200 else 0
    tailles[niveau] = len(data)
    print(f"  {niveau:6} -> {len(data) / 1024 / 1024:5.2f} Mo  ({gain:+.0%})")
ok("compression effective sur medium et high",
   tailles["medium"] < len(sc) - 1000 and tailles["high"] < len(sc) - 1000)
ok("niveaux ordonnes", tailles["low"] <= tailles["medium"] <= tailles["high"])

print("\n=== to-image sur fichier corrompu ===")
s, data, _ = post("/api/pdf/to-image", [("file", "f.pdf", b"pas un PDF")], {"format": "png", "dpi": "150"})
print(f"  HTTP {s} -> {data[:100].decode('utf-8', 'replace')}")
ok("refus explicite (422)", s == 422, f"HTTP {s}")

print(f"\n=== BILAN : {sum(resultats)}/{len(resultats)} ===")
sys.exit(0 if all(resultats) else 1)
