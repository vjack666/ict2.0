# Decisión de alcance de fuente histórica — 2026-08-29

## Decisión

Dukascopy queda cerrado como fuente histórica auxiliar y no se buscará ni se
enviará una solicitud de autorización adicional para el snapshot existente.

## Límites

- El snapshot Dukascopy se conserva únicamente como fixture histórico de
  investigación porque MT5 no cubre toda la ventana necesaria.
- MT5 es la fuente operativa objetivo para el uso real.
- El snapshot Dukascopy no es fuente de producción ni se redistribuyen sus datos
  crudos.
- A7 certifica la integridad causal, determinismo, lineage, MTF y reproducibilidad
  del Funnel a partir de bytes declarados; no certifica la licencia del proveedor.
- `license_and_permitted_use=UNKNOWN` y la evidencia de adquisición incompleta
  permanecen visibles como limitación de fuente, fuera del gate técnico A7.

## Consecuencia operativa

No crear tareas, prompts ni follow-ups para obtener permiso de Dukascopy. Si en el
futuro se requiere una nueva descarga, uso de producción o certificación legal de
la fuente, deberá abrirse una decisión explícita del cliente y reabrirse este
alcance.

## Siguiente acción

Cerrar la verificación técnica A7 con los clean runs actuales y pasar al siguiente
tema del plan sin reabrir Dukascopy.

## Cierre técnico verificado

La matriz independiente `reports/audits/experiments/fvg_ob/a7_completion_audit.json`
confirmó `overall_status=PASS` y `375 passed`:

- `mtf_seq_funnel_a7_20260829_192637.json` — commit `25d0e32`, `CLEAN`;
- `mtf_seq_funnel_a7_20260829_200059.json` — commit `25d0e32`, `CLEAN`;
- ambos: `aggregated_status=PASS`, `aggregated_findings=0`,
  `prefix_sequence_invariant=true`, `certification_status=PASS`;
- checksum lógico idéntico:
  `321ce484e7b9a9458a00b324bd4377d5d50648872a1761de38e5913276c49a13`;
- OE-A7.1–OE-A7.12: `PASS`.

La metadata conserva `license_and_permitted_use=UNKNOWN` y
`source_provenance_complete=false`; esos campos describen la fuente y no
invalidan la certificación técnica A7 bajo el alcance decidido.
