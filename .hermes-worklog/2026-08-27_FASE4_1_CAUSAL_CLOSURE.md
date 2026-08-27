# FASE 4.1 — Cierre causal real del visor

- **Agente:** Codex
- **Departamento:** D5 Assurance / D7 Delivery
- **Fecha:** 2026-08-27
- **Base de código:** `codex/visual-replay-wyckoff-v1-1-20260826` @ `d9d2df3`

## Objetivo

El visor debe explicar el estado causal en cada instante `T`: entidades vivas,
origen multi-TF, rol, lifecycle, delta respecto de `T-1`, estado AHF canónico,
linaje temporal y ausencia de futuro. No es un motor de trading ni una prueba de
edge.

## Correcciones ejecutadas

1. `setup_builder` traduce `AHFSnapshot` y conserva la invalidación de
   `AHFSnapshot.history`; si falta el snapshot, falla cerrado.
2. `replay.py` falla cerrado si el AHF canónico no puede producir el timeline.
3. La proyección de `MarketState` normaliza los UUID runtime de objetos
   secuenciales a identidades deterministas, preservando el linaje padre/hijos.
   El motor canónico no fue modificado.
4. `verify_6tf_acceptance.py` compara realmente dos artifacts FULL/PREFIX y no
   infiere el resultado desde `pit_temporal_consistency`.
5. El visor muestra `ORIGEN`, `VIENDO`, `ROL`, `ESTADO`, cambios de entidades,
   terminales como historia no activa, AHF y `FUTURO UTILIZADO: NO`.

## Evidencia

- Suite Python relevante: **36 passed, 1 skipped**, una advertencia de pandas.
- Suite del visor: **5 passed**; `npm run build`: **PASS**.
- FULL: `backtest/runs/eaade0989790b9390b8e872e/visual_backtest.json`.
- PREFIX: `backtest/runs/c510fbcb5badf5111ea69437/visual_backtest.json`.
- Seis capas presentes: `D1/H4/H1/M15/M5/M1`.
- `FULL_PREFIX_SNAPSHOTS=96`; snapshots `market_state` y `setups` idénticos en
  toda la intersección; **8/8 PASS**.
- El visor local sirve el FULL corregido post-commit en
  `http://127.0.0.1:4173/`.

## Limitaciones honestas

- La corrida es diagnóstica y usa `TICK_VOLUME_PROXY`; no declara edge.
- Se ejecutó sin `--wyckoff`, por lo que la capa Wyckoff real requiere una corrida
  separada si se necesita mostrarla junto al replay corregido.
- `generator_worktree_clean_before_run=false` por cambios preexistentes en M1/M5
  y el script de verificación; no se tocaron ni se commitean esos Parquet.
- Los JSON de runs permanecen locales e ignorados por su tamaño.

## Estado

```text
M3 AHF/Setup State              PASS
AHF fail-closed                 PASS
FULL/PREFIX real                PASS (96 snapshots)
Six timeframe acceptance        PASS (8/8)
Viewer causal explanation       PASS (build + server HTTP 200)
FASE 4.1                        CORREGIDA LOCALMENTE
Push                            NO AUTORIZADO
```

## Siguiente acción

Auditoría independiente del diff y, solo después de una instrucción explícita
del cliente, publicación selectiva de código. No incluir `data/` ni
`backtest/runs/`.
