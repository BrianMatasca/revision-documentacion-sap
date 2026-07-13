# Contexto y problema

Trabajo en el Departamento Administrativo de Planeación (DAP) de la Gobernación del Valle del Cauca, en la Subdirección de Inversión Pública. Necesito una aplicación que ayude a los revisores a validar los documentos que las secretarías radican en SAP para tramitar proyectos de inversión pública (radicación inicial, adición, reducción, vigencia futura, etc.).

Cada proyecto se compone de varios documentos: Carta de Presentación, Verificación de Requisitos, Viabilidad del Proyecto, Documento Técnico, Presupuesto Detallado, y el archivo XML exportado de la plataforma MGA (Metodología General Ajustada) del DNP, que contiene los datos estructurados del proyecto (nombre, código PI, BPIN, valores, etc.).

El problema que resuelve esta app: los revisores actualmente detectan errores de forma manual y tardía (nombres que no coinciden entre documentos, sumas de presupuesto que no cuadran, formatos desactualizados, firmas faltantes). Quiero automatizar la mayor parte posible de esta revisión.

# Recursos actuales

- Ya existe una app en Streamlit para este propósito (adjunto `app.py` como referencia de contexto, **no la continúes ni la tomes como base obligatoria** — analízala solo para entender el enfoque previo y decide tú la mejor arquitectura desde cero o reutilizando lo que consideres útil).
- Uso el SDK `google-genai` de Python para llamar a la API de Gemini.
- Los documentos en SAP son accesibles vía un link HTTP con autenticación Basic Auth (usuario/contraseña institucional de SAP). **Esta debe ser la opción por defecto para subir los documentos** — el usuario pega el link de SAP y el sistema los descarga usando sus credenciales, en vez de subir el PDF manualmente desde su equipo (aunque subir el PDF manualmente puede quedar como alternativa secundaria).

# Restricción clave: no tengo API key institucional con facturación

Tengo licencia institucional de Gemini, pero solo se puede usar desde el chat web (gemini.google.com) — no permite generar una API key porque requiere facturación habilitada, y eso no está disponible por ahora. Para lo que sí se puede automatizar vía API, uso mi propia API key personal de la capa gratuita, que tiene cuota muy limitada.

Esto genera dos flujos distintos en la misma app:

**Flujo automatizado (con API key personal, cuota limitada):**
Los documentos Carta de Presentación, Verificación de Requisitos y Viabilidad del Proyecto se procesan con OCR (Tesseract) para extraer el texto, y luego se revisan mediante una llamada a la API de Gemini por documento (lo más probable, dada la naturaleza de la validación, es que sea una llamada por documento — pero no asumas esto por mí: decide tú, según el problema, si algo puede resolverse sin IA o si conviene combinar OCR con la llamada al modelo).

**Flujo manual asistido (usando la licencia institucional vía chat, sin gastar cuota de API):**
El Presupuesto y el Documento Técnico no se envían a la API. En su lugar, cuando el usuario sube el XML de la MGA, la app debe extraer los valores clave del proyecto (BPIN, código PI, nombre del proyecto, valor total, etc.) y con eso **generar un prompt de texto en la propia página de Streamlit**, que el usuario pueda copiar y pegar manualmente en el chat de Gemini (usando su licencia institucional), junto con el PDF del Presupuesto o del Documento Técnico. Este prompt generado debe construirse usando como contexto el `formato.md` y el `prompt.md` de la carpeta correspondiente (ver estructura de carpetas más abajo), para que ya venga completo con lo que se debe revisar en ese formato específico.

# Regla obligatoria de flujo: el XML de la MGA es requisito previo

**El usuario no puede subir ningún otro documento (Carta, Verificación, Viabilidad, Presupuesto, Documento Técnico) hasta que primero suba el archivo XML de la MGA.** Este XML es la fuente de los datos base del proyecto (nombre, código PI, BPIN, valores) que luego se usan para las validaciones cruzadas entre documentos y para construir los prompts del flujo manual asistido. La interfaz debe bloquear o deshabilitar la carga de los demás documentos mientras el XML no esté cargado.

# Estructura de carpetas de referencia (ya la voy a crear yo)

En la raíz del proyecto voy a colocar una carpeta `formatos/` con esta estructura:

