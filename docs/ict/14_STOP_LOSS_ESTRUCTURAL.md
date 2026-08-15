# ICT — Stop Loss Estructural (anclar el SL a la estructura, no al ATR)

| Campo | Valor |
|-------|-------|
| **ID** | `14_STOP_LOSS_ESTRUCTURAL.md` |
| **Versión** | 1.0 |
| **Fecha** | 2026-07-13 |
| **Estándar** | ADR-021 / RFC-001 |
| **Estado** | Draft (docs) · Needs-code (motor `ict_backtest/engine.py`) |
| **Métricas** | ver R4 v28 (`results/r4/r4v28_turtle_...json`) — backtest con SL por ATR |

> **Fuente de verdad:** código del repo (`detectors/`, `ict_backtest/engine.py`, `rules.py`) + auditorías + esta investigación. Fuentes externas (ICT Mentorship / fluxcharts / TradingStrategyGuides) solo como respaldo de la regla de oro.

---

## 0. Contrato operativo (el SL NUNCA es ATR)

| # | Condición medible | Obligatorio |
|---|-------------------|:-----------:|
| 1 | El SL se ubica en el nivel donde la **tesis del trade queda invalidada** (no a X ATR del entry) | Sí |
| 2 | En contratendencia (Turtle Soup): SL **más allá del sweep** (por detrás de la mecha que barrió la liquidez) | Sí |
| 3 | En a-favor: SL bajo el swing roto / borde del OB o FVG que define la estructura | Sí |
| 4 | RR se deriva del SL real (TP en liquidez opuesta o estructura), NO se impone 1:2 fijo | Sí |
| 5 | El motor NO usa `entry ± atr` como fallback de SL | Sí (hoy INCUMPLIDO) |

**Setup completo** = SL anclado a estructura + TP en objetivo estructural.
**Hoy el motor FALLA #1 y #5** (usa fallback `entry ± atr`).

---

## 1. Teoría — cómo calcula el SL un humano ICT/SMC

El stop loss tiene **UNA sola función: invalidar la idea del trade**. No se pone a una distancia "cómoda" ni a un múltiplo de ATR. Se pone en el nivel exacto donde, si el precio lo toca, la lectura estructural que justificó la entrada queda **demostrada como falsa**.

Regla de oro (consenso ICT + SMC, fuentes externas):

- **SMC:** el stop de un long va **bajo el mínimo de la mecha que barrió la SSL** (sellside liquidity) antes de revertir. Si el precio vuelve por debajo de esa mecha, la reacción institucional desde la que operaste **falló**.
- **ICT:** el stop de un long va **bajo el mínimo del Judas Swing** (la manipulación). Si el precio retrocede más allá, el Judas Swing no fue la fase de manipulación — la narrativa se rompe.

En ambos casos el SL está **atado a un evento de estructura concreto**, no a la volatilidad reciente.

### Por qué el ATR como SL es un antipatrón en ICT

El ATR mide ruido reciente. Anclar el stop a él:
1. Lo deja **flotando** entre el entry y la estructura → el ruido inmediato lo saca antes de que la tesis madure.
2. En contratendencia (Turtle Soup) el movimiento ya ocurrió (entrás tras el BOS de giro); el ATR está **atrás** del nivel que define la reversión, así que te sacan en el "spring" / segundo toque típico del fallo del sweep.
3. Ignora dónde está la liquidez tomada, el swing roto y el OB/FVG — precisamente los niveles que el mercado respeta.

---

## 2. Práctica del trader (pasos)

Contexto HTF → trigger LTF → confirmación → **SL estructural** → TP estructural.

