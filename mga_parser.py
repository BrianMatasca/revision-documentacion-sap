"""
mga_parser.py
─────────────
Módulo para parsear archivos XML exportados desde la plataforma MGA
(Metodología General Ajustada) del DNP de Colombia.

Utiliza xml.etree.ElementTree para recorrer la estructura del XML y
extraer todos los datos clave del proyecto de inversión pública.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any


# ──────────────────────────────────────────────────────────────────────
# Helpers internos
# ──────────────────────────────────────────────────────────────────────

def _txt(elemento: ET.Element | None, ruta: str, default: str = "") -> str:
    """Obtiene el texto de un sub-elemento dado por *ruta* XPath simple."""
    if elemento is None:
        return default
    nodo = elemento.find(ruta)
    if nodo is not None and nodo.text:
        return nodo.text.strip()
    return default


def _float(texto: str) -> float:
    """Convierte texto a float; devuelve 0.0 si falla."""
    try:
        return float(texto.replace(",", "."))
    except (ValueError, AttributeError):
        return 0.0


# ──────────────────────────────────────────────────────────────────────
# Función principal de parseo
# ──────────────────────────────────────────────────────────────────────

def parsear_mga_xml(xml_bytes: bytes) -> dict[str, Any]:
    """Parsea el XML de la MGA y extrae todos los datos clave del proyecto.

    Parámetros
    ----------
    xml_bytes : bytes
        Contenido crudo del archivo XML exportado desde la MGA.

    Retorna
    -------
    dict
        Diccionario con las siguientes claves:
        nombre_proyecto, bpin, objetivo_general, sector, entidad,
        programa, periodo_cero, poblacion_afectada, poblacion_objetivo,
        problema_central, causas_directas, causas_indirectas,
        objetivos_especificos, productos, valor_total,
        fuentes_financiacion, localizacion, plan_desarrollo,
        indicadores_gestion, riesgos, demografia.
    """
    root = ET.fromstring(xml_bytes)

    # ── Datos generales ──────────────────────────────────────────────
    nombre_proyecto = _txt(root, "Name")
    bpin = _txt(root, "BPIN")
    objeto = _txt(root, "Object")
    sector = _txt(root, "Sector/Description") or _txt(root, "SectorId")
    entidad = _txt(root, "Entity/Name")
    programa = _txt(root, "Program")
    periodo_cero = _txt(root, "PeriodZero")
    fase = _txt(root, "Phase/Name")
    poblacion_afectada = _txt(root, "AffectedPeople")
    poblacion_objetivo = _txt(root, "ObjectivePeople")

    # ── Problema central y causas ────────────────────────────────────
    problema_central = _txt(root, "CentralProblem/CentralProblem")
    causas_directas: list[str] = []
    causas_indirectas: list[str] = []
    objetivos_especificos: list[str] = []

    for causa in root.findall(".//CentralProblem/Causes/Cause"):
        tipo_id = _txt(causa, "CauseEffectTypeId")
        descripcion = _txt(causa, "Description") or _txt(causa, "Cause")
        if not descripcion:
            # Algunas versiones usan el texto directo del nodo
            descripcion = causa.text.strip() if causa.text else ""

        if tipo_id == "1":
            causas_directas.append(descripcion)
        elif tipo_id == "3":
            causas_indirectas.append(descripcion)
        else:
            # Si no hay tipo definido, se agrega como directa por defecto
            if descripcion:
                causas_directas.append(descripcion)

        # Objetivo específico asociado a la causa
        obj_esp = _txt(causa, "SpecificObjective/SpecificObjective")
        if obj_esp and obj_esp not in objetivos_especificos:
            objetivos_especificos.append(obj_esp)

    # ── Objetivo general ─────────────────────────────────────────────
    objetivo_general = _txt(root, "GeneralObjective/GeneralObjective")

    # ── Alternativas → Productos y Actividades ───────────────────────
    productos: list[dict[str, Any]] = []
    riesgos: list[dict[str, str]] = []

    for alt in root.findall(".//Alternatives/Alternative"):
        # Filtrar solo la alternativa seleccionada / enviada a preparación
        enviada = _txt(alt, "SendToPreparation")
        seleccionada = _txt(alt, "IsSelected")
        if enviada not in ("1", "true", "True", "") and seleccionada not in ("1", "true", "True", ""):
            continue

        # Productos
        for prod in alt.findall(".//Products/Product"):
            actividades: list[dict[str, Any]] = []
            for act in prod.findall(".//Activities/Activity"):
                actividades.append({
                    "nombre": _txt(act, "Name"),
                    "costo": _float(_txt(act, "Cost")),
                })

            productos.append({
                "nombre": _txt(prod, "ProductName"),
                "meta": _txt(prod, "Amount"),
                "indicador": _txt(prod, "AutoIndicatorName"),
                "actividades": actividades,
            })

        # Riesgos
        for riesgo in alt.findall(".//Risks/Risk"):
            riesgos.append({
                "descripcion": _txt(riesgo, "Description"),
                "tipo": _txt(riesgo, "RiskType/Description"),
                "probabilidad": _txt(riesgo, "Probability/Description"),
                "impacto": _txt(riesgo, "Impact/Description"),
            })

    # ── Valor total (suma de costos de actividades) ──────────────────
    valor_total = sum(
        act["costo"]
        for prod in productos
        for act in prod.get("actividades", [])
    )

    # ── Fuentes de financiación ──────────────────────────────────────
    fuentes_financiacion: list[dict[str, Any]] = []
    for fuente in root.findall(".//FundingSource/Sources/Source"):
        montos: list[dict[str, Any]] = []
        for prog in fuente.findall(".//SourceProgrammings/SourceProgramming"):
            montos.append({
                "periodo": _txt(prog, "Period"),
                "monto": _float(_txt(prog, "Amount")),
            })

        fuentes_financiacion.append({
            "tipo": _txt(fuente, "ResourceType/Description"),
            "entidad": _txt(fuente, "EntityTypeCatalogOption/Name"),
            "montos": montos,
        })

    # ── Localización ─────────────────────────────────────────────────
    localizacion: list[dict[str, str]] = []
    for loc in root.findall(".//Localizations/Localization"):
        localizacion.append({
            "region": _txt(loc, "Region/Name"),
            "departamento": _txt(loc, "Department/Name"),
            "municipio": _txt(loc, "Municipality/Name"),
            "centro_poblado": _txt(loc, "PopulationCenter/Name"),
            "especifica": _txt(loc, "SpecificLocalization"),
            "tipo_id": _txt(loc, "LocalizationTypeId"),
        })

    # ── Plan de desarrollo ───────────────────────────────────────────
    plan_desarrollo = _txt(root, "PublicationContribution/DevelopmentPlan")

    # ── Indicadores de gestión ───────────────────────────────────────
    indicadores_gestion: list[str] = []
    for ind in root.findall(".//ManagementIndicators/ManagementIndicator"):
        desc = _txt(ind, "Description")
        if desc:
            indicadores_gestion.append(desc)

    # ── Demografía ───────────────────────────────────────────────────
    demografia: list[dict[str, Any]] = []
    for dem in root.findall(".//DemographicCharacteristics/DemographicCharacteristic"):
        demografia.append({
            "tipo": _txt(dem, "CharacteristicType/Description"),
            "clasificacion": _txt(dem, "CharacteristiClassification/Description"),
            "numero_personas": _txt(dem, "NumberOfPeople"),
        })

    # ── Resultado final ──────────────────────────────────────────────
    return {
        "nombre_proyecto": nombre_proyecto,
        "bpin": bpin,
        "objeto": objeto,
        "objetivo_general": objetivo_general,
        "sector": sector,
        "entidad": entidad,
        "programa": programa,
        "periodo_cero": periodo_cero,
        "fase": fase,
        "poblacion_afectada": poblacion_afectada,
        "poblacion_objetivo": poblacion_objetivo,
        "problema_central": problema_central,
        "causas_directas": causas_directas,
        "causas_indirectas": causas_indirectas,
        "objetivos_especificos": objetivos_especificos,
        "productos": productos,
        "valor_total": valor_total,
        "fuentes_financiacion": fuentes_financiacion,
        "localizacion": localizacion,
        "plan_desarrollo": plan_desarrollo,
        "indicadores_gestion": indicadores_gestion,
        "riesgos": riesgos,
        "demografia": demografia,
    }


# ──────────────────────────────────────────────────────────────────────
# Cálculo del valor total
# ──────────────────────────────────────────────────────────────────────

def calcular_valor_total(datos: dict[str, Any]) -> float:
    """Calcula el valor total sumando los costos de todas las actividades.

    Parámetros
    ----------
    datos : dict
        Diccionario retornado por ``parsear_mga_xml``.

    Retorna
    -------
    float
        Suma de los costos de todas las actividades.
    """
    total = 0.0
    for producto in datos.get("productos", []):
        for actividad in producto.get("actividades", []):
            total += actividad.get("costo", 0.0)
    return total


# ──────────────────────────────────────────────────────────────────────
# Formateo para prompts de Gemini
# ──────────────────────────────────────────────────────────────────────

def formatear_datos_mga_para_prompt(datos: dict[str, Any]) -> str:
    """Genera un texto legible con los datos de la MGA para inyectar en
    prompts de Gemini.

    El formato resultante se usa tanto en flujos automatizados como en
    revisión asistida manual.

    Parámetros
    ----------
    datos : dict
        Diccionario retornado por ``parsear_mga_xml``.

    Retorna
    -------
    str
        Texto formateado con todas las secciones del proyecto.
    """
    lineas: list[str] = []

    def _seccion(titulo: str) -> None:
        lineas.append(f"\n{'='*60}")
        lineas.append(f"  {titulo}")
        lineas.append(f"{'='*60}")

    def _campo(etiqueta: str, valor: Any) -> None:
        if valor:
            lineas.append(f"  {etiqueta}: {valor}")

    # ── Información general ──────────────────────────────────────────
    _seccion("INFORMACIÓN GENERAL DEL PROYECTO")
    _campo("Nombre del proyecto", datos.get("nombre_proyecto"))
    _campo("BPIN", datos.get("bpin"))
    _campo("Objeto", datos.get("objeto"))
    _campo("Sector", datos.get("sector"))
    _campo("Entidad", datos.get("entidad"))
    _campo("Programa", datos.get("programa"))
    _campo("Periodo cero", datos.get("periodo_cero"))
    _campo("Fase", datos.get("fase"))
    _campo("Población afectada", datos.get("poblacion_afectada"))
    _campo("Población objetivo", datos.get("poblacion_objetivo"))
    _campo("Plan de desarrollo", datos.get("plan_desarrollo"))

    # ── Problema central ─────────────────────────────────────────────
    _seccion("PROBLEMA CENTRAL")
    _campo("Descripción", datos.get("problema_central"))

    if datos.get("causas_directas"):
        lineas.append("\n  Causas directas:")
        for i, c in enumerate(datos["causas_directas"], 1):
            lineas.append(f"    {i}. {c}")

    if datos.get("causas_indirectas"):
        lineas.append("\n  Causas indirectas:")
        for i, c in enumerate(datos["causas_indirectas"], 1):
            lineas.append(f"    {i}. {c}")

    # ── Objetivos ────────────────────────────────────────────────────
    _seccion("OBJETIVOS")
    _campo("Objetivo general", datos.get("objetivo_general"))

    if datos.get("objetivos_especificos"):
        lineas.append("\n  Objetivos específicos:")
        for i, obj in enumerate(datos["objetivos_especificos"], 1):
            lineas.append(f"    {i}. {obj}")

    # ── Productos y actividades ──────────────────────────────────────
    _seccion("PRODUCTOS Y ACTIVIDADES")
    for i, prod in enumerate(datos.get("productos", []), 1):
        lineas.append(f"\n  Producto {i}: {prod.get('nombre', 'Sin nombre')}")
        _campo("    Meta", prod.get("meta"))
        _campo("    Indicador", prod.get("indicador"))
        if prod.get("actividades"):
            lineas.append("    Actividades:")
            for j, act in enumerate(prod["actividades"], 1):
                costo_fmt = f"${act.get('costo', 0):,.0f}"
                lineas.append(f"      {j}. {act.get('nombre', 'Sin nombre')} — Costo: {costo_fmt}")

    valor_total = datos.get("valor_total", 0)
    lineas.append(f"\n  VALOR TOTAL DEL PROYECTO (suma de todas las vigencias): ${valor_total:,.0f}")

    # Desglose de valor por vigencia (periodo_cero + offset)
    try:
        periodo_cero = int(datos.get("periodo_cero") or 0)
    except (ValueError, TypeError):
        periodo_cero = 0

    valores_por_periodo: dict[int, float] = {}
    for fuente in datos.get("fuentes_financiacion", []):
        for m in fuente.get("montos", []):
            try:
                p = int(m.get("periodo", -1))
                valores_por_periodo[p] = valores_por_periodo.get(p, 0.0) + m.get("monto", 0.0)
            except (ValueError, TypeError):
                pass

    if valores_por_periodo:
        lineas.append("\n  VALOR FINANCIADO POR VIGENCIA (para comparar contra valores anuales declarados en documentos):")
        lineas.append("  NOTA: Los documentos declaran el valor de UNA sola vigencia. Use la fila correspondiente.")
        for p in sorted(valores_por_periodo):
            anio = periodo_cero + p if periodo_cero else p
            lineas.append(f"    Vigencia {anio} (Periodo {p}): ${valores_por_periodo[p]:,.0f}")

    # ── Fuentes de financiación ──────────────────────────────────────
    if datos.get("fuentes_financiacion"):
        _seccion("FUENTES DE FINANCIACIÓN")
        for i, fuente in enumerate(datos["fuentes_financiacion"], 1):
            lineas.append(f"\n  Fuente {i}:")
            _campo("    Tipo de recurso", fuente.get("tipo"))
            _campo("    Entidad", fuente.get("entidad"))
            if fuente.get("montos"):
                lineas.append("    Programación:")
                for m in fuente["montos"]:
                    lineas.append(f"      Periodo {m.get('periodo', '?')}: ${m.get('monto', 0):,.0f}")

    # ── Localización ─────────────────────────────────────────────────
    if datos.get("localizacion"):
        _seccion("LOCALIZACIÓN")
        for i, loc in enumerate(datos["localizacion"], 1):
            partes = []
            if loc.get("departamento"):
                partes.append(loc["departamento"])
            if loc.get("municipio"):
                partes.append(loc["municipio"])
            if loc.get("centro_poblado"):
                partes.append(loc["centro_poblado"])
            if loc.get("especifica"):
                partes.append(loc["especifica"])
            lineas.append(f"  {i}. {' > '.join(partes) if partes else 'Sin especificar'}")

    # ── Indicadores de gestión ───────────────────────────────────────
    if datos.get("indicadores_gestion"):
        _seccion("INDICADORES DE GESTIÓN")
        for i, ind in enumerate(datos["indicadores_gestion"], 1):
            lineas.append(f"  {i}. {ind}")

    # ── Riesgos ──────────────────────────────────────────────────────
    if datos.get("riesgos"):
        _seccion("RIESGOS")
        for i, r in enumerate(datos["riesgos"], 1):
            lineas.append(f"\n  Riesgo {i}: {r.get('descripcion', 'Sin descripción')}")
            _campo("    Tipo", r.get("tipo"))
            _campo("    Probabilidad", r.get("probabilidad"))
            _campo("    Impacto", r.get("impacto"))

    # ── Demografía ───────────────────────────────────────────────────
    if datos.get("demografia"):
        _seccion("DEMOGRAFÍA")
        for i, d in enumerate(datos["demografia"], 1):
            lineas.append(
                f"  {i}. {d.get('tipo', '')} — {d.get('clasificacion', '')} "
                f"— Personas: {d.get('numero_personas', '0')}"
            )

    return "\n".join(lineas)


# ──────────────────────────────────────────────────────────────────────
# Resumen para la UI
# ──────────────────────────────────────────────────────────────────────

def formatear_datos_mga_resumen(datos: dict[str, Any]) -> dict[str, Any]:
    """Genera un diccionario con datos resumidos para la interfaz de usuario.

    Parámetros
    ----------
    datos : dict
        Diccionario retornado por ``parsear_mga_xml``.

    Retorna
    -------
    dict
        Resumen con nombre, bpin, valor_total formateado, sector,
        entidad, número de productos y localizaciones.
    """
    valor_total = datos.get("valor_total", 0)
    num_productos = len(datos.get("productos", []))
    num_actividades = sum(
        len(p.get("actividades", []))
        for p in datos.get("productos", [])
    )
    num_localizaciones = len(datos.get("localizacion", []))

    return {
        "nombre_proyecto": datos.get("nombre_proyecto", "Sin nombre"),
        "bpin": datos.get("bpin", "Sin BPIN"),
        "valor_total": f"${valor_total:,.0f}",
        "valor_total_numerico": valor_total,
        "sector": datos.get("sector", "Sin sector"),
        "entidad": datos.get("entidad", "Sin entidad"),
        "programa": datos.get("programa", ""),
        "periodo_cero": datos.get("periodo_cero", ""),
        "objetivo_general": datos.get("objetivo_general", ""),
        "num_productos": num_productos,
        "num_actividades": num_actividades,
        "num_localizaciones": num_localizaciones,
        "num_riesgos": len(datos.get("riesgos", [])),
        "num_fuentes": len(datos.get("fuentes_financiacion", [])),
    }