```
formatos/
├── presentacion/
│   ├── formato.md    ← especificación de lo que debe contener el formato base
│   └── prompt.md      ← aspectos generales que se deben revisar en ese documento
├── verificacion/
│   ├── formato.md
│   └── prompt.md
├── viabilidad/
│   ├── formato.md
│   └── prompt.md
├── presupuesto/
│   ├── formato.md
│   └── prompt.md
├── documento_tecnico/
│   ├── formato.md
│   └── prompt.md
└── documento_tecnico_ajuste/
    ├── formato.md
    └── prompt.md
```

Usa esta estructura como contexto de referencia al construir la app: cada subcarpeta corresponde a un tipo de documento, y su `formato.md` + `prompt.md` deben alimentar tanto las llamadas a la API (flujo automatizado) como la construcción del prompt para copiar/pegar (flujo manual asistido).

Ten en cuenta que existen **dos variantes de Documento Técnico**: `documento_tecnico` corresponde a la formulación inicial del proyecto, y `documento_tecnico_ajuste` corresponde al soporte de ajustes/modificaciones (adición, reducción, vigencia futura, etc.) sobre un proyecto ya radicado. Son formatos distintos, con código y estructura propios — no deben tratarse como el mismo documento. `documento_tecnico_ajuste` sigue el mismo flujo manual asistido que `documento_tecnico` y `presupuesto`: no se envía a la API, sino que se usa para generar el prompt de copiar/pegar para el chat de Gemini con la licencia institucional.

# Modelos disponibles en la capa gratuita de Gemini y guía de decisión

Dada la restricción de cuota, decide tú qué modelo usar para cada tipo de llamada, pero ten en cuenta que **lo más conveniente por límites es `models/gemini-3.1-flash-lite`**, salvo que consideres que otro modelo se ajusta mejor a una tarea específica (por ejemplo, si alguna validación necesita más capacidad de razonamiento y el volumen de esa llamada es bajo).

| Modelo | RPM | TPM | RPD |
|---|---|---|---|
| Gemini 3.5 Flash | 5 | 250k | 20 |
| Gemini 3 Flash | 5 | 250k | 20 |
| Gemini 3.1 Flash Lite | 15 | 250k | 500 |
| Gemini 2.5 Flash | 5 | 250k | 20 |
| Gemini 2.5 Flash Lite | 10 | 250k | 20 |

Optimiza las llamadas a la API pensando en estos límites: minimiza el número de requests por documento, evita reenviar contenido innecesario (por ejemplo, si el OCR ya extrajo el texto de forma confiable, no reenvíes también la imagen completa del PDF salvo que sea necesario), y evita llamadas redundantes entre documentos del mismo proyecto.

# Manejo de múltiples API keys

La app debe tener un campo de entrada en la interfaz donde el usuario pueda ingresar su Gemini API key personal, con la posibilidad de cambiarla en cualquier momento (por si la cuota de la key actual se agota, el usuario pueda pegar otra sin reiniciar la sesión ni perder el progreso de la revisión). Cuando una llamada a la API falle porque se alcanzó el límite de cuota, la app debe mostrar un mensaje claro indicando que se alcanzó el límite de la API key actual y que se debe ingresar una nueva.

# Resultado final de la revisión

La respuesta final de la revisión debe presentarse organizada claramente por cada formato/documento (no como un bloque único de texto), con una UX cuidada: estado de la validación por documento, hallazgos específicos, y una experiencia visual clara y fácil de escanear para el revisor. Ten en cuenta que quien usa esta app revisa muchos proyectos al día, así que la app debe permitir entender rápido qué documentos tienen errores y cuáles están correctos.

# Lo que te pido concretamente

Diseña y construye esta aplicación Streamlit desde el análisis del problema descrito arriba. Tienes libertad para decidir:
- Qué se resuelve con reglas/código (programático) y qué necesita una llamada a la IA — no te voy a indicar esa división, quiero que la identifiques tú según lo que cada documento realmente requiere validar.
- Cuántas llamadas a la API hacer por documento y cómo estructurar los prompts para que sean eficientes en tokens y en número de requests, dado el límite de cuota.
- La arquitectura de código, siempre que cumpla con los requisitos funcionales descritos (SAP como fuente por defecto, XML de MGA obligatorio antes de continuar, flujo manual asistido para Presupuesto y Documento Técnico, input de API key con manejo de límite alcanzado, y resultado final organizado por documento con buena UX).
- Olvida las firmas, es algo complejo y aun mas con una IA limitada. Las firmas se verificarian con una revision visual/Manual