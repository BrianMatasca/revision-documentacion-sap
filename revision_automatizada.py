"""
Módulo de revisión automatizada de documentos SAP usando la API de Gemini Vision.

Revisa documentos del flujo automatizado: Carta de Presentación,
Verificación de Requisitos y Viabilidad. Envía las páginas del PDF como
imágenes a Gemini (Vision) para una interpretación correcta de tablas.
"""

import json
import re
from pathlib import Path
from typing import Union

from google import genai
from google.genai import types as genai_types

import mga_parser

# Modelo a usar
_MODELO = 'models/gemini-3.1-flash-lite'


class QuotaExhaustedError(Exception):
    """Excepción lanzada cuando se agota la cuota de la API de Gemini."""
    pass


# ──────────────────────────────────────────────────────────────────────
# Helpers de lectura y construcción de prompts
# ──────────────────────────────────────────────────────────────────────

def _leer_archivo_formato(formato_dir: Union[str, Path], nombre_archivo: str) -> str:
    """Lee un archivo de la carpeta del formato."""
    ruta = Path(formato_dir) / nombre_archivo
    try:
        return ruta.read_text(encoding='utf-8')
    except FileNotFoundError:
        return f'[Archivo {nombre_archivo} no encontrado en {formato_dir}]'
    except Exception as e:
        return f'[Error al leer {nombre_archivo}: {e}]'


def _construir_system_prompt(formato_dir: Union[str, Path]) -> str:
    """
    Construye el prompt de sistema a partir de los archivos del formato
    y del archivo de reglas global.
    """
    contenido_prompt = _leer_archivo_formato(formato_dir, 'prompt.md')
    contenido_formato = _leer_archivo_formato(formato_dir, 'formato.md')
    
    # Leer el archivo global de reglas para evitar falsos positivos
    base_dir = Path(__file__).parent
    ruta_reglas = base_dir / 'reglas_falsos_positivos.md'
    try:
        reglas_falsos_positivos = ruta_reglas.read_text(encoding='utf-8')
    except Exception as e:
        reglas_falsos_positivos = f'[Error al leer reglas de falsos positivos: {e}]'

    system_prompt = (
        f'{contenido_prompt}\n\n'
        f'--- FORMATO BASE DE REFERENCIA ---\n'
        f'{contenido_formato}\n\n'
        f'IMPORTANTE: NO valides firmas, ni fechas, sellos ni rúbricas. '
        f'Solo valida contenido textual y coherencia de datos.\n\n'

        f'{reglas_falsos_positivos}\n\n'

        f'FORMATO DE RESPUESTA OBLIGATORIO: Responde SIEMPRE con un único objeto JSON '
        f'(no una lista, no texto adicional) con exactamente estas claves:\n'
        f'{{\n'
        f'  "estado": "OK" | "ERRORES" | "REVISION_MANUAL",\n'
        f'  "resumen": "<resumen breve de la revisión>",\n'
        f'  "hallazgos": ["<hallazgo 1>", "<hallazgo 2>", ...],\n'
        f'  "recomendacion": "<recomendación general>",\n'
        f'  "codigo_pi": "<código PI encontrado en el documento, o null si no se identifica>"\n'
        f'}}'
    )
    return system_prompt


def _parsear_respuesta_gemini(raw_text: str) -> dict:
    """
    Parsea la respuesta JSON de Gemini con manejo robusto de formatos.

    Soporta: objeto JSON directo, lista JSON (toma primer elemento),
    y extracción regex como último recurso.
    """
    try:
        data = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError):
        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        data = json.loads(match.group(0)) if match else {}

    # Si Gemini devuelve una lista en vez de un objeto, tomar el primer elemento
    if isinstance(data, list):
        data = data[0] if data else {}

    # Asegurarse de que sea un dict
    if not isinstance(data, dict):
        data = {}

    estado = data.get('estado', 'REVISION_MANUAL').upper()
    if estado not in ('OK', 'ERRORES', 'REVISION_MANUAL'):
        estado = 'REVISION_MANUAL'

    # Extraer código PI (puede ser string, None o ausente)
    codigo_pi_raw = data.get('codigo_pi', None)
    if isinstance(codigo_pi_raw, str):
        codigo_pi = codigo_pi_raw.strip() or None
    else:
        codigo_pi = None

    return {
        'estado': estado,
        'resumen': data.get('resumen', f'Sin resumen. Respuesta raw: {raw_text[:300]}'),
        'hallazgos': data.get('hallazgos', ['No se extrajeron hallazgos.']),
        'recomendacion': data.get('recomendacion', 'Revisar manualmente.'),
        'codigo_pi': codigo_pi,
    }


