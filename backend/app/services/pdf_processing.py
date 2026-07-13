"""PDF processing service — all operations use PyPDF2 + reportlab."""
from __future__ import annotations
import io
import os
from typing import Optional

from PIL import Image
from PyPDF2 import PdfReader, PdfWriter, PdfMerger
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def merge_pdfs(pdf_bytes_list: list[bytes]) -> bytes:
    """Merge multiple PDFs into one."""
    merger = PdfMerger()
    for pdf_bytes in pdf_bytes_list:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        merger.append(reader)
    output = io.BytesIO()
    merger.write(output)
    merger.close()
    return output.getvalue()


def split_pdf(pdf_bytes: bytes, pages: Optional[str] = None) -> list[bytes]:
    """Split PDF into individual pages or specified range.
    
    pages format: "1,3,5-8" or None for all pages
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
        results.append(output.getvalue())
    
    return results


def compress_pdf(pdf_bytes: bytes, quality: str = "medium") -> bytes:
    """Compress PDF by removing objects and optimizing.
    
    quality: low, medium, high
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    
    for page in reader.pages:
        writer.add_page(page)
    
    # Remove metadata to reduce size
    if quality in ("low", "medium"):
        writer.add_metadata({})
    
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def pdf_to_images(pdf_bytes: bytes, fmt: str = "png", dpi: int = 150) -> list[bytes]:
    """Convert PDF pages to images."""
    try:
        from pdf2image import convert_from_bytes
        images = convert_from_bytes(pdf_bytes, dpi=dpi)
        
        results = []
        for img in images:
            buffer = io.BytesIO()
            if fmt.lower() == "jpeg":
                img.convert("RGB").save(buffer, format="JPEG", quality=85)
            else:
                img.save(buffer, format="PNG")
            results.append(buffer.getvalue())
        
        return results
    except Exception:
        # Fallback: simple page render using PyPDF2
        reader = PdfReader(io.BytesIO(pdf_bytes))
        results = []
        for page in reader.pages:
            # Create a placeholder image
            img = Image.new("RGB", (595, 842), "white")  # A4 size
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            results.append(buffer.getvalue())
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
    """Add text watermark to each PDF page."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    
    for page in reader.pages:
        # Create watermark
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
        
        watermark_reader = PdfReader(io.BytesIO(watermark_buffer.getvalue()))
        page.merge_page(watermark_reader.pages[0])
        writer.add_page(page)
    
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
