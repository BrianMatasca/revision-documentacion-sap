# Qué se revisa – Presupuesto (FO-M1-P1-24)

## Encabezado y metadatos
- Código de formato = FO-M1-P1-24, Versión = 02, Fecha de aprobación = 13/06/2025, idéntico en todas las páginas/pestañas del documento
- Nombre del proyecto idéntico al usado en Carta de Presentación, Verificación de Requisitos, Viabilidad y Documento Técnico
- Entidad/Dependencia coincide con la secretaría formuladora indicada en los documentos previos
- Vigencia coincide con la vigencia fiscal del proyecto
- Código PI idéntico y con prefijo consistente (ej. PI32-, PI30-, PI34-, PI43-) en todas las páginas del mismo documento
- ID MGA o código BPIN presente y con formato estándar (código largo tipo AAAA##########); marcar como inconsistencia si aparece truncado o incompleto
- Tipo de modificación y Valor de la modificación diligenciados de forma coherente entre sí (Radicación Inicial, Actualización sin Afectación Presupuestal, Crédito, Contracrédito, Adición, Reducción, Traslado Interno, o Vigencia Futura).

## Estructura de la tabla principal (página "Presupuesto Detallado")
- Presencia de todas las columnas de la cadena de valor: Objetivos específicos, Producto MGA, Entregable en MGA(aplica solo para proyectos con EDT), Actividad del proyecto, Fuente de financiación
- Presencia de la clasificación central producto CCPT-DANE (código y nombre de cuenta) para cada actividad
- Presencia de las cuatro columnas de presupuesto: Unidad de medida, Cantidad, Valor de la actividad apropiados(DEPTO O PROPIOS DE DESCENTRALIZADA), Valor de la actividad (APLICA PARA RECURSOS NACION)
- Presencia de recursos por gestionar / asignar
- Valor total del proyecto por fila = apropiados + recursos nación + recursos por gestionar
- Subtotal Proyecto = suma correcta de todas las filas

## Estructura de la página "Histórico de Modificaciones"
- Mismo encabezado (nombre proyecto, entidad, vigencia, código PI, BPIN) que la página de detalle
- Columnas Modificación 1 a 8 con formato de fecha DD-MM cuando estén diligenciadas
- Identificar cuál columna "Modificación N" corresponde al trámite actual (la última columna con datos diligenciados)
- Presupuesto inicial + todas las modificaciones diligenciadas + recursos de gestión = Valor total del proyecto (verificar tanto por fila como en el subtotal — un error de fila puede compensarse en el subtotal y pasar desapercibido)
- El valor absoluto de la suma de la columna "Modificación N" activa (identificada arriba) coincide con el campo "Valor de la modificación" del encabezado — NO comparar el total de la página completa contra este campo, son magnitudes distintas (delta vs. total acumulado)

## Validación de formato institucional
- Confirmar que el documento use el código FO-M1-P1-24 y no un formato paralelo (SGR, presupuestos de obra tipo AIU/CD u otros esquemas ajenos al Banco de Proyectos departamental)
- Rechazar como "Presupuesto" cualquier archivo sin encabezado institucional completo (nombre del proyecto, entidad, código PI, BPIN, código de formato)
- Verificar que estén todas las columnas del formato vigente (especialmente CCPT-DANE y "valor de la actividad apropiados"); marcar si faltan columnas respecto al formato base

## Cruces con otros documentos del expediente
- Nombre del proyecto, código PI y BPIN idénticos a los reportados en Carta de Presentación, Verificación de Requisitos, Viabilidad y Documento Técnico
- Valor total del proyecto consistente con el valor reportado en Viabilidad del Proyecto
- Nombre del formulador y del Secretario/Subsecretario coherentes con la entidad/dependencia reportada
- Nombre de archivo consistente con el código PI/BPIN contenido dentro del documento
- El "Subtotal Proyecto" de la página "Presupuesto Detallado" DEBE coincidir con el "Valor total del proyecto" (columna final) de la página "Histórico de Modificaciones". Si difieren, es un hallazgo crítico: el documento se contradice internamente sobre cuál es el presupuesto vigente del proyecto.
- Valor total de la página "Presupuesto Detallado" coincide con el valor total declarado en la Carta de Presentación para la misma vigencia.