# ──────────────────────────────────────────────────────────────────────
# Función principal de revisión (Gemini Vision)
# ──────────────────────────────────────────────────────────────────────

def revisar_documento(
    api_key: str,
    pdf_bytes: bytes,
    tipo_documento: str,
    datos_mga: dict,
    formato_dir: Union[str, Path],
) -> dict:
    """
    Revisa un documento enviando sus páginas como imágenes a Gemini Vision.

    Convierte el PDF a imágenes PNG y las envía junto con los datos de la
    MGA al modelo Gemini. Esto permite una interpretación correcta de
    tablas de chequeo, sin los errores de OCR en texto plano.

    Args:
        api_key: Clave de API de Gemini.
        pdf_bytes: Contenido crudo del PDF a revisar.
        tipo_documento: 'presentacion', 'verificacion' o 'viabilidad'.
        datos_mga: Diccionario con datos parseados del XML MGA.
        formato_dir: Ruta a la carpeta con formato.md y prompt.md.

    Returns:
        Diccionario con keys:
            - estado (str): 'OK', 'ERRORES' o 'REVISION_MANUAL'.
            - resumen (str): Resumen de la revisión.
            - hallazgos (list[str]): Lista de hallazgos encontrados.
            - recomendacion (str): Recomendación general.
            - tokens_entrada (int): Tokens de prompt consumidos.
            - tokens_salida (int): Tokens de respuesta generados.
            - num_paginas (int): Número de páginas del documento.

    Raises:
        QuotaExhaustedError: Si se agota la cuota de la API.
        RuntimeError: Si el PDF no se puede convertir a imágenes.
    """
    # 1. Convertir PDF a imágenes PNG
    from ocr_processor import pdf_a_imagenes_bytes
    imagenes_bytes = pdf_a_imagenes_bytes(pdf_bytes, dpi=150)
    num_paginas = len(imagenes_bytes)

    # 2. Construir el system prompt
    system_prompt = _construir_system_prompt(formato_dir)

    # 3. Construir las partes del mensaje de usuario:
    #    Texto con datos MGA + imágenes de las páginas del documento
    datos_mga_formateados = mga_parser.formatear_datos_mga_para_prompt(datos_mga)

    parts = []

    # Texto introductorio con datos de la MGA
    parts.append(genai_types.Part.from_text(
        text=(
            f'--- DATOS DEL PROYECTO (MGA - fuente de verdad) ---\n'
            f'{datos_mga_formateados}\n\n'
            f'--- DOCUMENTO A REVISAR ({num_paginas} página(s)) ---\n'
            f'A continuación se adjuntan las imágenes de cada página del documento. '
            f'Revisa el documento visualmente siguiendo las instrucciones del sistema. '
            f'NO valides firmas ni sellos.'
        )
    ))

    # Imágenes de cada página
    for i, img_bytes in enumerate(imagenes_bytes, 1):
        parts.append(genai_types.Part.from_bytes(
            data=img_bytes,
            mime_type='image/png',
        ))
        # Etiqueta de separación entre páginas (en texto)
        if i < num_paginas:
            parts.append(genai_types.Part.from_text(text=f'[Fin página {i}]'))

    # 4. Llamar a la API de Gemini
    client = genai.Client(api_key=api_key)
    config = genai_types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type='application/json',
    )

    try:
        response = client.models.generate_content(
            model=_MODELO,
            contents=[
                genai_types.Content(role='user', parts=parts)
            ],
            config=config,
        )
    except Exception as e:
        error_str = str(e).lower()
        es_cuota = (
            '429' in error_str
            or 'resource_exhausted' in error_str
            or 'quota' in error_str
            or ('rate' in error_str and 'limit' in error_str)
        )
        if es_cuota:
            raise QuotaExhaustedError(
                'Se alcanzó el límite de la API key actual. '
                'Ingrese una nueva API key en la barra lateral para continuar.'
            ) from e
        raise

    # 5. Extraer uso de tokens
    tokens_entrada = 0
    tokens_salida = 0
    try:
        meta = response.usage_metadata
        tokens_entrada = getattr(meta, 'prompt_token_count', 0) or 0
        tokens_salida = getattr(meta, 'candidates_token_count', 0) or 0
    except Exception:
        pass

    # 6. Parsear la respuesta JSON
    raw_text = response.text or ''
    resultado = _parsear_respuesta_gemini(raw_text)

    # 7. Añadir métricas de uso al resultado
    resultado['tokens_entrada'] = tokens_entrada
    resultado['tokens_salida'] = tokens_salida
    resultado['tokens_total'] = tokens_entrada + tokens_salida
    resultado['num_paginas'] = num_paginas

    return resultado
