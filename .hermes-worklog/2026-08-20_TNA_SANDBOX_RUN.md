# Bitácora — TNA Sandbox runner + validación rollback

**Fecha:** 2026-08-20  
**Responsable:** Grok  
**Commit asociado:** (este commit)

## Objetivo
Adaptar TNA para correr en entorno sandbox (CPU/tiempo limitado) y validar el fix de `rollback_depth`.

## Qué se creó
- `scripts/tna_sandbox_runner.py` — runner multi-ventana mínima (STEP=4, 3 ventanas, ~55-60 steps c/u)
- Reportes:
  - `reports/audits/temporal/ahf_temporal_navigation_SANDBOX.json`
  - `reports/audits/temporal/ahf_temporal_navigation_SANDBOX.md`

## Resultados de la corrida

| Métrica | Valor |
|---------|------:|
| Ventanas | 3/3 PASS_TRACE_INTEGRITY |
| Barras auditadas | 170 |
| Invalidaciones | 51 |
| Rollback depth max | **2.0** |
| Rollback fix validado | **SÍ** |
| Overall sandbox | **PASS** |

### Detalle por ventana
- 2017-smoke: inv=18, rb_max=1.0
- 2020-covid: inv=18, rb_max=2.0  
- 2024-recent: inv=15, rb_max=1.0

## Interpretación
1. El fix de instrumentación funciona: ya no es siempre 0.
2. Hay rollbacks de 1 y 2 capas → la máquina sí retrocede entre temporalidades.
3. Trace integrity se mantiene en regímenes distintos (2017, 2020, 2024).
4. Esto **no** cierra TNA full-span 20Y; cierra el riesgo de “métrica rota”.

## Plan de trabajo restante
1. En máquina local/cloud con ≥16GB: `python scripts/tna_audit_runner.py` (full-span, precompute=True).
2. Comparar distribución de rollback_depth full-span vs sandbox.
3. Si BEHAVIORAL falla en full-span → laboratorio de diseño de estados (no de medición).

## Gobernanza
- Cobertura etiquetada explícitamente como STRATIFIED_MULTI_WINDOW_MINI.
- No se usa PnL ni se declara edge.