1. **HTF (D1/H4):** marcar BSL/SSL (liquidez sobre máximos / bajo mínimos) y la marea.
2. **LTF (M15):** esperar **sweep** de esa liquidez (rompe y **cierra de vuelta adentro** — ver libro `05_LIQUIDEZ.md` §0 #3).
3. **Confirmación:** CHoCH / BOS de giro en dirección opuesta al HTF (Turtle Soup) o a favor (a-favor).
4. **Entrada:** en el retorno a la zona (FVG/OB), **no en la mecha del sweep**.
5. **SL estructural:**
   - *Long tras sweep de SSL:* SL **bajo el mínimo de la vela que barrió la SSL** (la mecha de caza). Un tick más abajo = la reversión falló.
   - *Short tras sweep de BSL:* SL **sobre el máximo de la vela que barrió la BSL**.
   - *A-favor:* SL bajo el swing que se acaba de romper (último HL en uptrend) o bajo el borde del OB/FVG de entrada.
6. **TP estructural:** liquidez opuesta del HTF (BSL si long / SSL si short) o siguiente estructura. El RR resulta del par; no se fuerza 1:2.

---

## 3. Algoritmo (replicar en código)

```text
# Niveles ya disponibles en el repo (detectors/liquidity_context.py, detect_bos.py):
#   bsl_price / ssl_price   -> zonas de liquidez (libro 05)
#   canonical_sweep()        -> sweep valido (rompe y cierra adentro)
#   swing_high / swing_low   -> de detect_bos._swing_points (sin look-ahead, #1)
#   bos_level                -> nivel del BOS (detect_bos)
#
# SL ESTRUCTURAL (reemplaza el fallback entry ± atr):

def calc_structural_sl(row, direction, ctx):
    # ctx = contexto de la vela de entrada (exec TF + HTF)
    if direction == 1:   # LONG
        # 1) si hubo sweep de SSL en esta vela/contexto -> SL bajo la mecha de caza
        if ctx["sweep_down"]:
            return ctx["sweep_low"] - tick   # minimo de la vela que barrio SSL
        # 2) si no, bajo el swing_low previo (estructura rota)
        if ctx["swing_low"] is not None:
            return ctx["swing_low"] - tick
        # 3) fallback SOLO si no hay nada estructural: borde del OB/FVG
        if ctx["ob_low"] is not None:
            return ctx["ob_low"] - tick
    else:               # SHORT (espejo)
        if ctx["sweep_up"]:
            return ctx["sweep_high"] + tick
        if ctx["swing_high"] is not None:
            return ctx["swing_high"] + tick
        if ctx["ob_high"] is not None:
            return ctx["ob_high"] + tick
    return None  # sin estructura -> NO operar (no SL por ATR)

# El motor (engine.build_signals_from_frames) debe usar calc_structural_sl()
# en lugar de: sl = sl_level if sl_level is not None else (entry - atr ...)
```

**Riesgos:** look-ahead en `sweep_low`/`swing_low` (deben venir de `.shift(1)`, ya corregido en `#1`); zona horaria para killzone; no comprimir el SL para ganar tamaño de lote (regla 1% del riesgo, no del SL).

---

## 4. Código SMC-SYSTEMS (dónde vive y qué falta)

| Pieza | Ruta | Rol hoy | Gap |
|-------|------|---------|-----|
| Detector de liquidez | `detectors/liquidity_context.py` | Expone `bsl_price`/`ssl_price` + `canonical_sweep` | ✅ listo para usar |
| Swings | `detectors/bos.py` `_swing_points` | `swing_high`/`swing_low` sin look-ahead | ✅ listo |
| BOS nivel | `detectors/bos.py` | `bos_level` | ✅ listo |
| **Motor de SL** | `ict_backtest/engine.py` `_invalidation_level` (línea 303) | Busca `estructura["M15"]["invalidation"]` → **esa columna NUNCA se crea** → devuelve `None` | 🔴 columna inexistente |
| **Fallback de SL** | `ict_backtest/engine.py` línea 113 | `sl = entry ± atr` (ATR ciego) | 🔴 este es el bug |
| Checklist | `ict_backtest/rules.py` `checklist_intradia` | Exige sweep + BOS opuesto, entra al **close del BOS** (tarde) | 🔴 timing de entrada |
| Backtest R4 | `scripts/r4_turtle_v28.py` | `--tp-mode fixed2r` (TP 2 ATR) | 🔴 RR fijo |

**Cadena de falla (R4 v28):** el motor pide `invalidation` → no existe → cae a `entry ± atr` → SL a 1 ATR, flotante, sin ancla estructural → el 65-70% de trades explota en SL porque el ruido inmediato (y el segundo toque del fallo del sweep) lo saca antes de que el TP de 2 ATR madure.

---

## 5. Auditoría y huecos

- **Hallazgo nuevo (2026-07-13):** el SL estructural no está cableado. `build_features` (`data_feed.py`) no genera `invalidation`; `_invalidation_level` siempre devuelve `None`; el motor usa ATR. Confirmado por lectura de código, no conjetura.
- **Hallazgo previo relevante (#1/#2 en `10_AUDITORIA_REFACCION/`):** swings ya sin look-ahead y CHOCH real — los niveles para anclar el SL YA existen en el repo; solo falta cablearlos al motor.
- **Hueco de timing:** el motor entra al `close` de la vela del BOS (línea 107 `entry = row["close"]`), no en el fallo del sweep. Para Turtle Soup correcto debería entrar tras el retorno a la zona, con SL en la mecha de caza.
- **Sistemas a fin (en el repo):** `05_LIQUIDEZ.md` (sweep = rompe y cierra adentro), `06_TURTLE_SOUP.md` (ya dice "SL más allá del sweep"), `02_MSS_CHOCH.md` (niveles de invalidación por swing/BOS), `12_ESTRATEGIAS_COMPLETAS.md` (inventario). Todos coinciden: el SL va a estructura, no a ATR.

---

## 6. Resultados

Backtest actual (R4 v28, Turtle Soup CT fixed2r) con SL por ATR:
- EURUSD: PF 0.771, WR 29%, 521 trades, 363 SL / 137 TP → 70% SL.
- GBPUSD: PF 0.993, WR 34%, 667 trades, 437 SL / 215 TP → 65% SL.
Hipótesis a validar tras el parche: anclar el SL a la mecha del sweep debe reducir las salidas por ruido y mejorar WR/PF (la cifra la dará el re-run, no se afirma aquí).

---

## 7. Checklist de aplicación al sistema

- [ ] `data_feed.build_features`: exponer `sweep_low`/`sweep_high` (de `canonical_sweep`) y `ob_low`/`ob_high` al motor.
- [ ] `engine._invalidation_level` / nuevo `calc_structural_sl`: usar mecha del sweep → swing → OB (nunca ATR).
- [ ] `engine.build_signals_from_frames`: reemplazar `sl = sl_level if ... else entry ± atr` por `calc_structural_sl(...)`.
- [ ] `rules.checklist_intradia`: entrar tras el retorno a zona (fallo del sweep), no al close del BOS.
- [ ] Re-run R4 con `--tp-mode liquidity` (TP en BSL/SSL opuesto) y SL estructural; comparar WR/PF vs v28.
- [ ] Tests: `tests/` para `calc_structural_sl` (sintéticos: long tras sweep SSL → SL bajo mecha; short tras sweep BSL → SL sobre mecha).

---

## En resumen

El SL estructural es la regla que separa ICT/SMC de "poner un stop a tamaño fijo": el stop invalida la tesis, no mide volatilidad. El repo YA tiene todos los niveles (sweep, swing, OB, BSL/SSL) pero el motor de backtest no los usa y cae a `entry ± atr`. Ese es el bug que explica por qué Turtle Soup revienta en SL. El parche es cablear `calc_structural_sl` al motor y entrar en el fallo del sweep, no en el BOS confirmado.
