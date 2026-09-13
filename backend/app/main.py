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
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, File, Form, UploadFile, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import router as auth_router
from app.auth.utils import get_current_user
from app.config import settings
from app.database import User, get_db, init_db
from app.rate_limit import limiter
from app.routers.usage import router as usage_router
from app.services.pdf_processing import (
    PdfConversionError, build_zip,
    merge_pdfs, split_pdf, compress_pdf, pdf_to_images,
    images_to_pdf, protect_pdf, unprotect_pdf,
    add_watermark_to_pdf, rotate_pdf, crop_pdf,
)
from app.services.usage import check_and_increment_usage
from app.database import CIBLE_BASE

logger = logging.getLogger("pdf_tools")
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ouvre la base au demarrage.

    Les tables sont creees ici, comme sur warult-tools.com : la premiere
    execution sur une base vide doit pouvoir se faire sans migration manuelle.

    La cible est journalisee AVANT la connexion. Sans cela, un echec de
    demarrage en production ressemble a une erreur de code alors qu'il vient le
    plus souvent du secret DATABASE_URL — mauvais format, base suspendue, mot de
    passe tourne. L'hote et le nom de base suffisent a trancher ; le mot de
    passe n'est jamais journalise.
    """
    logger.info("Base de donnees visée : %s", CIBLE_BASE)
    logger.info("Initialisation de la base de donnees...")
    await init_db()
    logger.info("PDF Tools API started")
    yield
    logger.info("PDF Tools API shutting down")

app = FastAPI(
    title="PDF Tools API",
    description=(
        "API de traitement de fichiers PDF — fusion, découpage, compression, "
        "conversion, protection.\n\n"
        "## Authentification\n"
        "Chaque opération est comptée dans un quota quotidien, donc un compte est "
        "nécessaire. Utilisez le bouton **Authorize** avec un jeton Bearer obtenu "
        "via `/api/auth/register` ou `/api/auth/login`."
    ),
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

app.include_router(auth_router)
app.include_router(usage_router)


def _validate_pdf(file: UploadFile) -> None:
    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else ""
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Format non supporté: {ext}")
    if file.size and file.size > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(400, f"Fichier trop volumineux (max {settings.MAX_UPLOAD_MB}MB)")


def nom_sortie(*fichiers: UploadFile, suffixe: str, extension: str = "pdf") -> str:
    """Nom du fichier renvoye, derive de celui qui a ete envoye.

    Sans cela, le service repondait toujours « compressed.pdf », « rotated.pdf » :
    l'utilisateur qui envoie `facture-mars.pdf` devait renommer le resultat a la
    main, alors que le nom d'origine est justement l'information qu'il connait.

    Le nom est reduit a de l'ASCII sur. Ce n'est pas de la pudeur : un en-tete
    HTTP ne transporte pas d'autre jeu de caracteres de facon fiable, et un
    guillemet ou un retour a la ligne dans le nom permettrait de scinder
    l'en-tete `Content-Disposition`.

    Plusieurs fichiers (fusion, assemblage d'images) : le premier donne la base,
    c'est celui que l'utilisateur a choisi en premier et celui qu'il reconnaitra.
    """
    for fichier in fichiers:
        if fichier is not None and fichier.filename:
            base = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(fichier.filename).stem).strip("-._")
            if base:
                return f"{base}-{suffixe}.{extension}"
    return f"document-{suffixe}.{extension}"


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
async def api_merge(
    request: Request,
    files: list[UploadFile] = File(..., description="PDFs à fusionner"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Fusionner plusieurs fichiers PDF en un seul."""
    if len(files) < 2:
        raise HTTPException(400, "Au moins 2 fichiers PDF requis")
    if len(files) > 20:
        raise HTTPException(400, "Maximum 20 fichiers à la fois")

    # Validation AVANT de consommer le quota : un fichier refuse ne doit pas
    # couter une operation.
    for f in files:
        _validate_pdf(f)
    await check_and_increment_usage(db, user)

    pdf_bytes_list = [await f.read() for f in files]

    result = merge_pdfs(pdf_bytes_list)
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers={
            "Content-Disposition":
                f'attachment; filename="{nom_sortie(*files, suffixe="fusionne")}"'
        },
    )


