# EXP — SEQUENCE × CONTEXT STATE (H1 20Y)

**Fecha:** 2026-08-19  
**Estado:** EJECUTADO (Grok cloud)  
**Pregunta:** ¿La misma secuencia tiene una distribución de resultados distinta según Context State?  
**Contrato:** `../contratos/CONTRATO_CONTEXT_STATE.md`  
**Driver:** `scripts/exp_sequence_x_context_state.py`  
**Artefacto:** `reports/audits/exp_sequence_x_context_state_H1_20Y.json`

---

## 1. Hipótesis

```text
H1: depth(secuencia) ≥ k  +  CTX_ALIGNED
      vs
H0: depth(secuencia) ≥ k  +  CTX_AGAINST | CTX_NEUTRAL
        ↓
¿cambia P(end>0), mean(end), a horizontes fijos?
```

Prioridad: **máxima** (`SDD_CONTEXT_STATE_MTF_NAVIGATION.md` §5).

---

## 2. Diseño

| Elemento | Valor v1 |
|----------|----------|
| Dataset | EURUSD Dukascopy 20Y H1/H4/D1 |
| Secuencia | `engine/sequential_events.run_sequential` (`structure_mode=canonical_bos`) |
| Universo | Cadenas con **depth ≥ 4** (llegaron a STRUCTURE) |
| Ancla temporal | Barra del nodo STRUCTURE (point-in-time) |
| Context State | `MTFNavigator.navigate(t=time[STRUCTURE], exec_tf=H1)` → buckets §3 del contrato |
| Dirección secuencia | `chain.direction` (+1 / −1) |
| Outcome | Movimiento firmado del close desde ancla: `direction * (close[t+h] - close[t])` en h ∈ {6,12,24,48} |
| Baseline | Todas las depth≥4 sin estratificar |
| **No** | Stop fijo, entry, PnL de sistema, OTE como tesis |

Policy:

```text
SEQUENCE × CONTEXT  =  objeto de estudio de distribución
SEQUENCE × CONTEXT  ≠  señal de trading aprobada
```

---

## 3. Métricas mínimas

Por bucket (`CTX_ALIGNED`, `CTX_AGAINST`, `CTX_NEUTRAL`, `ALL_DEPTH4`):

- n (cadenas; tras dedup por `structure_bar` si aplica)
- end>0 @ +6 / +12 / +24 / +48
- mean end (precio) @ +24
- n efectivo y aviso si n < 30

Gate de **interpretación**:

| Condición | Lectura |
|-----------|---------|
| n_ALIGNED < 30 o n_AGAINST < 30 | **INSUFICIENTE** — no declarar edge |
| |end>0_ALIGNED − end>0_AGAINST| estable y n≥30 | Hipótesis **compatible** (no = edge operativo) |
| Diferencia ≈ 0 con n decente | Hipótesis **no soportada** en este diseño |

---

## 4. Relación con evidencias previas

| EXP previo | Relación |
|------------|----------|
| Multi-factor EMA | **No** sustituye este EXP (proxy inválido) |
| COMPLETE expectancy | n≈5; aquí se usa depth≥4 para potencia |
| TNA AHF | Valida navegación; este EXP mide **outcome distribution** |

---

## 5. Resultado (corrida 2026-08-19 — Grok)

**Gate:** `INSUFFICIENT_N`

| Bucket | n | end>0 +6 | +12 | +24 | +48 | mean_end +24 |
|--------|--:|---------:|----:|----:|----:|-------------:|
| ALL_DEPTH4 | 24 | 50.0 | 37.5 | 45.83 | 41.67 | −0.001195 |
| CTX_ALIGNED | 5 | 40.0 | 0.0 | 40.0 | 40.0 | −0.001914 |
| CTX_AGAINST | 11 | 54.55 | 54.55 | 45.45 | 54.55 | −0.001929 |
| CTX_NEUTRAL | 8 | 50.0 | 37.5 | 50.0 | 25.0 | +0.000264 |

- Δ (ALIGNED − AGAINST) end>0@+24: **−5.45** pp (ruido; n demasiado bajo)
- Secuencia: 1460 cadenas; depth≥4 raw 32; scored dedup por structure_bar: **24**
- COMPLETE: 3 (como EXP previo)
- EMA: **no usada**
- elapsed: ~46 s

### Lectura correcta

1. El pipeline **SEQUENCE × CONTEXT STATE** corre de punta a punta (contrato + navigator + sequential).
2. Con **canonical_bos**, depth≥4 sigue siendo escaso (n=24) → no se puede contrastar H1.
3. Los % por bucket **no** autorizan edge ni entry.
4. Siguiente ingeniería útil: subir n de depth≥4 (ventanas, structure_mode lite en ablación, o depth≥3) **sin** volver a flags EMA; o anclar en DISPLACEMENT/STRUCTURE con stop fijo cuando n≥30 por bucket.

### Policy

```text
SEQUENCE × CONTEXT  =  objeto de estudio
SEQUENCE × CONTEXT  ≠  señal de trading aprobada
```
