# Misión científica de desbloqueo — Fase 2B EURUSD

- **Mission ID:** `MC-20260911-153509-dfab2f`
- **Estado:** `PLAN`
- **Modo:** `LOCAL_ONLY / AUDIT_FIRST`
- **Dueño inicial:** D4 Data Lineage — Data Engineer
- **Revisiones obligatorias:** D5 CRO/Auditor independiente y Compliance
- **Contribuyentes condicionados:** D6 Research, D3 IA y D2 Ingeniería
- **Autoridad final:** cliente; una misión no autoriza producción.

## Objetivo

Desbloquear de manera reproducible los gates de Fase 2B definidos en
`SDD_MECHANICAL_SIGNAL_PRODUCER_V1`,
`EXP_PASS_EDGE_INTRADIA_01_PREREGISTRATION` y
`CONTRATO_PASS_EDGE_INTRADIA_V1`. El cierre científico puede resultar
`PASS_EDGE`, `NO_EDGE`, `REVIEW` o `BLOCKED`; solo el primero habilita evaluar
el gate de publicación, y ninguno habilita por sí mismo una orden.

## Fronteras no negociables

- No modificar `can_trade=false` ni `entry_authorized=false`.
- No publicar ni escribir `runtime/mechanical_bot/latest_snapshot.json`.
- No conectar el gate de Fase 2B al bot, MT5 ni un broker.
- No usar `label_end_*`, accuracy o log-loss como sustitutos de `net_R`.
- No descargar, reparar, borrar o mutar datos sin un subpaso autorizado y
  contrato aplicable. Las nueve anomalías se conservan y se reportan en ambas
  sensibilidades; no se corrigen silenciosamente.
- No reutilizar el HOLDOUT para elegir reglas, costes, horizonte o umbral.

## Ruta con dependencias

| ID | Trabajo | Dueño | Predecesor | Evidencia que habilita el siguiente paso |
| --- | --- | --- | --- | --- |
| U0 | Congelar baseline, commits, configuración y superficies excluidas | D1 + D5 | — | acta de freeze, hashes y exposición previa del HOLDOUT |
| U1 | Inventario D4 de fuente EURUSD: proveedor, licencia, adquisición UTC, schema, timezone, OHLC, anomalías y hashes | D4 | U0 | manifiesto de procedencia o `BLOCKED` exacto |
| U2 | Resolver unidad económica: `setup_id`, `episode_id`, entry, stop, R, fill, costes, salida y horizonte | D6 + D5 | U1 PASS | enmienda preregistrada aprobable; sin mirar outcomes |
| U3 | Construir replay causal y FULL/PREFIX independientes para la unidad congelada | D2 + D5 | U2 | evidencia PIT, igualdad FULL/PREFIX y lineage por setup |
| U4 | Ejecutar evaluación económica preregistrada de `net_R`, bootstrap por cluster, MDE y estabilidad | D6 + D5 | U1-U3 PASS y GO D5 | artefactos `setups`, `trades`, `audit`, `report`, manifiestos |
| U5 | Materializar modelo de probabilidad separado: TRAIN/VALIDATION/HOLDOUT, Brier, fiabilidad y OOD/abstención | D3 + D5 | U1-U3 PASS; contrato IA específico | artefacto calibrado y auditoría OOS; no sustituye U4 |
| U6 | Dictamen independiente de datos, causalidad, calibración, edge y autorización | D5 | U4-U5 | matriz de gates `PASS/REVIEW/BLOCKED` firmada |
| U7 | Evaluar el gate técnico de publicación | D2 + D5 | U6: todos `PASS` | contrato atómico candidato, aún sujeto a veto final del bot |

## Definiciones congeladas para revisar, no alterar post-resultado

- Dirección técnica: la regla existente `CANDIDATE_CONTEXT_DIRECTION_V1` solo
  puede traducir un `CANDIDATE_SETUP` causal BULLISH/BEARISH después de U6.
- `confirmed=true`: `PHASE2A_CHAIN_COMPLETE_CLOSED_M15_V1`; no incluye el
  estocástico, que es un control final del bot.
- Probabilidad: debe calibrarse exclusivamente con VALIDATION y evaluarse en
  HOLDOUT no usado para fit; Brier y curva de fiabilidad son obligatorios.
- Edge: media `net_R` frente a `R0=0`, IC bootstrap por `episode_id/chain_id`,
  MDE `+0,10R`, potencia `0,80` y estabilidad preregistrada.

## Stop conditions

La misión se detiene en el gate que falle. Falta de identidad de fuente,
licencia/permitted-use, adquisición, manifest/hash, worktree reproducible,
costes/fill/horizonte o causalidad implica `BLOCKED`; no se compensa con una
métrica IA, un proxy ni una señal demo. U4 y U5 no comienzan sin el GO
independiente indicado por el preregistro.

## Criterio de cierre

El cierre requiere artefactos mínimos del contrato (`manifest.json`,
`setups.jsonl`, `trades.jsonl`, `audit.json`, `report.md`), reproducción limpia
dos veces, dictamen D5 y matriz completa de gates. El resultado se registra en
la misión persistente; producción permanece separada y exige autorización del
cliente.
