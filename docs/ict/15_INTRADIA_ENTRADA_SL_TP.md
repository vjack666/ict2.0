# ICT — Intradía: Entrada, SL y TP en la temporalidad correcta

| Campo | Valor |
|-------|-------|
| **ID** | `15_INTRADIA_ENTRADA_SL_TP.md` |
| **Versión** | 1.0 |
| **Fecha** | 2026-07-13 |
| **Autor** | SMC-SYSTEMS (Ruben + agente) |
| **Estado** | Propuesta de aplicación al motor (v30) |
| **Fuente verdad** | Código repo + innercircletrader.net (Turtle Soup / MSS) |
| **Relaciona** | `06_TURTLE_SOUP.md`, `14_STOP_LOSS_ESTRUCTURAL.md`, `16_TEMPORALIDAD_EJECUCION.md` |

---

## §0 Contrato operativo (CITABLE)

1. Intradía = HTF **H4** para sesgo + **M15** como TF de ejecución (entry, SL, TP). No bajar a M1/M5 salvo para confirmar el FVG (ver `16_TEMPORALIDAD_EJECUCION.md`).
2. **Entrada**: en el RETORNO a la zona (FVG/OB del displacement) tras el sweep confirmado que falla (cierra adentro). NUNCA en el close de la vela del BOS.
3. **SL**: mecha del sweep ± buffer (0.3 ATR). NUNCA ATR fijo. (Base ya implementada en `calc_structural_sl`, v29.)
4. **TP**: primera liquidez opuesta del LTF M15 MÁS CERCANA al entry (nivel, no cluster). Si no hay, fallback a la zona, pero el nivel cercano es prioridad.
5. **Max hold**: suficiente para que el TP cercano madure (≥ 40 velas M15, no 16). El hold corto mata trades rentables (ver evidencia v29).
6. **RR mínimo 1:3** (modelo 2022 / Silver Bullet, ver libro 18). No forzar 1:2. El TP en liquidez cercana debe sostener al menos 1:3 sin inflar el hold.

---

## 1. Por qué el motor actual falla en intradía (causa raíz)

`ict_backtest/engine.py` `build_signals_from_frames` (líneas 80-107):

```
for i in range(len(ltf_df)):
    row = ltf_df.iloc[i]              # itera M15 barra por barra
    ...
    entry = float(row["close"])       # ENTRA en el close de la vela M15 del BOS
```

El motor decide la entrada en la vela M15 del BOS/CHOCH. ICT dice: la entrada intradía va en el **retorno a la zona** (la vela de displacement deja un FVG/OB; entrás en el retrace a ese nivel). Entrar en el close del BOS = entrar tarde, después del impulso. Eso es el mismo bug de temporalidad que tenían el SL y el TP: el ciclo completo (entry+SL+TP) se resuelve en M15 grueso en vez de en la zona fina.

Evidencia medida (R4 v29, SL estructural ya aplicado):
- EURUSD: 7/11 salidas por `hold_limit` → el TP no se alcanzaba en 16 velas.
- GBPUSD: 11/13 salidas por `hold_limit`.
El SL ya no saca por ruido (PF>1), pero el TP lejano + hold corto duerme el trade.

---

## 2. Entrada intradía (el modelo ICT)

Secuencia (fuente: innercircletrader.net Turtle Soup + MSS):
1. HTF H4 confirma sesgo / rango.
2. M15 barre liquidez (sweep) y falla (cierra adentro del nivel).
3. M15 rompe estructura (BOS/CHOCH) en dirección opuesta al sweep.
4. La vela de ruptura deja un **FVG o OB** (la zona de displacement).
5. **Entrada**: retrace del precio a esa zona (FVG/OB M15), no el close del BOS.
6. SL: mecha del sweep ± buffer (ya en `calc_structural_sl`).
7. TP: primera liquidez opuesta M15 más cercana.

El motor hoy hace (2)+(3) pero no (4)+(5): entra en el close de (3). Hay que esperar el retrace a la zona.

---

## 3. SL intradía (base ya implementada)

`calc_structural_sl` (engine.py, v29):
- SL = `sweep_low` − buffer (long) / `sweep_high` + buffer (short).
- Fallback a `swing_low`/`swing_high` si no hay sweep.
- Si no hay nada → None → no opera (no degrada a ATR).
- `STRUCT_SL_BUFFER_ATR = 0.3`, `STRUCT_SL_MAX_ATR = 6.0` (filtro de tamaño).

Esto es correcto para intradía. No tocar.

---

## 4. TP intradía (lo que hay que corregir en v30)

`_tp_liquidity` (engine.py 283-299) hoy:
```
bsl = float(row.get("bsl_price"))   # cluster de liquidez del LTF (promedio de swings)
if pd.notna(bsl) and bsl > close: return bsl
```
`bsl_price` viene de `detect_liquidity` (liquidity.py): agrupa swings en banda ATR/4 y asigna el precio PROMEDIO del cluster. Si el rango M15 es amplio, el cluster queda lejos → TP lejano → hold_limit.

Corrección v30: TP = el **swing de liquidez opuesto MÁS CERCANO** al entry (primer BSL/SSL que el precio toca yendo a favor), no el cluster. El repo ya tiene `bsl_price`/`ssl_price` por vela; la lógica debe tomar el nivel cercano, no la zona.

---

## 5. Max hold intradía

R4 v29 usó `max_hold=16` velas M15. Con TP cercano (v30) eso puede alcanzar, pero para dar aire: `max_hold >= 40` velas M15. El hold corto es el que dormía los trades rentables.

---

## 6. Auditoría

- Look-ahead: `sweep_low`/`sweep_high` usan `.shift(1)` en `data_feed._sweep_level` → nivel del sweep ya cerrado. Sin look-ahead.
- La zona de entry (FVG/OB M15) debe leerse de la vela YA CERRADA (`.shift(1)`), no de la vela en formación.
- `require_displacement=True` ya exige la vela de displacement (v29 lo usó). Mantener.

---

## 7. Checklist de aplicación (v30)

- [ ] `build_signals_from_frames`: entry en retorno a zona FVG/OB M15 (no close del BOS).
- [ ] `_tp_liquidity`: nivel de liquidez cercano, no cluster.
- [ ] `run_backtest.py` / script v30: `max_hold >= 40`.
- [ ] Re-correr R4 v30 (EURUSD + GBPUSD, H4→M15, CT, SL estructural, TP cercano).
- [ ] Medir: % hold_limit debe bajar, PF debe sostenerse > 1.

---

> **Nota de veracidad**: los números de v29 son medidos (log `docs/ict/logs/R4V29_STRUCTSL.log`). El veredicto de v30 se mide en el re-run, no se afirma antes.
