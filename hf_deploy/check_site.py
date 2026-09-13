"""Verification finale complete de pdf.warult-tools.com.

Couvre ce qui n'avait PAS encore ete verifie :
  - les 10 pages d'outils (statut, titre, contenu attendu)
  - les pages annexes (404 attendus)
  - les ressources statiques (polices, icones, sitemap)
  - les metadonnees (canoniques, og, description)
  - l'absence de residus de l'ancienne version
"""
import re
import urllib.error
import urllib.request

BASE = "https://pdf.warult-tools.com"
OK, KO = [], []


def get(chemin: str):
    req = urllib.request.Request(
        BASE + chemin,
        headers={"User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache"},
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return r.status, r.read().decode("utf-8", "replace"), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, "", dict(e.headers)
    except Exception as e:
        return None, f"{type(e).__name__}", {}


def check(label, condition, detail=""):
    (OK if condition else KO).append(label)
    print(f"  [{'OK ' if condition else 'ECHEC'}] {label}{(' — ' + detail) if detail else ''}")


OUTILS = {
    "merge": "Fusionner des PDF",
    "split": "Découper un PDF",
    "compress": "Compresser un PDF",
    "to-image": "Convertir un PDF en images",
    "from-images": "Assembler des images en PDF",
    "protect": "Protéger un PDF",
    "unprotect": "Déverrouiller un PDF",
    "watermark": "Ajouter un filigrane",
    "rotate": "Pivoter des pages",
    "crop": "Recadrer des pages",
}

print("=== 1. les 10 pages d'outils ===")
for slug, titre in OUTILS.items():
    status, html, _ = get(f"/tools/{slug}")
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    titre_page = re.search(r"<title>(.*?)</title>", html, re.S)
    titre_ok = h1 and titre in re.sub(r"<[^>]+>", "", h1.group(1))
    check(f"/tools/{slug}", status == 200 and titre_ok,
          f"{status} | {titre_page.group(1)[:38] if titre_page else '?'}")

print("\n=== 2. page d'accueil ===")
status, html, _ = get("/")
check("accueil 200", status == 200, str(status))
check("titre a jour", "dix opérations sur un document" in html)
check("les 10 outils listes", all(s in html for s in OUTILS))
check("aucun emoji de l'ancienne version", not any(e in html for e in ["\U0001F4C4", "\U0001F5DC", "\U0001F510", "\U0001F4CB"]))

print("\n=== 3. pages qui doivent avoir disparu ===")
for chemin in ("/pricing",):
    status, _, _ = get(chemin)
    check(f"{chemin} -> 404", status == 404, str(status))

print("\n=== 4. ressources statiques ===")
for chemin, attendu in [
    ("/favicon.ico", 200),
    ("/icon.svg", 200),
    ("/robots.txt", 200),
    ("/sitemap.xml", 200),
]:
    status, _, _ = get(chemin)
    check(chemin, status == attendu, str(status))

print("\n=== 5. polices servies par Next ===")
status, html, _ = get("/")
polices = re.findall(r'href="([^"]*\.woff2[^"]*)"', html)
if not polices:
    polices = re.findall(r"href=\"(/_next/static/media/[^\"]+)\"", html)
check(f"{len(polices)} fichier(s) de police reference(s)", len(polices) >= 2, str(len(polices)))
if polices:
    p_status, _, _ = get(polices[0])
    check("premiere police accessible", p_status == 200, str(p_status))

print("\n=== 6. metadonnees de l'accueil ===")
check("canonique presente", 'rel="canonical"' in html)
check("og:url present", "og:url" in html)
check("og:site_name present", "og:site_name" in html)
check("description presente", 'name="description"' in html)
check("lang=fr", 'lang="fr"' in html)

print("\n=== 7. sitemap ===")
status, sitemap, _ = get("/sitemap.xml")
urls = re.findall(r"<loc>(.*?)</loc>", sitemap)
check(f"{len(urls)} URL declarees", len(urls) == 11, str(len(urls)))
manquants = [s for s in OUTILS if not any(s in u for u in urls)]
check("les 10 outils y figurent", not manquants, str(manquants or "tous presents"))

print("\n=== 8. robots.txt ===")
status, robots, _ = get("/robots.txt")
check("exploration autorisee", "Allow: /" in robots)
check("api exclue", "Disallow: /api/" in robots)
check("sitemap declare", "Sitemap:" in robots)

print(f"\n{'=' * 60}")
print(f"BILAN : {len(OK)} OK, {len(KO)} ECHEC")
if KO:
    print("\nA CORRIGER :")
    for item in KO:
        print(f"  - {item}")
