# T7 real — MTF Replay Orchestrator v1, enero 2025

## AGENTE / DEPARTAMENTO / TAREA

- **AGENTE:** Codex, director D2; controles D4/D5; cierre D1/D7.
- **TAREA:** ejecutar T7 real preregistrado y auditar causalidad, recursos,
  completitud y procedencia.
- **MODO:** `LOCAL_ONLY`; sin edge, IA, MT5, órdenes, promoción ni push.

## STATUS

`COMPLETED — PASS_TECHNICAL_BLOCKED_PROVENANCE`

El software pasó la aceptación mensual. La procedencia formal conserva
`BLOCKED_PROVENANCE`: `license_permitted_use=UNKNOWN` y
`acquired_at_utc=null`. No se confunde integridad mecánica con autorización.

## Datos congelados

- Perfil `INTRADAY_H4_M15`; enero 2025, con diciembre 2024 como warmup.
- EURUSD spot bid M15 histórico de Dukascopy, solo investigación.
- Diciembre: 1,587 filas, SHA-256 `bce88337...c80c6e`.
- Enero: 2,112 filas, SHA-256 `c62b9355...e0cf6`.
- Dataset: `145229219abea0abca63734b28ed65e17afbb809661ef966afa2b79c31e1a25c`.
- Integridad mecánica PASS; 16 huecos de mercado preservados; sin reparación.
- MT5 y sus parquets no se usaron ni modificaron.

## Resultado

- Commit productor: `4b10815b6ced219eafadf8d29be787ef180b8cb0`.
- 3,699 M15 con warmup; 246 H4 closed-only; 2,117 batches de enero.
- Detectados: H4 59, M15 881; cargados: 59 objetos de autoridad H4.
- Determinismo PASS: checksum en ambos runs
  `9bebed22426f5cd43cdda46049ae529df41e3453550adc7d2a9d825067e62674`.
- FULL/PREFIX 25/50/75/90 % PASS.
- Chunks 500/257 invariantes: 8/15 chunks, PASS.
- Primera pasada: 71.97 s; pico working set: 159.43 MB.

## Completitud honesta

`NO_COMPLETE_SETUP_POPULATION_H4_AUTHORITY_REPLAY`.

T7 probó reloj real, H4 closed-only, autoridad H4, observación M15, lifecycle,
checkpoints, determinismo, causalidad y visor. No produjo setups, Episodes ni
trades: el ensamblador histórico público crea FVG/OB, pero todavía no
materializa BOS/displacement como `MarketObject`. No se inventó esa población.
Los caminos completos siguen cubiertos por M6 sintético. Por tanto, T7 certifica
el replay mensual real, no un Setup Builder histórico end-to-end ni edge.

## Causas raíz corregidas

1. `tracemalloc` distorsionaba repeticiones: reemplazado por working set Windows.
2. Hashes calculados pero no confrontados: ahora fallan cerrado contra preregistro.
3. Lifecycle guardaba barras irrelevantes en `_seen_events`: dedupe acotado a
   eventos geométricamente relevantes.
4. Objetos terminales se reevaluaban: el replay ahora los omite.
5. Proyecciones históricas imposibles/duplicadas: guardas causales sin cambiar
   candidatos ni la semántica BLOCKED de SetupBuilder.

## Evidencia y siguiente acción

- Preregistro: `docs/experimentos/EXP_MTF_REPLAY_T7_2025_01_PREREGISTRATION.md`.
- Reporte: `reports/audits/mtf_replay/t7_2025_01/t7_audit.json`.
- Artefacto/visor: `reports/audits/mtf_replay/t7_2025_01/`.
- Antes de ampliar meses o abrir edge: contrato y productor histórico canónico
  de BOS/displacement con lineage y FULL/PREFIX; luego T7b end-to-end.
- No push.
