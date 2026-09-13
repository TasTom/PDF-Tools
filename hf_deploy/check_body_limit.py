"""Teste la limite de taille d'envoi REELLE de Vercel.

Vercel plafonne le corps des requetes a 4,5 Mo pour les fonctions serverless.
Notre rewrite /api/* passe par la, donc notre limite annoncee de 50 Mo pourrait
ne pas s'appliquer en production. A verifier, pas a supposer.
"""
import io
import math
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://pdf.warult-tools.com"


def bruit() -> bytes:
    img = Image.frombytes("RGB", (800, 800), os.urandom(800 * 800 * 3))
    b = io.BytesIO()
    img.save(b, format="JPEG", quality=80)
    return b.getvalue()


PAGE = bruit()
print(f"une page de bruit = {len(PAGE) / 1024:.0f} Ko")


def scan(cible_mo: float) -> bytes:
    pages = max(1, math.ceil(cible_mo / (len(PAGE) / 1024 / 1024)))
    b = io.BytesIO()
    c = canvas.Canvas(b, pagesize=A4)
    for _ in range(pages):
        c.drawImage(ImageReader(io.BytesIO(bruit())), 40, 60, width=515, height=760)
        c.showPage()
    c.save()
    return b.getvalue()


def post(content: bytes) -> tuple:
    boundary = "----big" + uuid.uuid4().hex
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
        f'filename="gros.pdf"\r\nContent-Type: application/pdf\r\n\r\n'
    ).encode() + content + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        BASE + "/api/pdf/compress", data=body, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return r.status, len(r.read()), time.time() - t0, ""
    except urllib.error.HTTPError as e:
        corps = e.read(300).decode("utf-8", "replace")
        return e.code, 0, time.time() - t0, corps
    except Exception as e:
        return None, 0, time.time() - t0, f"{type(e).__name__}: {str(e)[:80]}"


print(f"\n=== envois vers {BASE} ===")
print(f"  {'taille':>10}  {'resultat':<34} duree")
for cible in (2, 6, 13, 30, 48, 55):
    data = scan(cible)
    taille = len(data) / 1024 / 1024
    code, recu, duree, err = post(data)
    if code == 200:
        verdict = f"HTTP 200 -> {recu / 1024 / 1024:.2f} Mo"
    elif code is None:
        verdict = f"ECHEC RESEAU : {err}"
    else:
        verdict = f"HTTP {code} : {err[:60]}"
    print(f"  {taille:8.2f} Mo  {verdict:<34} {duree:.1f} s")

print("\n=== lecture ===")
print("  Sous 4,5 Mo : Vercel doit laisser passer.")
print("  Au-dessus  : si HTTP 413 apparait, c'est la limite de Vercel, pas la notre.")