@app.post("/api/pdf/split", tags=["PDF"])
@limiter.limit(settings.RATE_LIMIT_LIGHT)
async def api_split(
    request: Request,
    file: UploadFile = File(..., description="PDF à découper"),
    pages: str = Form("", description="Pages à extraire (ex: 1,3,5-8). Vide = toutes les pages"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Découper un PDF en pages individuelles ou extraire des pages spécifiques."""
    _validate_pdf(file)
    await check_and_increment_usage(db, user)
    pdf_bytes = await file.read()
    result = split_pdf(pdf_bytes, pages if pages else None)
    
    if len(result) == 1:
        _, data = result[0]
        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/pdf",
            headers={
                "Content-Disposition":
                    f'attachment; filename="{nom_sortie(file, suffixe="extrait")}"'
            },
        )
    
    # Plusieurs pages : une archive, sinon l'utilisateur ne recevrait que la premiere.
    archive = build_zip([(f"page_{number}.pdf", data) for number, data in result])
    return StreamingResponse(
        io.BytesIO(archive),
        media_type="application/zip",
        headers={
            "Content-Disposition":
                f'attachment; filename="{nom_sortie(file, suffixe="pages", extension="zip")}"'
        },
    )


@app.post("/api/pdf/compress", tags=["PDF"])
@limiter.limit(settings.RATE_LIMIT_LIGHT)
async def api_compress(
    request: Request,
    file: UploadFile = File(..., description="PDF à compresser"),
    quality: str = Form("medium", description="Qualité: low, medium, high"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Réduire la taille d'un fichier PDF."""
    _validate_pdf(file)
    await check_and_increment_usage(db, user)
    pdf_bytes = await file.read()
    original_size = len(pdf_bytes)
    
    result = compress_pdf(pdf_bytes, quality)
    
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers={
            "Content-Disposition":
                f'attachment; filename="{nom_sortie(file, suffixe="compresse")}"',
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
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Convertir les pages d'un PDF en images."""
    _validate_pdf(file)
    await check_and_increment_usage(db, user)
    pdf_bytes = await file.read()
    images = pdf_to_images(pdf_bytes, format, dpi)
    
    mime = "image/jpeg" if format == "jpeg" else "image/png"
    ext = "jpg" if format == "jpeg" else "png"
    
    if len(images) == 1:
        return StreamingResponse(
            io.BytesIO(images[0]),
            media_type=mime,
            headers={
                "Content-Disposition":
                    f'attachment; filename="{nom_sortie(file, suffixe="page-1", extension=ext)}"'
            },
        )
    
    # Plusieurs pages : une archive, sinon l'utilisateur ne recevrait que la premiere.
    archive = build_zip(
        [(f"page_{index}.{ext}", data) for index, data in enumerate(images, start=1)]
    )
    return StreamingResponse(
        io.BytesIO(archive),
        media_type="application/zip",
        headers={
            "Content-Disposition":
                f'attachment; filename="{nom_sortie(file, suffixe="pages", extension="zip")}"'
        },
    )


@app.post("/api/pdf/from-images", tags=["PDF"])
@limiter.limit(settings.RATE_LIMIT_HEAVY)
async def api_from_images(
    request: Request,
    files: list[UploadFile] = File(..., description="Images à convertir en PDF"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Créer un PDF à partir de plusieurs images."""
    if len(files) > 50:
        raise HTTPException(400, "Maximum 50 images à la fois")

    for f in files:
        _validate_pdf(f)
    await check_and_increment_usage(db, user)

    image_bytes_list = [await f.read() for f in files]

    result = images_to_pdf(image_bytes_list)
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers={
            "Content-Disposition":
                f'attachment; filename="{nom_sortie(*files, suffixe="assemble")}"'
        },
    )


@app.post("/api/pdf/protect", tags=["PDF"])
@limiter.limit(settings.RATE_LIMIT_LIGHT)
async def api_protect(
    request: Request,
    file: UploadFile = File(..., description="PDF à protéger"),
    password: str = Form(..., description="Mot de passe"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Protéger un PDF avec un mot de passe."""
    _validate_pdf(file)
    await check_and_increment_usage(db, user)
    pdf_bytes = await file.read()
    result = protect_pdf(pdf_bytes, password)
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers={
            "Content-Disposition":
                f'attachment; filename="{nom_sortie(file, suffixe="protege")}"'
        },
    )


@app.post("/api/pdf/unprotect", tags=["PDF"])
@limiter.limit(settings.RATE_LIMIT_LIGHT)
async def api_unprotect(
    request: Request,
    file: UploadFile = File(..., description="PDF protégé à déverrouiller"),
    password: str = Form(..., description="Mot de passe"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Supprimer la protection mot de passe d'un PDF."""
    _validate_pdf(file)
    await check_and_increment_usage(db, user)
    pdf_bytes = await file.read()
    try:
        result = unprotect_pdf(pdf_bytes, password)
    except Exception:
        raise HTTPException(400, "Mot de passe incorrect")
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers={
            "Content-Disposition":
                f'attachment; filename="{nom_sortie(file, suffixe="deverrouille")}"'
        },
    )


@app.post("/api/pdf/watermark", tags=["PDF"])
@limiter.limit(settings.RATE_LIMIT_LIGHT)
async def api_watermark(
    request: Request,
    file: UploadFile = File(..., description="PDF à filigraner"),
    text: str = Form(..., description="Texte du filigrane"),
    opacity: float = Form(0.3, ge=0.05, le=1.0, description="Opacité (0.05-1.0)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ajouter un filigrane texte à chaque page du PDF."""
    _validate_pdf(file)
    await check_and_increment_usage(db, user)
    pdf_bytes = await file.read()
    result = add_watermark_to_pdf(pdf_bytes, text, opacity)
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers={
            "Content-Disposition":
                f'attachment; filename="{nom_sortie(file, suffixe="filigrane")}"'
        },
    )


@app.post("/api/pdf/rotate", tags=["PDF"])
@limiter.limit(settings.RATE_LIMIT_LIGHT)
async def api_rotate(
    request: Request,
    file: UploadFile = File(..., description="PDF à pivoter"),
    angle: int = Form(90, description="Angle de rotation: 90, 180, 270"),
    pages: str = Form("", description="Pages à pivoter. Vide = toutes"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Pivoter les pages d'un PDF."""
    _validate_pdf(file)
    await check_and_increment_usage(db, user)
    pdf_bytes = await file.read()
    result = rotate_pdf(pdf_bytes, angle, pages if pages else None)
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers={
            "Content-Disposition":
                f'attachment; filename="{nom_sortie(file, suffixe="pivote")}"'
        },
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
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Recadrer les pages d'un PDF."""
    _validate_pdf(file)
    await check_and_increment_usage(db, user)
    pdf_bytes = await file.read()
    result = crop_pdf(pdf_bytes, x, y, w, h)
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers={
            "Content-Disposition":
                f'attachment; filename="{nom_sortie(file, suffixe="recadre")}"'
        },
    )
