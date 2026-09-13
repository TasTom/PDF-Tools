"""PDF processing service — pypdf, pikepdf, pypdfium2 et reportlab."""
from __future__ import annotations
import io
import logging
import zipfile
from typing import Optional

import pikepdf
import pypdfium2 as pdfium
from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

logger = logging.getLogger("pdf_tools.processing")


class PdfConversionError(RuntimeError):
    """Le PDF fourni n'a pas pu etre rendu en image (fichier illisible)."""


def merge_pdfs(pdf_bytes_list: list[bytes]) -> bytes:
    """Fusionne plusieurs PDF en un seul, dans l'ordre recu.

    pypdf a supprime `PdfMerger` : l'accumulation se fait directement sur un
    `PdfWriter` via `append`, qui accepte un lecteur.
    """
    writer = PdfWriter()
    for pdf_bytes in pdf_bytes_list:
        writer.append(PdfReader(io.BytesIO(pdf_bytes)))
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def split_pdf(pdf_bytes: bytes, pages: Optional[str] = None) -> list[tuple[int, bytes]]:
    """Decoupe un PDF page par page.

    pages : "1,3,5-8", ou None pour toutes les pages.
    Renvoie des couples (numero de page a 1 index, contenu) pour que l'appelant
    puisse nommer chaque fichier d'apres sa page d'origine.
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    total = len(reader.pages)
    
    if pages:
        page_indices = _parse_page_range(pages, total)
    else:
        page_indices = list(range(total))
    
    results = []
    for idx in page_indices:
        writer = PdfWriter()
        writer.add_page(reader.pages[idx])
        output = io.BytesIO()
        writer.write(output)
        results.append((idx + 1, output.getvalue()))
    
    return results


# Niveau demande -> (plafond de pixels par image, qualite JPEG).
# Les plafonds sont donnes en pixels mais correspondent a une resolution sur une
# page A4, qui est ce dont parle l'utilisateur. Le premier chiffre limite la
# DEFINITION, le second la QUALITE : les deux agissent, voir `_shrink_images`.
_COMPRESS_PRESETS: dict[str, tuple[int, int]] = {
    "low": (1_000_000, 55),     # ~100 ppp sur A4
    "medium": (2_500_000, 72),  # ~160 ppp sur A4
    "high": (6_000_000, 85),    # ~250 ppp sur A4
}


def compress_pdf(pdf_bytes: bytes, quality: str = "medium") -> bytes:
    """Reduit la taille d'un PDF : flux recompresses et images re-encodees.

    Le plafond de pixels depend de `quality` (low, medium, high), qui agit donc
    reellement sur le resultat. Le fichier rendu n'est JAMAIS plus gros que
    l'entree : en cas d'echec ou d'absence de gain, l'entree est renvoyee telle
    quelle plutot qu'un resultat degrade.
    """
    max_pixels, jpeg_quality = _COMPRESS_PRESETS.get(quality, _COMPRESS_PRESETS["medium"])

    try:
        with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
            _shrink_images(pdf, max_pixels, jpeg_quality)
            buffer = io.BytesIO()
            pdf.save(
                buffer,
                compress_streams=True,
                recompress_flate=True,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
            )
            candidate = buffer.getvalue()
    except Exception as exc:
        logger.warning("Compression impossible, fichier rendu inchange : %s", exc)
        return pdf_bytes

    return candidate if len(candidate) < len(pdf_bytes) else pdf_bytes


def _is_jpeg(raw) -> bool:
    """Vrai si l'image est deja stockee en JPEG.

    Sert a ne pas convertir une image sans perte (PNG, Flate) en JPEG sans
    raison : le gain n'est pas garanti et des artefacts apparaitraient sur du
    texte.

    Attention a la forme de `/Filter` : c'est soit un nom (`/DCTDecode`), soit un
    TABLEAU de filtres appliques en chaine, et c'est ce que produit un JPEG insere
    par la plupart des outils : `[/ASCII85Decode, /DCTDecode]`. Un `pikepdf.Array`
    n'est pas une `list` Python : tester `isinstance(..., list)` rate le cas le plus
    courant, et un nom n'est pas iterable. D'ou l'iteration avec repli.
    """
    try:
        filters = raw.get("/Filter")
    except Exception:
        return False
    if filters is None:
        return False

    try:
        candidates = list(filters)
    except TypeError:
        candidates = [filters]  # `/Filter` est un nom unique

    return any(str(item) == "/DCTDecode" for item in candidates)


def _shrink_images(pdf: pikepdf.Pdf, max_pixels: int, jpeg_quality: int) -> None:
    """Reduit le poids des images, par deux leviers independants.

    1. **Definition** : une image depassant `max_pixels` est redimensionnee.
    2. **Qualite** : une image deja en JPEG est re-encodee a `jpeg_quality`.

    Le second levier n'est pas un luxe. Un scan A4 a 150 ppp pese 2,17 Mpx, soit
    MOINS que le plafond de « medium » (2,5 Mpx) : avec le seul premier levier, le
    niveau par defaut n'aurait aucun effet sur le cas le plus courant.

    Rien n'est conserve si le resultat n'est pas plus petit que l'original, ce qui
    rend le second levier auto-limite : re-encoder une image deja tres compressee
    la fait grossir, et la modification est alors abandonnee.

    Les echecs sont ignores image par image : une image recalcitrante ne doit pas
    faire echouer la compression du document entier.
    """
    for page in pdf.pages:
        try:
            entries = list(page.get_images().items())
        except Exception:
            continue

        for name, raw in entries:
            try:
                image = pikepdf.PdfImage(raw)

                # Ne pas toucher aux images masquees : un re-encodage JPEG
                # perdrait le canal alpha. Attention, `image_mask` vaut False
                # (et non None) quand l'image n'est pas un masque : on teste la
                # verite, pas l'identite a None.
                if image.image_mask or raw.get("/SMask", None) is not None:
                    continue

                width, height = image.width, image.height
                if not width or not height:
                    continue

                must_resize = width * height > max_pixels
                # Convertir une image sans perte n'a de sens que si on la reduit
                # aussi : sinon on degraderait sans contrepartie assuree.
                if not must_resize and not _is_jpeg(raw):
                    continue

                resized = image.as_pil_image()
                if must_resize:
                    scale = (max_pixels / (width * height)) ** 0.5
                    resized = resized.resize(
                        (max(1, int(width * scale)), max(1, int(height * scale))),
                        Image.Resampling.LANCZOS,
                    )

                buffer = io.BytesIO()
                resized.convert("RGB").save(
                    buffer, format="JPEG", quality=jpeg_quality, optimize=True
                )
                encoded = buffer.getvalue()

                # Comparer a la taille REELLE stockee, pas a la taille decodee.
                try:
                    original_size = len(bytes(raw.read_raw_bytes()))
                except Exception:
                    original_size = len(bytes(raw.read_bytes()))
                if len(encoded) >= original_size:
                    continue

                stream = pikepdf.Stream(pdf, encoded)
                stream.Type = pikepdf.Name("/XObject")
                stream.Subtype = pikepdf.Name("/Image")
                stream.Width = resized.width
                stream.Height = resized.height
                stream.ColorSpace = pikepdf.Name("/DeviceRGB")
                stream.BitsPerComponent = 8
                stream.Filter = pikepdf.Name("/DCTDecode")
                page.Resources.XObject[name] = stream
            except Exception as exc:
                logger.debug("Image ignoree a la compression : %s", exc)
                continue


def pdf_to_images(pdf_bytes: bytes, fmt: str = "png", dpi: int = 150) -> list[bytes]:
    """Rend chaque page du PDF en image.

    Utilise pypdfium2, qui embarque PDFium (le moteur de Chrome) dans son wheel :
    aucune dependance systeme, donc le rendu fonctionne a l'identique sur un poste
    de developpement Windows et dans le conteneur. C'est la raison du choix face a
    pdf2image, qui exige poppler installe a cote, et face a PyMuPDF, dont la
    licence AGPL imposerait de publier le code source du service.

    Leve PdfConversionError si le rendu est impossible. Aucune image de repli n'est
    produite : une page blanche silencieuse serait indiscernable d'un succes et
    ferait croire a l'utilisateur que la conversion a fonctionne.
    """
    try:
        document = pdfium.PdfDocument(pdf_bytes)
    except Exception as exc:
        raise PdfConversionError(
            "Ce PDF n'a pas pu etre ouvert : le fichier est peut-etre corrompu."
        ) from exc

    if len(document) == 0:
        raise PdfConversionError("Ce PDF ne contient aucune page.")

    # 72 points = 1 pouce : l'echelle est le rapport direct entre ppp et points.
    scale = dpi / 72
    results: list[bytes] = []

    try:
        for index in range(len(document)):
            bitmap = document[index].render(scale=scale)
            image = bitmap.to_pil()

            buffer = io.BytesIO()
            if fmt.lower() == "jpeg":
                image.convert("RGB").save(buffer, format="JPEG", quality=85)
            else:
                image.save(buffer, format="PNG")
            results.append(buffer.getvalue())
    except Exception as exc:
        raise PdfConversionError(
            "Ce PDF n'a pas pu etre rendu en image : le fichier est peut-etre corrompu."
        ) from exc

    return results


def images_to_pdf(image_bytes_list: list[bytes]) -> bytes:
    """Create PDF from multiple images."""
    images = []
    for img_bytes in image_bytes_list:
        img = Image.open(io.BytesIO(img_bytes))
        if img.mode == "RGBA":
            img = img.convert("RGB")
        images.append(img)
    
    if not images:
        raise ValueError("No images provided")
    
    buffer = io.BytesIO()
    images[0].save(buffer, format="PDF", save_all=True, append_images=images[1:])
    return buffer.getvalue()


def protect_pdf(pdf_bytes: bytes, user_password: str, owner_password: Optional[str] = None) -> bytes:
    """Add password protection to PDF."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    
    for page in reader.pages:
        writer.add_page(page)
    
    writer.encrypt(
        user_password=user_password,
        owner_password=owner_password or user_password,
    )
    
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def unprotect_pdf(pdf_bytes: bytes, password: str) -> bytes:
    """Remove password from PDF."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    
    if reader.is_encrypted:
        reader.decrypt(password)
    
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def add_watermark_to_pdf(pdf_bytes: bytes, watermark_text: str, opacity: float = 0.3) -> bytes:
    """Ajoute un filigrane texte en diagonale sur chaque page.

    L'ordre compte : la page est d'abord ATTACHEE au writer, ensuite fusionnee.
    Fusionner une page encore rattachee au lecteur est deprecie par pypdf
    (« unreliable », suppression prevue en 7.0) : `PdfWriter.add_page` renvoie la
    page telle qu'elle appartient au document de sortie, et c'est celle-la qu'il
    faut modifier.
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()

    for page in reader.pages:
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)

        watermark_buffer = io.BytesIO()
        c = canvas.Canvas(watermark_buffer, pagesize=(width, height))
        c.setFont("Helvetica", 48)
        c.setFillAlpha(opacity)
        c.saveState()
        c.translate(width / 2, height / 2)
        c.rotate(45)
        c.drawCentredString(0, 0, watermark_text)
        c.restoreState()
        c.save()

        target = writer.add_page(page)
        watermark_reader = PdfReader(io.BytesIO(watermark_buffer.getvalue()))
        target.merge_page(watermark_reader.pages[0])

    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def rotate_pdf(pdf_bytes: bytes, angle: int = 90, pages: Optional[str] = None) -> bytes:
    """Rotate PDF pages by specified angle."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    
    total = len(reader.pages)
    if pages:
        page_indices = _parse_page_range(pages, total)
    else:
        page_indices = list(range(total))
    
    for idx, page in enumerate(reader.pages):
        if idx in page_indices:
            page.rotate(angle)
        writer.add_page(page)
    
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def crop_pdf(pdf_bytes: bytes, x: float, y: float, w: float, h: float) -> bytes:
    """Crop PDF pages to specified dimensions (in points, 72 DPI)."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    
    for page in reader.pages:
        page.mediabox.lower_left = (x, y)
        page.mediabox.upper_right = (x + w, y + h)
        writer.add_page(page)
    
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def _parse_page_range(range_str: str, total: int) -> list[int]:
    """Parse page range string like '1,3,5-8' into list of 0-based indices."""
    indices = []
    for part in range_str.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            start = max(1, int(start))
            end = min(total, int(end))
            indices.extend(range(start - 1, end))
        else:
            idx = int(part) - 1
            if 0 <= idx < total:
                indices.append(idx)
    return sorted(set(indices))


def build_zip(entries: list[tuple[str, bytes]]) -> bytes:
    """Assemble plusieurs fichiers en une archive ZIP, en memoire."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries:
            archive.writestr(name, data)
    return buffer.getvalue()
