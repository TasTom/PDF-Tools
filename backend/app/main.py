"""PDF Tools API — FastAPI application."""
# NE PAS ajouter `from __future__ import annotations` dans ce module.
# Les annotations deviendraient des chaînes, et FastAPI les résoudrait dans le
# mauvais espace de noms : `@limiter.limit` enveloppe chaque endpoint, si bien
# que `inspect.signature` suit `__wrapped__` jusqu'à la fonction d'origine mais
# évalue ses annotations dans les globales de slowapi, où `UploadFile` n'existe
# pas. Résultat : `ForwardRef('list[UploadFile]')` non résolu et l'application
# refuse de démarrer. Python 3.11 (voir hf_deploy/Dockerfile) comprend nativement
# `list[...]`, l'import est donc inutile ici.
import io
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, File, Form, UploadFile, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings
from app.services.pdf_processing import (
    PdfConversionError, build_zip,
    merge_pdfs, split_pdf, compress_pdf, pdf_to_images,
    images_to_pdf, protect_pdf, unprotect_pdf,
    add_watermark_to_pdf, rotate_pdf, crop_pdf,
)

logger = logging.getLogger("pdf_tools")
logging.basicConfig(level=logging.INFO)

# Protection anti-abus, entièrement en mémoire et par adresse IP.
# Aucune donnée utilisateur n'est conservée et les compteurs repartent de zéro
# à chaque redémarrage du processus.
limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("PDF Tools API started")
    yield
    logger.info("PDF Tools API shutting down")

app = FastAPI(
    title="PDF Tools API",
    description="API de traitement de fichiers PDF — merge, split, compress, convert, protect.",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(PdfConversionError)
async def _pdf_conversion_failed(request: Request, exc: PdfConversionError):
    """Le fichier envoye n'a pas pu etre rendu."""
    return JSONResponse(status_code=422, content={"detail": str(exc)})

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _validate_pdf(file: UploadFile) -> None:
    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else ""
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Format non supporté: {ext}")
    if file.size and file.size > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(400, f"Fichier trop volumineux (max {settings.MAX_UPLOAD_MB}MB)")


@app.get("/", tags=["health"])
async def root():
    return {"status": "ok", "service": "PDF Tools API", "version": "1.0.0"}


@app.get("/health", tags=["health"])
async def health():
    """Sonde de disponibilité, utilisée par le déploiement."""
    return {"status": "ok"}


# ========== PDF Endpoints ==========

@app.post("/api/pdf/merge", tags=["PDF"])
@limiter.limit(settings.RATE_LIMIT_LIGHT)
async def api_merge(request: Request, files: list[UploadFile] = File(..., description="PDFs à fusionner")):
    """Fusionner plusieurs fichiers PDF en un seul."""
    if len(files) < 2:
        raise HTTPException(400, "Au moins 2 fichiers PDF requis")
    if len(files) > 20:
        raise HTTPException(400, "Maximum 20 fichiers à la fois")
    
    pdf_bytes_list = []
    for f in files:
        _validate_pdf(f)
        pdf_bytes_list.append(await f.read())
    
    result = merge_pdfs(pdf_bytes_list)
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="merged.pdf"'},
    )


@app.post("/api/pdf/split", tags=["PDF"])
@limiter.limit(settings.RATE_LIMIT_LIGHT)
async def api_split(
    request: Request,
    file: UploadFile = File(..., description="PDF à découper"),
    pages: str = Form("", description="Pages à extraire (ex: 1,3,5-8). Vide = toutes les pages"),
):
    """Découper un PDF en pages individuelles ou extraire des pages spécifiques."""
    _validate_pdf(file)
    pdf_bytes = await file.read()
    result = split_pdf(pdf_bytes, pages if pages else None)
    
    if len(result) == 1:
        _, data = result[0]
        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="split.pdf"'},
        )
    
    # Plusieurs pages : une archive, sinon l'utilisateur ne recevrait que la premiere.
    archive = build_zip([(f"page_{number}.pdf", data) for number, data in result])
    return StreamingResponse(
        io.BytesIO(archive),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="pages.zip"'},
    )


@app.post("/api/pdf/compress", tags=["PDF"])
@limiter.limit(settings.RATE_LIMIT_LIGHT)
async def api_compress(
    request: Request,
    file: UploadFile = File(..., description="PDF à compresser"),
    quality: str = Form("medium", description="Qualité: low, medium, high"),
):
    """Réduire la taille d'un fichier PDF."""
    _validate_pdf(file)
    pdf_bytes = await file.read()
    original_size = len(pdf_bytes)
    
    result = compress_pdf(pdf_bytes, quality)
    
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="compressed.pdf"',
            "X-Original-Size": str(original_size),
            "X-Compressed-Size": str(len(result)),
        },
    )


