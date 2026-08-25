# Resultado — Auditoría temporal AHF / MTF

**Fecha:** 2026-08-19  
**Plan:** `audits/PLAN_AUDITORIA_TEMPORAL_AHF.md`  
**Motor de métricas:** `audits/codigo/ahf_temporal_navigation_audit.py`  
**Artefacto JSON:** `reports/audits/temporal/AUDITORIA_TEMPORAL_AHF_RESULT.json`
**Policy:** `TEMPORAL_AUDIT_NOT_PNL` / `AHF_STATE_NOT_ENTRY`

---

## Dataset / ventana

| Campo | Valor |
| ------- | -------- |
| Símbolo | EURUSD |
| Fuente | `data/raw/EURUSD` (Dukascopy 20Y) |
| Ventana H1 | 2017-03-14 → 2017-04-28 (~800 barras) |
| Decision steps | 750 (desde bar 50) |
| Seq precompute | OFF (velocidad; depth proxy en nav) |

---

## Gates de integridad

| Gate | Resultado |
| ------ | ----------- |
| Trace presente | PASS |
| Historial monótono en barras | **PASS** |
| Transiciones reconstruibles | **PASS** |
| Policy ≠ entry | **PASS** |
| **Gate global** | **PASS** (`PASS_TRACE_INTEGRITY`) |

---

## Navegación

| Métrica | Valor |
| --------- | ------: |
| Transiciones únicas | 501 |
| Invalidaciones | 193 |
| Switches down / up | 105 / 104 |
| Visitas TF | D1: 1 · H4: 209 · H1: 291 |
| Estado final (ventana) | `WAIT_H4` |
| Stuck states (p95 dwell) | 12 |

### Duración por estado (barras entre transiciones)

| Estado | n | mediana | p95 | max |
| -------- | --: | --------: | ----: | ----: |
| D1_LOCKED | 1 | 0 | 0 | 0 |
| WAIT_H4 | 105 | 1 | 1 | 1 |
| H4_LOCKED | 104 | 0 | 0 | 0 |
| WAIT_H1 | 193 | 1 | 1 | 1 |
| WAIT_LTF | 92 | 1 | 7.8 | 34 |
| SETUP_READY | 6 | 41.5 | 63.8 | 69 |

### Rollback

| Métrica | n | mediana | max |
|---------|--:|--------:|----:|
| Profundidad de capas | 193 | 0 | 0 |
| Barras hasta siguiente transición | 192 | 1 | 1 |

Lectura: hay muchas invalidaciones registradas, pero el medidor de “profundidad de capa” quedó en 0 por cómo se etiqueta `parent_state` vs TF en el trace actual — **métrica de profundidad a refinar**; la existencia de invalidaciones y el orden temporal sí son válidos.

---

## Magnitud FVG/OB (descriptiva, no TP/SL)

| Grupo | n | size_pips mediana |
| ------- | --: | ------------------: |
| H1 FVG bearish | 76 | ~3.5 |
| H1 FVG bullish | 73 | ~3.7 |
| H1 OB bullish | 5 | ~13.4 |
| H1 OB bearish | 8 | ~10.5 |

Excursiones +1…+48 en el JSON (`object_magnitude.aggregated`). **No** son expectancy ni R.

---

## Interpretación

1. El AHF **produce traces auditables** con orden temporal reconstruible.
2. Navega y **retrocede** con frecuencia (193 invalidaciones en ~750 pasos) — coherente con una máquina sensible a cambios de bias/BOS, no con un loop fijo.
3. `SETUP_READY` aparece poco y con dwell alto cuando se alcanza (mediana ~41 barras).
4. Esta auditoría **no** valida edge; valida **integridad temporal de navegación**.

---

## Siguiente

- Alinear `parent_state` / `active_tf` en invalidaciones para medir bien rollback depth.
- Repetir con `precompute_sequences=True` en ventana acotada.
- EXP secuencia × contexto (fuera del alcance de esta auditoría).
