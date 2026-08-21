# Auditoría Funnel FVG/OB + Relación — EURUSD 20 años

**Fecha:** 2026-08-18  
**Autor:** Hermes  
**Commit base de código:** `95b48b4` (FVG↔OB relation integration)  
**Dataset:** Dukascopy bid 2006-01-01 → 2025-12-31 (20.0 años)  
**IA / PnL:** desactivados

---

## 1. Qué cambió respecto al funnel anterior

| Antes (sin relación) | Ahora (`engine/relations.py`) |
| ---------------------- | ------------------------------- |
| CONFLUENCE = 0 aceptada (`NO_*_RELATION_AUDITED`) | CONFLUENCE con reglas explícitas |
| Solo poblaciones FVG y OB | + `FVG_OB_OVERLAP` + `CausalLink` |
| Sin rate de solape | `relation_rate_vs_fvg` / `vs_ob` medibles |

**Regla canónica:**

```
same_direction + positive_price_overlap + <=20 bars_apart + causal ordering
```

Cadena auditada:

```
FVG → OB → FVG_OB_OVERLAP → CausalLink
```

---

## 2. Data

| TF | Barras | Rango |
|----|-------:|-------|
| H1 | 124.377 | 2006-01-01 → 2025-12-31 |
| H4 | 32.133 | 2006-01-01 → 2025-12-31 |
| D1 | 6.258 | 2006-01-01 → 2025-12-31 |

Fuente: `dukascopy-node` (bid). A0 previo PASS tras limpieza de 17 barras OHLC inválidas.

---

## 3. Resultados del funnel con relación

| TF | FVG | OB | **Relations** | bull/bear rel | rate vs FVG | rate vs OB | CausalLinks | Audit |
| ---- | ----: | ---: | --------------: | --------------: | ------------: | -----------: | ------------: | ------- |
| **H1** | 22.477 | 2.799 | **2.318** | 1.121 / 1.197 | **10.3 %** | **82.8 %** | 2.318 | PASS |
| **H4** | 6.497 | 862 | **716** | 338 / 378 | **11.0 %** | **83.1 %** | 716 | PASS |
| **D1** | 1.543 | 214 | **178** | 64 / 114 | **11.5 %** | **83.2 %** | 178 | PASS |

### Lectura

1. **~10–12 % de los FVG** encuentran al menos un OB solapado (misma dirección, ≤20 barras, solape de precio).
2. **~83 % de los OB** participan en alguna relación — el OB es el eslabón más “cubierto”; muchos FVG quedan sin pareja.
3. Balance direccional de relaciones ~50/50 en H1/H4; en D1 hay más bear (114 vs 64).
4. `causal_links == relation_count` en los tres TF → los links generados pasan `validate_links` (point-in-time).
5. **PASS de auditoría de funnel** en H1/H4/D1.

---

## 4. Delta vs corrida sin relación (mismo 20Y)

| Métrica | Sin relación | Con relación |
| --------- | -------------- | -------------- |
| FVG / OB counts | ≈ iguales | ≈ iguales |
| CONFLUENCE accepted | **0** | **2.318 / 716 / 178** |
| CausalLink | 0 | = relation_count |
| Valor nuevo | solo población | **grafo FVG↔OB auditable** |

Sí había razón para re-correr: el motor **sí cambió** (nuevo `relate_fvg_ob`).

---

## 5. Limitaciones

- No es señal de trading ni setup completo (falta entry/SL/TP / Fase E).
- `max_bars_apart=20` fijo; no calibrado por TF.
- Un FVG puede relacionarse con varios OB (y viceversa); no hay dedupe 1:1 en esta pasada.
- Data Dukascopy bid ≠ feed MT5 del Director.
- Backtest sigue bloqueado por política del índice hasta cierre CI + snapshot.

---

## 6. Artefactos

```
AUDITORIA_FVG_OB_RELATION_20Y.md
reports/audits/experiments/fvg_ob/fvg_ob_funnel.json          # sobrescrito con relación 20Y
data/metadata/EURUSD_20Y.json
```

---

## 7. Gate

| Criterio | Resultado |
| ---------- | ----------- |
| Código relación presente (`95b48b4`) | OK |
| Funnel 20Y con CONFLUENCE > 0 | **PASS** |
| CausalLink validado | **PASS** |
| Setup / PnL | no ejecutado |

**Veredicto:** `PASS` — la conexión FVG→OB→overlap→CausalLink es ejecutable y medible en 20 años de EURUSD.
