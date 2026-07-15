"""
Revisor de Documentos de Inversión Pública
Gobernación del Valle del Cauca · Departamento Administrativo de Planeación

Aplicación Streamlit que automatiza la validación de documentos de proyectos
de inversión pública radicados en SAP ante el DAP.
"""

import os
import streamlit as st
from pathlib import Path
from dotenv import load_dotenv

# Módulos propios
from mga_parser import parsear_mga_xml, formatear_datos_mga_resumen
from sap_client import descargar_documento_sap, SAPError, SAPAuthError
from revision_automatizada import revisar_documento, QuotaExhaustedError
from prompt_generator import generar_prompt_manual

# ── Cargar variables de entorno ─────────────────────────────────────────────
load_dotenv()

# ── Configuración de página ─────────────────────────────────────────────────
st.set_page_config(
    page_title="Revisor de Documentos — DAP",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Constantes ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
FORMATOS_DIR = BASE_DIR / "formatos"

# Documentos del flujo automatizado (se envían a la API de Gemini)
DOCS_AUTOMATIZADOS = {
    "presentacion": {
        "nombre": "Carta de Presentación",
        "icono": "📄",
        "dir": FORMATOS_DIR / "presentacion",
    },
    "verificacion": {
        "nombre": "Verificación de Requisitos",
        "icono": "✅",
        "dir": FORMATOS_DIR / "verificacion",
    },
    "viabilidad": {
        "nombre": "Viabilidad del Proyecto",
        "icono": "📊",
        "dir": FORMATOS_DIR / "viabilidad",
    },
}

# Documentos del flujo manual asistido (se genera prompt para copiar/pegar)
DOCS_MANUALES = {
    "presupuesto": {
        "nombre": "Presupuesto Detallado",
        "icono": "💰",
        "dir": FORMATOS_DIR / "presupuesto",
    },
    "documento_tecnico": {
        "nombre": "Documento Técnico Inicial",
        "icono": "📑",
        "dir": FORMATOS_DIR / "documento_tecnico",
    },
    "documento_tecnico_ajuste": {
        "nombre": "Documento Técnico de Ajuste",
        "icono": "🔄",
        "dir": FORMATOS_DIR / "documento_tecnico_ajuste",
    },
}

# ── CSS personalizado ───────────────────────────────────────────────────────
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
    html, body {
        font-family: 'Inter', sans-serif;
    }

    .stApp {
        font-family: 'Inter', sans-serif;
    }
    
    /* ── Encabezado principal ───────────────────────────────── */
    .main-header {
        background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%);
        color: white;
        padding: 1.8rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 20px rgba(0,0,0,0.15);
    }
    .main-header h1 {
        margin: 0;
        font-size: 1.5rem;
        font-weight: 700;
        letter-spacing: -0.02em;
        color: white !important;
    }
    .main-header p {
        margin: 0.4rem 0 0;
        font-size: 0.85rem;
        opacity: 0.8;
        font-weight: 400;
        color: white !important;
    }

    /* ── Card de resumen del proyecto ──────────────────────── */
    .project-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 15px rgba(102,126,234,0.3);
    }
    .project-card h3 {
        margin: 0 0 0.8rem;
        font-size: 1.1rem;
        font-weight: 600;
        color: white !important;
    }
    .project-card .field {
        display: flex;
        justify-content: space-between;
        padding: 0.3rem 0;
        font-size: 0.85rem;
        border-bottom: 1px solid rgba(255,255,255,0.15);
        color: white !important;
    }
    .project-card .field:last-child { border-bottom: none; }
    .project-card .field .label { opacity: 0.8; }
    .project-card .field .value { font-weight: 600; }

    /* ── Badges de estado ─────────────────────────────────── */
    .badge {
        display: inline-block;
        padding: 5px 14px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.82rem;
        letter-spacing: 0.02em;
    }
    .badge-ok {
        background: #d4edda;
        color: #155724 !important;
    }
    .badge-errores {
        background: #f8d7da;
        color: #721c24 !important;
    }
    .badge-manual {
        background: #fff3cd;
        color: #856404 !important;
    }
    .badge-pendiente {
        background: #e2e3e5;
        color: #383d41 !important;
    }
    .badge-prompt {
        background: #d1ecf1;
        color: #0c5460 !important;
    }

    /* ── Bloqueo visual (compatible con light y dark) ─────── */
    .blocked-overlay {
        border: 2px dashed rgba(128,128,128,0.4);
        border-radius: 12px;
        padding: 2rem;
        text-align: center;
    }
    .blocked-overlay h4 { margin: 0.5rem 0; }
    .blocked-overlay p { margin: 0; font-size: 0.9rem; }

    /* ── Hallazgos (compatible con light y dark) ──────────── */
    .hallazgo-item {
        padding: 0.5rem 0.8rem;
        margin: 0.3rem 0;
        border-left: 3px solid #667eea;
        background: rgba(128,128,128,0.08);
        border-radius: 0 6px 6px 0;
        font-size: 0.88rem;
    }
