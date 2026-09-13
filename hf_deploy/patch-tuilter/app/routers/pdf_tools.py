"""PDF tools router — merge, split, compress, convert, protect, watermark, rotate, crop.

Version corrigee. Seuls TROIS comportements changent par rapport a l'original :

1. `split` renvoie une archive ZIP des qu'il produit plusieurs pages, au lieu de
   ne renvoyer silencieusement que la premiere.
2. `to-image` fait de meme, et signale franchement un PDF illisible au lieu de
   produire une page blanche indiscernable d'un succes.
3. `split_pdf` renvoie des couples (numero de page, contenu), pour que chaque
   fichier de l'archive porte le numero de sa page d'origine.

Le reste est inchange : file d'attente `processing_queue`, execution dans un
thread via `run_in_executor`, limites de debit et validation des entrees.
"""
import asyncio
import io
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.utils import get_current_user
from app.config import settings
from app.rate_limit import limiter
from app.database import User, get_db
from app.services.pdf_processing import (
    PdfConversionError, build_zip,
    merge_pdfs, split_pdf, compress_pdf, pdf_to_images,
    images_to_pdf, protect_pdf, unprotect_pdf,
    add_watermark_to_pdf, rotate_pdf, crop_pdf,
)
from app.services.usage import check_and_increment_usage
from app.services.queue import processing_queue

logger = logging.getLogger("pdf_tools_router")
router = APIRouter(prefix="/api/pdf", tags=["📄 Outils PDF"])

PDF_MIME = "application/pdf"
ZIP_MIME = "application/zip"


def _validate_pdf(file: UploadFile) -> None:
    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else ""
    if ext not in {".pdf", ".png", ".jpg", ".jpeg"}:
        raise HTTPException(400, f"Format non supporté: {ext}")
    if file.size and file.size > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(400, f"Fichier trop volumineux (max {settings.MAX_UPLOAD_MB}MB)")


async def _run_blocking(func):
    """Execute un traitement PDF hors de la boucle d'evenements.

    Conserve tel quel depuis l'original : ces bibliotheques sont synchrones et
    bloqueraient le serveur si on les appelait directement.
    """
    await processing_queue.acquire(0)
    try:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, func)
    finally:
        processing_queue.release(0)


@router.post("/merge", summary="Fusionner plusieurs PDF")
@limiter.limit("20/minute")
async def api_merge(request: Request, files: list[UploadFile] = File(...)):
    if len(files) < 2:
        raise HTTPException(400, "Au moins 2 fichiers PDF requis")
    if len(files) > 20:
        raise HTTPException(400, "Maximum 20 fichiers à la fois")
    pdf_bytes_list = []
    for f in files:
        _validate_pdf(f)
        pdf_bytes_list.append(await f.read())
    result = await _run_blocking(lambda: merge_pdfs(pdf_bytes_list))
    return StreamingResponse(io.BytesIO(result), media_type=PDF_MIME,
        headers={"Content-Disposition": 'attachment; filename="merged.pdf"'})


@router.post("/split", summary="Découper un PDF")
@limiter.limit("20/minute")
async def api_split(request: Request, file: UploadFile = File(...), pages: str = Form("")):
    _validate_pdf(file)
    pdf_bytes = await file.read()
    # `split_pdf` renvoie [(numero_de_page, contenu), ...]
    result = await _run_blocking(lambda: split_pdf(pdf_bytes, pages if pages else None))

    if not result:
        raise HTTPException(400, "Aucune page à extraire pour cette sélection")

    # Une seule page : le PDF directement, sans archive inutile.
    if len(result) == 1:
        _, data = result[0]
        return StreamingResponse(io.BytesIO(data), media_type=PDF_MIME,
            headers={"Content-Disposition": 'attachment; filename="split.pdf"'})

    # Plusieurs pages : une archive, sinon l'utilisateur ne recevrait que la
    # premiere page sans le savoir.
    archive = build_zip([(f"page_{number}.pdf", data) for number, data in result])
    return StreamingResponse(io.BytesIO(archive), media_type=ZIP_MIME,
        headers={"Content-Disposition": 'attachment; filename="pages.zip"'})


@router.post("/compress", summary="Compresser un PDF")
@limiter.limit("20/minute")
async def api_compress(request: Request, file: UploadFile = File(...), quality: str = Form("medium")):
    _validate_pdf(file)
    pdf_bytes = await file.read()
    result = await _run_blocking(lambda: compress_pdf(pdf_bytes, quality))
    return StreamingResponse(io.BytesIO(result), media_type=PDF_MIME,
        headers={"Content-Disposition": 'attachment; filename="compressed.pdf"'})


