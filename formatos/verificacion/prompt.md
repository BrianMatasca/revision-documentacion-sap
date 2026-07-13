# 2. Verificación de Requisitos (FO-M1-P1-04)

## Qué se revisa
- **Formato y versión** — que sea `FO-M1-P1-04` versión vigente (04), no una plantilla desactualizada.
- **Ordenador del gasto declarado** — EL(LA) SUSCRITO(A) ORDENADOR DEL GASTO DE (NOMBRE DE LA DEPENDENCIA/ENTIDAD)
- **Nombre del proyecto** — coincide exactamente con el de los demás documentos.
- **Código PI** — presente y coincide con los demás documentos.
- **Código BPIN / ID-MGA** — presente y coincide con los demás documentos.
- **Tipo de trámite declarado** — identificado como uno de: Radicación Inicial, Actualización sin Afectación Presupuestal, Crédito, Contracrédito, Adición, Reducción, Traslado Interno, o Vigencia Futura.
- **Vigencia** — presente y coincide con los demás documentos.

- **Valor de la modificación** — presente y debe validarse así:
  1. Comparar contra el valor de la columna **"Valor de la modificación"** de la tabla de ajuste presupuestal en la Carta de Presentación (FO-M1-P1-11), NO contra los valores de vigencia total ni contra el total plurianual de la MGA. El "valor de la modificación" es un delta/transferencia, no un saldo total — nunca va a coincidir con un monto de programación presupuestal de la MGA, y no debe reportarse como error si no coincide con esos campos.
  2. Si el trámite es CONTRACRÉDITO o TRASLADO INTERNO: verificar que la suma algebraica de la columna "Valor de la modificación" en la tabla de ajuste de la carta (sumando signos +/-) dé **$0**. Si no da $0, ese sí es un hallazgo real (la reasignación no está balanceada).
  3. Si el trámite es ADICIÓN o REDUCCIÓN: el valor de la modificación debe coincidir con el cambio neto en el total del proyecto (después − antes) reportado en esa misma tabla de la carta.
  4. Si no hay tabla de ajuste en la carta (ej. Radicación Inicial), no aplica esta validación — marcar como NA, no como error.

- **Tabla de Requisitos Generales de Viabilización y Aprobación (ítems 1-9)** — cada ítem diligenciado con SI/NO/NA, sin celdas vacías.
- **Coherencia entre ítems condicionados** — ej. el ítem 3 (Documento Técnico Inicial) solo aplica si el trámite es Radicación Inicial; si el trámite es otro, debe estar en NA, no en SI/NO.
- **Tabla de Anexos y Soportes (ítems 10-19)** — cada ítem diligenciado con SI/NO/NA según aplique al tipo de proyecto.
- **Sección de Emergencia/Desastre (ítems 20-21)** — diligenciada solo si el proyecto tiene ese objeto; NA en caso contrario.
- **Ningún ítem marcado "NO"** — un NO en cualquier requisito general es motivo de rechazo o devolución; el sistema debe alertarlo con prioridad.
- **Fecha de firma** — presente y coherente con la fecha de radicación de la Carta de Presentación (no puede ser anterior).
- **Firma** — presente en la zona correspondiente del ordenador del gasto.

## Plantilla base parte inicial
Informa que el proyecto de inversión "(NOMBRE DEL PROYECTO)" identificado con PIXX-XXXXXX y Código BPIN o ID-MGA: XXXXXXXXX cumple con la verificación de requisitos para tramitar el ajuste (RADICACIÓN INICIAL, ACTUALIZACIÓN SIN AFECTACIÓN PRESUPUESTAL[^1], CRÉDITO, CONTRACRÉDITO, ADICIÓN, REDUCCIÓN, TRASLADO INTERNO O VIGENCIA FUTURA) por valor de $XXXXX (valor de la modificación) para la vigencia (AÑO) conforme a los siguientes requerimientos:

> Nota interna para el motor de revisión: "$XXXXX (valor de la modificación)" es un monto de transferencia/ajuste, no el valor total de la vigencia ni del proyecto. Su fuente de verdad para comparación es la tabla de ajuste presupuestal de la Carta de Presentación (FO-M1-P1-11), no los datos de programación de la MGA.