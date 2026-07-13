"""
sap_client.py
─────────────
Módulo para la descarga de documentos desde SAP mediante HTTP Basic Auth.

Proporciona una función principal ``descargar_documento_sap`` y excepciones
específicas para manejar errores de autenticación, recursos no encontrados
y problemas de conexión.
"""

from __future__ import annotations

import logging
import os
import re
from urllib.parse import unquote, urlparse

import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)

# Tiempo máximo de espera para la descarga (segundos)
_TIMEOUT = 30


# ──────────────────────────────────────────────────────────────────────
# Excepciones personalizadas
# ──────────────────────────────────────────────────────────────────────

class SAPError(Exception):
    """Error base para operaciones con SAP."""
    pass


class SAPAuthError(SAPError):
    """Error de autenticación al conectar con SAP (HTTP 401/403)."""
    pass


class SAPNotFoundError(SAPError):
    """El documento solicitado no fue encontrado en SAP (HTTP 404)."""
    pass


class SAPConnectionError(SAPError):
    """Error de conexión o timeout al comunicarse con SAP."""
    pass


# ──────────────────────────────────────────────────────────────────────
# Función principal
# ──────────────────────────────────────────────────────────────────────

def descargar_documento_sap(
    url: str,
    usuario: str,
    password: str,
) -> tuple[bytes, str]:
    """Descarga un documento PDF desde SAP usando HTTP Basic Auth.

    Parámetros
    ----------
    url : str
        URL completa del documento en SAP.
    usuario : str
        Nombre de usuario para autenticación HTTP Basic.
    password : str
        Contraseña para autenticación HTTP Basic.

    Retorna
    -------
    tuple[bytes, str]
        Tupla con (contenido_pdf_bytes, nombre_archivo).

    Raises
    ------
    ValueError
        Si la URL, usuario o contraseña están vacíos.
    SAPAuthError
        Si las credenciales son inválidas (HTTP 401 o 403).
    SAPNotFoundError
        Si el documento no fue encontrado (HTTP 404).
    SAPConnectionError
        Si hay un error de conexión o timeout.
    SAPError
        Para cualquier otro error HTTP o de procesamiento.
    """
    # ── Validación de parámetros ─────────────────────────────────────
    if not url or not url.strip():
        raise ValueError("La URL del documento SAP no puede estar vacía.")
    if not usuario or not usuario.strip():
        raise ValueError("El usuario SAP no puede estar vacío.")
    if not password:
        raise ValueError("La contraseña SAP no puede estar vacía.")

    url = url.strip()

    # ── Realizar la petición HTTP ────────────────────────────────────
    logger.info("Descargando documento desde SAP: %s", url)

    try:
        response = requests.get(
            url,
            auth=HTTPBasicAuth(usuario.strip(), password),
            timeout=_TIMEOUT,
            stream=False,
            verify=True,
        )
    except requests.exceptions.Timeout:
        raise SAPConnectionError(
            f"Timeout al intentar descargar el documento. "
            f"La conexión superó los {_TIMEOUT} segundos."
        )
    except requests.exceptions.ConnectionError as e:
        raise SAPConnectionError(
            f"Error de conexión con SAP: {e}"
        )
    except requests.exceptions.RequestException as e:
        raise SAPError(
            f"Error inesperado en la petición HTTP: {e}"
        )

    # ── Manejo de códigos de estado ──────────────────────────────────
    if response.status_code == 401:
        raise SAPAuthError(
            "Credenciales inválidas. Verifique usuario y contraseña. "
            "(HTTP 401 Unauthorized)"
        )
    if response.status_code == 403:
        raise SAPAuthError(
            "Acceso denegado. El usuario no tiene permisos para este recurso. "
            "(HTTP 403 Forbidden)"
        )
    if response.status_code == 404:
        raise SAPNotFoundError(
            f"Documento no encontrado en SAP. Verifique la URL. "
            f"(HTTP 404 Not Found)"
        )
    if response.status_code >= 500:
        raise SAPError(
            f"Error interno del servidor SAP. "
            f"(HTTP {response.status_code})"
        )
    if response.status_code != 200:
        raise SAPError(
            f"Respuesta inesperada de SAP. "
            f"(HTTP {response.status_code}: {response.reason})"
        )

    # ── Validar que el contenido sea un PDF ──────────────────────────
    content_type = response.headers.get("Content-Type", "")
    pdf_bytes = response.content

    if not pdf_bytes:
        raise SAPError("El servidor SAP devolvió una respuesta vacía.")

    # Verificar el magic number de PDF (%PDF-)
    es_pdf = pdf_bytes[:5] == b"%PDF-"
    es_content_type_pdf = "application/pdf" in content_type.lower()

    if not es_pdf and not es_content_type_pdf:
        raise SAPError(
            f"El contenido descargado no parece ser un PDF. "
            f"Content-Type recibido: '{content_type}'. "
            f"Primeros bytes: {pdf_bytes[:20]!r}"
        )

    # ── Extraer nombre del archivo ───────────────────────────────────
    filename = _extraer_nombre_archivo(response, url)

    logger.info(
        "Documento descargado exitosamente: '%s' (%d bytes)",
        filename,
        len(pdf_bytes),
    )

    return pdf_bytes, filename


# ──────────────────────────────────────────────────────────────────────
# Funciones internas
# ──────────────────────────────────────────────────────────────────────

def _extraer_nombre_archivo(response: requests.Response, url: str) -> str:
    """Extrae el nombre del archivo desde Content-Disposition o la URL.

    Parámetros
    ----------
    response : requests.Response
        Respuesta HTTP de SAP.
    url : str
        URL original de la petición.

    Retorna
    -------
    str
        Nombre del archivo con extensión .pdf.
    """
    # Intentar extraer desde Content-Disposition
    content_disp = response.headers.get("Content-Disposition", "")
    if content_disp:
        # Buscar filename*= (RFC 5987) primero
        match = re.search(r"filename\*=(?:UTF-8''|utf-8'')(.+?)(?:;|$)", content_disp)
        if match:
            nombre = unquote(match.group(1).strip().strip('"'))
            if nombre:
                return _asegurar_extension_pdf(nombre)

        # Buscar filename= estándar
        match = re.search(r'filename="?([^";]+)"?', content_disp)
        if match:
            nombre = match.group(1).strip()
            if nombre:
                return _asegurar_extension_pdf(nombre)

    # Intentar extraer desde la URL
    parsed = urlparse(url)
    ruta = parsed.path
    if ruta:
        nombre_url = os.path.basename(unquote(ruta))
        if nombre_url and nombre_url != "/":
            return _asegurar_extension_pdf(nombre_url)

    # Nombre por defecto
    return "documento_sap.pdf"


def _asegurar_extension_pdf(nombre: str) -> str:
    """Asegura que el nombre de archivo tenga extensión .pdf."""
    if not nombre.lower().endswith(".pdf"):
        nombre += ".pdf"
    return nombre