@router.post("/to-image", summary="PDF en images")
@limiter.limit("10/minute")
async def api_to_image(request: Request, file: UploadFile = File(...), format: str = Form("png"), dpi: int = Form(150)):
    _validate_pdf(file)
    pdf_bytes = await file.read()

    try:
        images = await _run_blocking(lambda: pdf_to_images(pdf_bytes, format, dpi))
    except PdfConversionError as exc:
        # Avant : l'echec etait avale et remplace par une page blanche, que
        # l'utilisateur prenait pour un resultat valide.
        raise HTTPException(422, str(exc))

    if not images:
        raise HTTPException(400, "Aucune page trouvée")

    mime = "image/jpeg" if format == "jpeg" else "image/png"
    ext = "jpg" if format == "jpeg" else "png"

    if len(images) == 1:
        return StreamingResponse(io.BytesIO(images[0]), media_type=mime,
            headers={"Content-Disposition": f'attachment; filename="page_1.{ext}"'})

    archive = build_zip([(f"page_{index}.{ext}", data) for index, data in enumerate(images, start=1)])
    return StreamingResponse(io.BytesIO(archive), media_type=ZIP_MIME,
        headers={"Content-Disposition": 'attachment; filename="pages.zip"'})


@router.post("/from-images", summary="Images en PDF")
@limiter.limit("10/minute")
async def api_from_images(request: Request, files: list[UploadFile] = File(...)):
    if len(files) > 50:
        raise HTTPException(400, "Maximum 50 images")
    image_bytes_list = []
    for f in files:
        _validate_pdf(f)
        image_bytes_list.append(await f.read())
    result = await _run_blocking(lambda: images_to_pdf(image_bytes_list))
    return StreamingResponse(io.BytesIO(result), media_type=PDF_MIME,
        headers={"Content-Disposition": 'attachment; filename="images.pdf"'})


@router.post("/protect", summary="Protéger PDF avec mot de passe")
@limiter.limit("20/minute")
async def api_protect(request: Request, file: UploadFile = File(...), password: str = Form(...)):
    _validate_pdf(file)
    pdf_bytes = await file.read()
    result = await _run_blocking(lambda: protect_pdf(pdf_bytes, password))
    return StreamingResponse(io.BytesIO(result), media_type=PDF_MIME,
        headers={"Content-Disposition": 'attachment; filename="protected.pdf"'})


@router.post("/unprotect", summary="Supprimer protection PDF")
@limiter.limit("20/minute")
async def api_unprotect(request: Request, file: UploadFile = File(...), password: str = Form(...)):
    _validate_pdf(file)
    pdf_bytes = await file.read()
    try:
        result = await _run_blocking(lambda: unprotect_pdf(pdf_bytes, password))
    except Exception:
        raise HTTPException(400, "Mot de passe incorrect")
    return StreamingResponse(io.BytesIO(result), media_type=PDF_MIME,
        headers={"Content-Disposition": 'attachment; filename="unprotected.pdf"'})


@router.post("/watermark", summary="Ajouter filigrane au PDF")
@limiter.limit("20/minute")
async def api_watermark(request: Request, file: UploadFile = File(...), text: str = Form(...), opacity: float = Form(0.3)):
    _validate_pdf(file)
    pdf_bytes = await file.read()
    result = await _run_blocking(lambda: add_watermark_to_pdf(pdf_bytes, text, opacity))
    return StreamingResponse(io.BytesIO(result), media_type=PDF_MIME,
        headers={"Content-Disposition": 'attachment; filename="watermarked.pdf"'})


@router.post("/rotate", summary="Pivoter les pages PDF")
@limiter.limit("20/minute")
async def api_rotate(request: Request, file: UploadFile = File(...), angle: int = Form(90), pages: str = Form("")):
    _validate_pdf(file)
    pdf_bytes = await file.read()
    result = await _run_blocking(lambda: rotate_pdf(pdf_bytes, angle, pages if pages else None))
    return StreamingResponse(io.BytesIO(result), media_type=PDF_MIME,
        headers={"Content-Disposition": 'attachment; filename="rotated.pdf"'})


@router.post("/crop", summary="Recadrer les pages PDF")
@limiter.limit("20/minute")
async def api_crop(request: Request, file: UploadFile = File(...), x: float = Form(0), y: float = Form(0), w: float = Form(595), h: float = Form(842)):
    _validate_pdf(file)
    pdf_bytes = await file.read()
    result = await _run_blocking(lambda: crop_pdf(pdf_bytes, x, y, w, h))
    return StreamingResponse(io.BytesIO(result), media_type=PDF_MIME,
        headers={"Content-Disposition": 'attachment; filename="cropped.pdf"'})
