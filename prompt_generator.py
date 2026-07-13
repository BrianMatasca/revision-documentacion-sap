"""
Módulo generador de prompts para el flujo manual-asistido.

Genera prompts completos listos para copiar y pegar en el chat de Gemini
para la revisión de documentos que requieren adjuntar el PDF directamente:
Presupuesto Detallado, Documento Técnico de Formulación Inicial y
Documento Técnico Soporte del Ajuste.
"""

from pathlib import Path
from typing import Union

import mga_parser


# Nombres legibles de cada tipo de documento
NOMBRES_DOCUMENTO = {
    'presupuesto': 'Presupuesto Detallado',
    'documento_tecnico': 'Documento Técnico de Formulación Inicial',
    'documento_tecnico_ajuste': 'Documento Técnico Soporte del Ajuste',
}


def _leer_archivo_formato(formato_dir: Union[str, Path], nombre_archivo: str) -> str:
    """
    Lee un archivo de la carpeta del formato.

    Args:
        formato_dir: Ruta a la carpeta del formato.
        nombre_archivo: Nombre del archivo a leer (ej. 'formato.md', 'prompt.md').

    Returns:
        Contenido del archivo como string, o mensaje indicativo si no existe.
    """
    ruta = Path(formato_dir) / nombre_archivo
    try:
        return ruta.read_text(encoding='utf-8')
    except FileNotFoundError:
        return f'[Archivo {nombre_archivo} no encontrado en {formato_dir}]'
    except Exception as e:
        return f'[Error al leer {nombre_archivo}: {e}]'


def generar_prompt_manual(
    tipo_documento: str,
    datos_mga: dict,
    formato_dir: Union[str, Path],
) -> str:
    """
    Genera un prompt completo para copiar y pegar en el chat de Gemini.

    Combina las instrucciones, los datos del proyecto extraídos de la MGA,
    el formato base de referencia y los criterios de revisión en un único
    bloque de texto listo para usar.

    Args:
        tipo_documento: Tipo de documento: 'presupuesto', 'documento_tecnico'
                        o 'documento_tecnico_ajuste'.
        datos_mga: Diccionario con datos parseados del XML MGA.
        formato_dir: Ruta a la carpeta del formato (contiene formato.md y prompt.md).

    Returns:
        Prompt completo como string, listo para copiar y pegar en Gemini.
    """
    # Obtener el nombre legible del documento
    nombre_documento = NOMBRES_DOCUMENTO.get(tipo_documento, tipo_documento)

    # Leer archivos del formato
    contenido_formato = _leer_archivo_formato(formato_dir, 'formato.md')
    contenido_prompt = _leer_archivo_formato(formato_dir, 'prompt.md')

    # Formatear datos de la MGA para incluir en el prompt
    datos_mga_formateados = mga_parser.formatear_datos_mga_para_prompt(datos_mga)

    # Construir el prompt completo
    prompt = (
        f'=== INSTRUCCIONES PARA EL REVISOR ===\n'
        f'Copia TODO este texto y pégalo en el chat de Gemini (gemini.google.com),\n'
        f'luego adjunta el PDF del {nombre_documento} en el mismo mensaje.\n'
        f'\n'
        f'=== DATOS DEL PROYECTO (extraídos del XML MGA - fuente de verdad) ===\n'
        f'{datos_mga_formateados}\n'
        f'\n'
        f'=== FORMATO BASE DE REFERENCIA ===\n'
        f'{contenido_formato}\n'
        f'\n'
        f'=== CRITERIOS DE REVISIÓN ===\n'
        f'{contenido_prompt}\n'
        f'\n'
        f'IMPORTANTE: NO valides firmas ni sellos — eso se revisa de forma visual.\n'
        f'Enfócate en: coherencia de datos con la MGA, completitud de secciones,\n'
        f'consistencia entre valores declarados en el documento vs. datos de la MGA.'
    )

    return prompt
