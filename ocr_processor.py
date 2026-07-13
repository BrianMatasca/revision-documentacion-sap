"""
ocr_processor.py
────────────────
Módulo para la extracción de imágenes desde archivos PDF.

Nota: Originalmente este módulo extraía texto mediante OCR (Tesseract).
El flujo actual convierte el PDF a imágenes (PNG) usando Poppler y 
las envía directamente a Gemini Vision, dejando que el LLM realice 
la lectura y extracción de forma nativa.
"""

from __future__ import annotations

import logging
import os

# ── Rutas a herramientas (relativas al módulo) ──────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_POPPLER_LOCAL = os.path.join(BASE_DIR, "poppler")  # binarios Windows (.exe)

# En Windows se usa la carpeta local con los .exe.
# En Linux/Streamlit Cloud se usa None → pdf2image toma el poppler del PATH
# (instalado vía packages.txt con poppler-utils).
import platform as _platform
POPPLER_PATH: str | None = (
    _POPPLER_LOCAL
    if _platform.system() == "Windows" and os.path.isdir(_POPPLER_LOCAL)
    else None
)

logger = logging.getLogger(__name__)


def pdf_a_imagenes_bytes(pdf_bytes: bytes, dpi: int = 150) -> list[bytes]:
    """Convierte cada página de un PDF a bytes PNG para enviar a Gemini Vision.

    Parámetros
    ----------
    pdf_bytes : bytes
        Contenido crudo del archivo PDF.
    dpi : int
        Resolución de las imágenes. 150 DPI es suficiente para Gemini.
        A mayor DPI, mayor calidad pero más tokens consumidos.

    Retorna
    -------
    list[bytes]
        Lista de imágenes PNG en bytes, una por página.

    Raises
    ------
    RuntimeError
        Si pdf2image o Poppler no están disponibles.
    """
    try:
        from pdf2image import convert_from_bytes
    except ImportError:
        raise RuntimeError(
            "pdf2image no está instalado. Ejecute: pip install pdf2image"
        )

    import io as _io

    poppler_path = POPPLER_PATH  # None en Linux → pdf2image usa el PATH del sistema
    try:
        imagenes = convert_from_bytes(pdf_bytes, dpi=dpi, poppler_path=poppler_path)
    except Exception as e:
        raise RuntimeError(f"Error al convertir PDF a imágenes: {e}") from e

    resultado: list[bytes] = []
    for img in imagenes:
        buf = _io.BytesIO()
        img.save(buf, format="PNG")
        resultado.append(buf.getvalue())

    logger.info(
        "PDF convertido a %d imágenes PNG (DPI=%d, tamaño prom. %.1f KB).",
        len(resultado),
        dpi,
        sum(len(b) for b in resultado) / max(len(resultado), 1) / 1024,
    )
    return resultado