@app.post("/api/pdf/to-image", tags=["PDF"])
@limiter.limit(settings.RATE_LIMIT_HEAVY)
async def api_to_image(
    request: Request,
    file: UploadFile = File(..., description="PDF à convertir"),
    format: str = Form("png", description="Format de sortie: png, jpeg"),
    dpi: int = Form(150, ge=72, le=300, description="Résolution DPI (72-300)"),
):
    """Convertir les pages d'un PDF en images."""
    _validate_pdf(file)
    pdf_bytes = await file.read()
    images = pdf_to_images(pdf_bytes, format, dpi)
    
    mime = "image/jpeg" if format == "jpeg" else "image/png"
    ext = "jpg" if format == "jpeg" else "png"
    
    if len(images) == 1:
        return StreamingResponse(
            io.BytesIO(images[0]),
            media_type=mime,
            headers={"Content-Disposition": f'attachment; filename="page_1.{ext}"'},
        )
    
    # Plusieurs pages : une archive, sinon l'utilisateur ne recevrait que la premiere.
    archive = build_zip(
        [(f"page_{index}.{ext}", data) for index, data in enumerate(images, start=1)]
    )
    return StreamingResponse(
        io.BytesIO(archive),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="pages.zip"'},
    )


@app.post("/api/pdf/from-images", tags=["PDF"])
@limiter.limit(settings.RATE_LIMIT_HEAVY)
async def api_from_images(request: Request, files: list[UploadFile] = File(..., description="Images à convertir en PDF")):
    """Créer un PDF à partir de plusieurs images."""
    if len(files) > 50:
        raise HTTPException(400, "Maximum 50 images à la fois")
    
    image_bytes_list = []
    for f in files:
        _validate_pdf(f)
        image_bytes_list.append(await f.read())
    
    result = images_to_pdf(image_bytes_list)
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="images.pdf"'},
    )


@app.post("/api/pdf/protect", tags=["PDF"])
@limiter.limit(settings.RATE_LIMIT_LIGHT)
async def api_protect(
    request: Request,
    file: UploadFile = File(..., description="PDF à protéger"),
    password: str = Form(..., description="Mot de passe"),
):
    """Protéger un PDF avec un mot de passe."""
    _validate_pdf(file)
    pdf_bytes = await file.read()
    result = protect_pdf(pdf_bytes, password)
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="protected.pdf"'},
    )


@app.post("/api/pdf/unprotect", tags=["PDF"])
@limiter.limit(settings.RATE_LIMIT_LIGHT)
async def api_unprotect(
    request: Request,
    file: UploadFile = File(..., description="PDF protégé à déverrouiller"),
    password: str = Form(..., description="Mot de passe"),
):
    """Supprimer la protection mot de passe d'un PDF."""
    _validate_pdf(file)
    pdf_bytes = await file.read()
    try:
        result = unprotect_pdf(pdf_bytes, password)
    except Exception:
        raise HTTPException(400, "Mot de passe incorrect")
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="unprotected.pdf"'},
    )


@app.post("/api/pdf/watermark", tags=["PDF"])
@limiter.limit(settings.RATE_LIMIT_LIGHT)
async def api_watermark(
    request: Request,
    file: UploadFile = File(..., description="PDF à filigraner"),
    text: str = Form(..., description="Texte du filigrane"),
    opacity: float = Form(0.3, ge=0.05, le=1.0, description="Opacité (0.05-1.0)"),
):
    """Ajouter un filigrane texte à chaque page du PDF."""
    _validate_pdf(file)
    pdf_bytes = await file.read()
    result = add_watermark_to_pdf(pdf_bytes, text, opacity)
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="watermarked.pdf"'},
    )


@app.post("/api/pdf/rotate", tags=["PDF"])
@limiter.limit(settings.RATE_LIMIT_LIGHT)
async def api_rotate(
    request: Request,
    file: UploadFile = File(..., description="PDF à pivoter"),
    angle: int = Form(90, description="Angle de rotation: 90, 180, 270"),
    pages: str = Form("", description="Pages à pivoter. Vide = toutes"),
):
    """Pivoter les pages d'un PDF."""
    _validate_pdf(file)
    pdf_bytes = await file.read()
    result = rotate_pdf(pdf_bytes, angle, pages if pages else None)
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="rotated.pdf"'},
    )


@app.post("/api/pdf/crop", tags=["PDF"])
@limiter.limit(settings.RATE_LIMIT_LIGHT)
async def api_crop(
    request: Request,
    file: UploadFile = File(..., description="PDF à recadrer"),
    x: float = Form(0, description="Position X (points)"),
    y: float = Form(0, description="Position Y (points)"),
    w: float = Form(595, description="Largeur (points)"),
    h: float = Form(842, description="Hauteur (points)"),
):
    """Recadrer les pages d'un PDF."""
    _validate_pdf(file)
    pdf_bytes = await file.read()
    result = crop_pdf(pdf_bytes, x, y, w, h)
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="cropped.pdf"'},
    )