</style>
""", unsafe_allow_html=True)


# ── Inicializar session_state ───────────────────────────────────────────────
def init_session_state():
    """Inicializa todas las variables de sesión necesarias."""
    defaults = {
        "api_key": os.environ.get("GEMINI_API_KEY", ""),
        "sap_user": "",
        "sap_password": "",
        "mga_datos": None,         # dict con datos parseados del XML
        "mga_nombre": None,        # nombre del archivo XML cargado
        # Documentos cargados: {tipo: {"bytes": bytes, "nombre": str}}
        "docs_cargados": {},
        # Resultados de revisión automatizada: {tipo: dict}
        "resultados_auto": {},
        # Prompts generados para flujo manual: {tipo: str}
        "prompts_manuales": {},
        # Documento genérico descargado de SAP: {"bytes": bytes, "nombre": str, "url": str}
        "generic_sap_doc": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_session_state()


# ── Sidebar ─────────────────────────────────────────────────────────────────
def render_sidebar():
    """Renderiza la barra lateral con configuración."""
    with st.sidebar:
        st.markdown("## ⚙️ Configuración")

        # ── API Key de Gemini ──
        st.markdown("#### 🔑 API Key de Gemini")
        api_input = st.text_input(
            "Clave API",
            type="password",
            value=st.session_state["api_key"],
            help="Obténgala en Google AI Studio (aistudio.google.com). "
                 "Puede cambiarla en cualquier momento sin perder el progreso.",
            placeholder="AIza...",
            label_visibility="collapsed",
        )
        if api_input != st.session_state["api_key"]:
            st.session_state["api_key"] = api_input
        if st.session_state["api_key"]:
            st.success("API Key configurada", icon="✅")
        else:
            st.warning("Ingrese su API Key para el flujo automatizado", icon="⚠️")

        st.divider()

        # ── Credenciales SAP ──
        st.markdown("#### 🔐 Credenciales SAP")
        with st.expander("Configurar credenciales", expanded=False):
            sap_user = st.text_input(
                "Usuario SAP",
                value=st.session_state["sap_user"],
                key="sidebar_sap_user",
            )
            sap_pwd = st.text_input(
                "Contraseña SAP",
                type="password",
                value=st.session_state["sap_password"],
                key="sidebar_sap_pwd",
            )
            if sap_user != st.session_state["sap_user"]:
                st.session_state["sap_user"] = sap_user
            if sap_pwd != st.session_state["sap_password"]:
                st.session_state["sap_password"] = sap_pwd

            if st.session_state["sap_user"] and st.session_state["sap_password"]:
                st.success("Credenciales configuradas", icon="✅")

        st.divider()

        # ── Carga del XML MGA ──
        st.markdown("#### 📋 XML de la MGA")
        st.caption("**Obligatorio** — Fuente de verdad del proyecto.")
        mga_file = st.file_uploader(
            "Cargar XML de la MGA",
            type=["xml"],
            help="Archivo XML exportado de la plataforma MGA del DNP.",
            label_visibility="collapsed",
        )

        if mga_file is not None:
            mga_bytes = mga_file.read()
            # Solo re-parsear si es un archivo nuevo
            if st.session_state["mga_nombre"] != mga_file.name:
                try:
                    datos = parsear_mga_xml(mga_bytes)
                    st.session_state["mga_datos"] = datos
                    st.session_state["mga_nombre"] = mga_file.name
                    # Limpiar resultados previos al cambiar de proyecto
                    st.session_state["resultados_auto"] = {}
                    st.session_state["prompts_manuales"] = {}
                    st.session_state["docs_cargados"] = {}
                    st.success(f"✅ {mga_file.name} cargado correctamente")
                except Exception as e:
                    st.error(f"Error al parsear el XML: {e}")
                    st.session_state["mga_datos"] = None
                    st.session_state["mga_nombre"] = None
        else:
            # Si el uploader está vacío, limpiar datos
            if st.session_state["mga_datos"] is not None:
                st.session_state["mga_datos"] = None
                st.session_state["mga_nombre"] = None

        if st.session_state["mga_datos"]:
            resumen = formatear_datos_mga_resumen(st.session_state["mga_datos"])
            st.info(
                f"**{resumen.get('nombre_proyecto', 'Sin nombre')[:60]}...**\n\n"
                f"BPIN: `{resumen.get('bpin', 'N/D')}`\n\n"
                f"Valor: `{resumen.get('valor_total', 'N/D')}`",
                icon="📋",
            )
        else:
            st.info("Sin MGA cargado", icon="📋")

        # ── Guía de Usuario ──
        st.divider()
        st.markdown("#### 📖 Guía de Usuario")
        try:
            ruta_guia = BASE_DIR / "guia.pdf"
            if ruta_guia.exists():
                with open(ruta_guia, "rb") as f:
                    pdf_bytes = f.read()
                st.download_button(
                    label="📥 Descargar Guía (PDF)",
                    data=pdf_bytes,
                    file_name="guia.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            else:
                st.caption("⚠️ Archivo guia.pdf no encontrado en el proyecto.")
        except Exception as e:
            st.error(f"Error al cargar la guía: {e}")



# ── Encabezado principal ────────────────────────────────────────────────────
def render_header():
    """Renderiza el encabezado principal de la aplicación."""
    st.markdown("""
    <div class="main-header">
        <h1>📋 Revisor de Documentos de Inversión Pública</h1>
        <p>Gobernación del Valle del Cauca · Departamento Administrativo de Planeación · Subdirección de Inversión Pública</p>
    </div>
    """, unsafe_allow_html=True)


# ── Card de resumen del proyecto ────────────────────────────────────────────
def render_project_card():
    """Muestra un card con los datos clave del proyecto (MGA)."""
    if not st.session_state["mga_datos"]:
        return

    resumen = formatear_datos_mga_resumen(st.session_state["mga_datos"])
    nombre = resumen.get("nombre_proyecto", "Sin nombre")
    bpin = resumen.get("bpin", "N/D")
    valor = resumen.get("valor_total", "N/D")
    sector = resumen.get("sector", "N/D")
    entidad = resumen.get("entidad", "N/D")
    vigencia = resumen.get("periodo_cero", "N/D")
    n_prod = resumen.get("num_productos", 0)
    n_act = resumen.get("num_actividades", 0)

    st.markdown(f"""
    <div class="project-card">
        <h3>📋 {nombre}</h3>
        <div class="field"><span class="label">BPIN</span><span class="value">{bpin}</span></div>
        <div class="field"><span class="label">Valor Total</span><span class="value">{valor}</span></div>
        <div class="field"><span class="label">Sector</span><span class="value">{sector}</span></div>
        <div class="field"><span class="label">Entidad</span><span class="value">{entidad}</span></div>
        <div class="field"><span class="label">Vigencia Base</span><span class="value">{vigencia}</span></div>
        <div class="field"><span class="label">Productos / Actividades</span><span class="value">{n_prod} / {n_act}</span></div>
    </div>
    """, unsafe_allow_html=True)


# ── Cargar documento (Link SAP o subir PDF) ────────────────────────────────
def render_carga_documento(tipo: str, nombre: str, icono: str):
    """Renderiza los controles de carga para un documento específico."""
    fuente = st.radio(
        "Fuente del documento",
        ["🔗 Link SAP (por defecto)", "📁 Subir PDF manual"],
        key=f"fuente_{tipo}",
        horizontal=True,
        label_visibility="collapsed",
    )

    if "Link SAP" in fuente:
        sap_url = st.text_input(
            "URL del documento en SAP",
            key=f"sap_url_{tipo}",
            placeholder="http://sappro-ci.valledelcauca.gov.co:8000/sap/...",
            label_visibility="collapsed",
        )
        if sap_url:
            if not st.session_state["sap_user"] or not st.session_state["sap_password"]:
                st.warning(
                    "Configure sus credenciales SAP en la barra lateral.",
                    icon="🔐",
                )
            else:
                if st.button(f"⬇️ Descargar desde SAP", key=f"dl_{tipo}"):
                    with st.spinner("Descargando desde SAP..."):
                        try:
                            pdf_bytes, filename = descargar_documento_sap(
                                sap_url,
                                st.session_state["sap_user"],
                                st.session_state["sap_password"],
                            )
                            st.session_state["docs_cargados"][tipo] = {
                                "bytes": pdf_bytes,
                                "nombre": filename,
                            }
                            st.success(f"✅ Descargado: {filename}")
                            st.rerun()
                        except SAPAuthError:
                            st.error(
                                "❌ Credenciales SAP incorrectas. "
                                "Verifique usuario y contraseña en la barra lateral."
                            )
                        except SAPError as e:
                            st.error(f"❌ Error SAP: {e}")
    else:
        # Inicializar uploader_version para resetear el widget cuando sea necesario
        if "uploader_version" not in st.session_state:
            st.session_state["uploader_version"] = {}
        version = st.session_state["uploader_version"].setdefault(tipo, 0)

        up = st.file_uploader(
            f"Subir PDF de {nombre}",
            type=["pdf"],
            key=f"upload_{tipo}_{version}",
            label_visibility="collapsed",
        )
        if up is not None:
            current_doc = st.session_state["docs_cargados"].get(tipo)
            if not current_doc or current_doc.get("nombre") != up.name:
                pdf_bytes = up.read()
                st.session_state["docs_cargados"][tipo] = {
                    "bytes": pdf_bytes,
                    "nombre": up.name,
                }
                # Limpiar resultados anteriores para forzar nueva revisión
                st.session_state["resultados_auto"].pop(tipo, None)
                st.rerun()
        else:
            # Si el uploader está vacío pero hay un documento cargado localmente,
            # lo quitamos de la memoria porque el usuario lo borró del widget
            if tipo in st.session_state["docs_cargados"]:
                st.session_state["docs_cargados"].pop(tipo, None)
                st.session_state["resultados_auto"].pop(tipo, None)
                st.rerun()

    # Mostrar estado del documento cargado
    doc = st.session_state["docs_cargados"].get(tipo)
    if doc:
        col_file, col_clear = st.columns([4, 1])
        with col_file:
            st.caption(f"📎 **{doc['nombre']}** · {len(doc['bytes']):,} bytes")
        with col_clear:
            if st.button("🗑️ Quitar", key=f"clear_{tipo}", use_container_width=True):
                st.session_state["docs_cargados"].pop(tipo, None)
                st.session_state["resultados_auto"].pop(tipo, None)
                if "uploader_version" in st.session_state and tipo in st.session_state["uploader_version"]:
                    st.session_state["uploader_version"][tipo] += 1
                st.rerun()
        return True
    return False


# ── Sección: Flujo Automatizado ─────────────────────────────────────────────
def render_flujo_automatizado():
    """Renderiza la sección de documentos que se revisan con la API de Gemini."""
    st.markdown("### 🤖 Revisión Automatizada")
    st.caption(
        "Estos documentos se revisan automáticamente usando la API de Gemini. "
        "Se extrae el texto del PDF y se valida contra los datos de la MGA."
    )

    docs_listos = {}

    for tipo, info in DOCS_AUTOMATIZADOS.items():
        with st.expander(f"{info['icono']} {info['nombre']}", expanded=False):
            esta_cargado = render_carga_documento(tipo, info["nombre"], info["icono"])
            docs_listos[tipo] = esta_cargado

            # Mostrar resultado previo si existe
            resultado = st.session_state["resultados_auto"].get(tipo)
            if resultado:
                _render_resultado(resultado)

    # Botón de revisión masiva
    hay_docs = any(docs_listos.values())
    tiene_api_key = bool(st.session_state["api_key"])

    col1, col2 = st.columns([3, 1])
    with col1:
        if not tiene_api_key and hay_docs:
            st.warning("Configure la API Key de Gemini en la barra lateral.", icon="🔑")
    iniciar_revision = False
    with col2:
        puede_revisar = hay_docs and tiene_api_key
        if st.button(
            "🔍 Revisar documentos",
            type="primary",
            disabled=not puede_revisar,
            key="btn_revisar_auto",
            use_container_width=True,
        ):
            iniciar_revision = True
            
    if iniciar_revision:
        _ejecutar_revision_automatizada(docs_listos)


def _ejecutar_revision_automatizada(docs_listos: dict):
    """Ejecuta la revisión de todos los documentos cargados del flujo automatizado."""
    docs_a_revisar = {
        tipo: st.session_state["docs_cargados"][tipo]
        for tipo, listo in docs_listos.items()
        if listo
    }

    if not docs_a_revisar:
        st.warning("No hay documentos cargados para revisar.")
        return

    with st.status("🔄 Analizando documentos con Gemini AI…", expanded=True) as status:
        for tipo, doc_data in docs_a_revisar.items():
            info = DOCS_AUTOMATIZADOS[tipo]
            status.write(f"📄 Procesando {info['nombre']}...")

            try:
                # Enviar PDF como imágenes a Gemini Vision (sin paso OCR intermedio)
                status.write(f"   ↳ Convirtiendo PDF a imágenes y enviando a Gemini Vision...")
                resultado = revisar_documento(
                    api_key=st.session_state["api_key"],
                    pdf_bytes=doc_data["bytes"],
                    tipo_documento=tipo,
                    datos_mga=st.session_state["mga_datos"],
                    formato_dir=info["dir"],
                )
                st.session_state["resultados_auto"][tipo] = resultado
                # Log de consumo en el status
                tok = resultado.get('tokens_total', 0)
                pags = resultado.get('num_paginas', '?')
                status.write(f"   ✓ Completado: {pags} pág. · {tok:,} tokens totales")

            except QuotaExhaustedError as e:
                st.session_state["resultados_auto"][tipo] = {
                    "estado": "REVISION_MANUAL",
                    "resumen": str(e),
                    "hallazgos": [
                        "Se alcanzó el límite de cuota de la API key actual.",
                        "Ingrese una nueva API key en la barra lateral para continuar.",
                    ],
                    "recomendacion": "Cambie la API key y vuelva a intentar.",
                }
                st.error(
                    "⚠️ **Límite de cuota alcanzado.** "
                    "Ingrese una nueva API key en la barra lateral.",
                    icon="🔑",
                )
                break  # No intentar más documentos con esta key

            except Exception as e:
                st.session_state["resultados_auto"][tipo] = {
                    "estado": "REVISION_MANUAL",
                    "resumen": f"Error técnico: {e}",
                    "hallazgos": [str(e)],
                    "recomendacion": "Intente nuevamente o revise manualmente.",
                }

        status.update(
            label="✅ Revisión completada",
            state="complete",
            expanded=False,
        )
    st.rerun()


# ── Sección: Flujo Manual Asistido ──────────────────────────────────────────
def render_flujo_manual():
    """Renderiza la sección de documentos para revisión manual asistida."""
    st.markdown("### 📝 Revisión Manual Asistida")
    st.caption(
        "Estos documentos no se envían a la API. Copie el prompt generado y péguelo "
        "en el chat de Gemini con su licencia institucional, adjuntando el PDF del documento."
    )

    for tipo, info in DOCS_MANUALES.items():
        with st.expander(f"{info['icono']} {info['nombre']}", expanded=False):
            # Generar prompt automáticamente (no requiere subir PDF)
            if tipo not in st.session_state["prompts_manuales"]:
                try:
                    prompt = generar_prompt_manual(
                        tipo_documento=tipo,
                        datos_mga=st.session_state["mga_datos"],
                        formato_dir=info["dir"],
                    )
                    st.session_state["prompts_manuales"][tipo] = prompt
                except Exception as e:
                    st.error(f"Error al generar el prompt: {e}")
                    continue

            # Mostrar prompt generado
            prompt_texto = st.session_state["prompts_manuales"].get(tipo, "")
            if prompt_texto:
                st.markdown(
                    '<span class="badge badge-prompt">📋 Prompt generado</span>',
                    unsafe_allow_html=True,
                )
                st.markdown("")
                st.info(
                    "**Instrucciones:** Copie el prompt de abajo y péguelo en "
                    "[gemini.google.com](https://gemini.google.com), "
                    "luego adjunte el PDF del documento en el mismo mensaje.",
                    icon="💡",
                )
                st.code(prompt_texto, language=None)
                st.caption(
                    f"📊 Longitud del prompt: {len(prompt_texto):,} caracteres"
                )


# ── Renderizar resultado de revisión ────────────────────────────────────────
def _render_resultado(resultado: dict):
    """Renderiza el resultado de una revisión automatizada."""
    estado = resultado.get("estado", "REVISION_MANUAL")

    # Badge de estado
    badge_map = {
        "OK": ("badge-ok", "✅ Documento OK"),
        "ERRORES": ("badge-errores", "❌ Errores encontrados"),
        "REVISION_MANUAL": ("badge-manual", "⚠️ Revisión manual sugerida"),
    }
    badge_class, badge_text = badge_map.get(estado, ("badge-manual", "⚠️ Revisión manual"))

    # Fila: badge + métricas de tokens
    col_badge, col_tokens = st.columns([2, 1])
    with col_badge:
        st.markdown(f'<span class="badge {badge_class}">{badge_text}</span>', unsafe_allow_html=True)
    with col_tokens:
        tok_in = resultado.get('tokens_entrada', 0)
        tok_out = resultado.get('tokens_salida', 0)
        tok_total = resultado.get('tokens_total', 0)
        num_pags = resultado.get('num_paginas', None)
        if tok_total:
            detalle = f"{tok_in:,} entrada · {tok_out:,} salida"
            pag_txt = f" · {num_pags} pág." if num_pags else ""
            st.caption(f"🔢 **{tok_total:,}** tokens{pag_txt}  \n{detalle}")
    st.markdown("")

    # Resumen
    st.markdown(f"**Resumen:** {resultado.get('resumen', 'Sin resumen')}")

    # Hallazgos
    hallazgos = resultado.get("hallazgos", [])
    if hallazgos:
        st.markdown("**Hallazgos:**")
        for h in hallazgos:
            st.markdown(
                f'<div class="hallazgo-item">{h}</div>',
                unsafe_allow_html=True,
            )

    # Recomendación
    recomendacion = resultado.get("recomendacion", "")
    if recomendacion:
        st.markdown(f"**💡 Recomendación:** {recomendacion}")

# ── Panel de resultados consolidados ────────────────────────────────────────
def _comparar_codigos_pi(resultados: dict) -> dict:
    """
    Compara los códigos PI extraídos por Gemini en cada documento.

    Retorna un dict con:
        - codigos: {tipo_doc: codigo_pi_str | None}
        - coinciden: bool (True si todos los no-None son iguales)
        - valores_distintos: list[str] (valores únicos encontrados)
    """
    codigos = {
        tipo: r.get('codigo_pi')
        for tipo, r in resultados.items()
        if r.get('codigo_pi')  # Solo los que Gemini identificó
    }
    valores = list(set(codigos.values()))
    coinciden = len(valores) <= 1
    return {
        'codigos': {
            tipo: r.get('codigo_pi')
            for tipo, r in resultados.items()
        },
        'coinciden': coinciden,
        'valores_distintos': valores,
    }


def render_panel_resultados():
    """Renderiza el panel consolidado de resultados."""
    resultados = st.session_state["resultados_auto"]
    prompts = st.session_state["prompts_manuales"]

    if not resultados and not prompts:
        return

    st.divider()
    st.markdown("### 📊 Resumen de la Revisión")

    # Contadores
    total_ok = sum(1 for r in resultados.values() if r.get("estado") == "OK")
    total_err = sum(1 for r in resultados.values() if r.get("estado") == "ERRORES")
    total_manual = sum(1 for r in resultados.values() if r.get("estado") == "REVISION_MANUAL")
    total_prompts = len(prompts)

    cols = st.columns(5)
    with cols[0]:
        st.metric("✅ OK", total_ok)
    with cols[1]:
        st.metric("❌ Errores", total_err)
    with cols[2]:
        st.metric("⚠️ Rev. Manual", total_manual)
    with cols[3]:
        st.metric("📋 Prompts", total_prompts)
    with cols[4]:
        total_tokens = sum(
            r.get('tokens_total', 0) for r in resultados.values()
        )
        st.metric("🔢 Tokens usados", f"{total_tokens:,}")

    # ── Verificación de Código PI (programática, sin llamadas extra) ─
    if resultados:
        st.markdown("#### 🔑 Verificación de Código PI")
        pi_info = _comparar_codigos_pi(resultados)
        nombres_doc = {
            tipo: DOCS_AUTOMATIZADOS.get(tipo, {}).get('nombre', tipo)
            for tipo in resultados
        }

        # Tabla de códigos encontrados
        filas = []
        for tipo, codigo in pi_info['codigos'].items():
            filas.append({
                'Documento': nombres_doc.get(tipo, tipo),
                'Código PI detectado': codigo if codigo else '— no detectado —',
            })

        import pandas as pd
        df = pd.DataFrame(filas)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Resultado de la comparación
        codigos_encontrados = [c for c in pi_info['codigos'].values() if c]
        if not codigos_encontrados:
            st.warning(
                "⚠️ Gemini no detectó el Código PI en ningún documento. "
                "Verifíquelo manualmente.",
                icon="🔍",
            )
        elif pi_info['coinciden']:
            st.success(
                f"✅ Código PI consistente en todos los documentos: "
                f"**{pi_info['valores_distintos'][0]}**",
                icon="✅",
            )
        else:
            vals = " / ".join(f'`{v}`' for v in pi_info['valores_distintos'])
            st.error(
                f"❌ **Inconsistencia en Código PI.** "
                f"Se encontraron valores distintos: {vals}. "
                f"Verifique que todos los documentos correspondan al mismo proyecto.",
                icon="❌",
            )

    # Detalle por documento
    for tipo, resultado in resultados.items():
        info = DOCS_AUTOMATIZADOS.get(tipo, {})
        nombre = info.get("nombre", tipo)
        icono = info.get("icono", "📄")
        with st.expander(f"{icono} {nombre}", expanded=(resultado.get("estado") == "ERRORES")):
            _render_resultado(resultado)



# ── Descargador Genérico SAP ────────────────────────────────────────────────
def render_descargador_sap():
    """Renderiza la sección de utilidades para descargar documentos de SAP."""
    st.markdown("### 📥 Descargador Genérico de SAP")
    st.caption(
        "Esta utilidad le permite descargar cualquier documento PDF desde SAP usando las "
        "credenciales que configuró en el panel lateral."
    )

    # Verificar credenciales
    tiene_credenciales = (
        bool(st.session_state["sap_user"]) and bool(st.session_state["sap_password"])
    )

    if not tiene_credenciales:
        st.warning(
            "Configure sus credenciales SAP en la barra lateral para poder descargar archivos.",
            icon="🔐",
        )
        return

    url_descarga = st.text_input(
        "URL del documento SAP",
        key="sap_generic_download_url",
        placeholder="http://sappro-ci.valledelcauca.gov.co:8000/sap/...",
    )

    # Si la URL en el input cambia, limpiamos el caché de descarga
    cached = st.session_state["generic_sap_doc"]
    if cached and cached.get("url") != url_descarga:
        st.session_state["generic_sap_doc"] = None
        cached = None

    if url_descarga:
        col_btn, _ = st.columns([1, 3])
        with col_btn:
            btn_descargar = st.button("⬇️ Descargar archivo", key="btn_download_generic_sap", use_container_width=True)

        if btn_descargar:
            with st.spinner("Descargando archivo desde SAP..."):
                try:
                    pdf_bytes, filename = descargar_documento_sap(
                        url_descarga,
                        st.session_state["sap_user"],
                        st.session_state["sap_password"],
                    )
                    st.session_state["generic_sap_doc"] = {
                        "bytes": pdf_bytes,
                        "nombre": filename,
                        "url": url_descarga,
                    }
                    st.rerun()
                except SAPAuthError:
                    st.error(
                        "❌ Credenciales SAP incorrectas. "
                        "Verifique usuario y contraseña en la barra lateral."
                    )
                except SAPError as e:
                    st.error(f"❌ Error al descargar de SAP: {e}")

        # Si el documento ya fue descargado a memoria y la URL coincide, mostrar el botón de guardado
        cached = st.session_state["generic_sap_doc"]
        if cached and cached.get("url") == url_descarga:
            st.markdown("")
            st.success(f"✅ Documento obtenido: **{cached['nombre']}** ({len(cached['bytes']):,} bytes)")
            st.download_button(
                label=f"💾 Guardar {cached['nombre']} en mi computador",
                data=cached["bytes"],
                file_name=cached["nombre"],
                mime="application/pdf",
                use_container_width=True,
                key="btn_save_generic_sap",
            )


# ── Pantalla de bloqueo (sin MGA) ──────────────────────────────────────────
def render_bloqueo():
    """Muestra mensaje de bloqueo cuando no hay MGA cargado."""
    st.markdown("""
    <div class="blocked-overlay">
        <h4>📋 Cargue primero el XML de la MGA</h4>
        <p>
            El archivo XML de la MGA es la fuente de verdad del proyecto.<br>
            Cárguelo en la barra lateral izquierda para desbloquear la revisión de documentos.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("")
    st.markdown("""
    **¿Cómo funciona esta herramienta?**

    1. **Suba el XML de la MGA** → Se extraen automáticamente los datos del proyecto
    2. **Cargue los documentos** → Vía link SAP (por defecto) o subiendo el PDF
    3. **Revise automáticamente** → Carta, Verificación y Viabilidad se revisan con IA
    4. **Copie prompts** → Para Presupuesto, Doc. Técnico y Doc. Técnico Ajuste,
       se genera un prompt para usar en el chat de Gemini institucional
    """)


# ── Función principal ───────────────────────────────────────────────────────
def main():
    """Punto de entrada principal de la aplicación."""
    render_sidebar()
    render_header()

    # Tabs principales
    tab_auto, tab_manual, tab_sap = st.tabs([
        "🤖 Revisión Automatizada",
        "📝 Revisión Manual Asistida",
        "📥 Descargador Genérico SAP",
    ])

    with tab_auto:
        if not st.session_state["mga_datos"]:
            render_bloqueo()
        else:
            render_project_card()
            render_flujo_automatizado()

    with tab_manual:
        if not st.session_state["mga_datos"]:
            render_bloqueo()
        else:
            render_project_card()
            render_flujo_manual()

    with tab_sap:
        render_descargador_sap()

    # Panel de resultados consolidados (solo si hay MGA y resultados)
    if st.session_state["mga_datos"] and st.session_state["resultados_auto"]:
        render_panel_resultados()


if __name__ == "__main__":
    main()
