# Contrato ejecutable — AHF (Adaptive Hierarchical MTF Funnel)

**Estado:** NORMATIVO v1  
**Módulo:** `engine/ahf.py`  
**SDD:** `docs/planificacion/SDD_CONTEXT_STATE_MTF_NAVIGATION.md` §4.3  
**Capas:** `docs/contratos/CONTRATO_MULTI_TF_LAYERS.md`

---

## 1. Definición

Máquina de estados **jerárquica, dirigida por eventos**, top-down entre temporalidades.  
**No** es un loop que inspecciona todos los TF en cada vela.  
**No** emite entradas.

---

## 2. Estados

```text
WAIT_D1 → D1_LOCKED → WAIT_H4 → H4_LOCKED → WAIT_H1 → WAIT_LTF → SETUP_READY → OUTCOME
```

Estados de terminal / espera también incluyen el estado actual de retroceso (`WAIT_*` tras invalidación).

---

## 3. Eventos de transición (hacia adelante)

| Evento | Desde | Hacia | Condición mínima (v1) |
|--------|-------|-------|------------------------|
| `D1_PASS` | WAIT_D1 | D1_LOCKED | Snapshot D1: estructura conocida **o** pool de liquidez |
| *(auto)* | D1_LOCKED | WAIT_H4 | Inmediato al lock |
| `H4_PASS` | WAIT_H4 | H4_LOCKED | Snapshot H4 disponible as-of t |
| *(auto)* | H4_LOCKED | WAIT_H1 | Inmediato |
| `H1_PASS` | WAIT_H1 | WAIT_LTF | Estructura H1 **o** seq_depth ≥ 1 |
| `LTF_CONFIRMATION` | WAIT_LTF | SETUP_READY | Trigger proxy (disp) **o** seq_depth ≥ 4 (si no hay LTF frame) |
| `OUTCOME_MARK` | SETUP_READY | OUTCOME | Solo marcado de estudio; sin fill |

---

## 4. Invalidación (retroceso)

| Evento | Efecto |
|--------|--------|
| `H1_INVALIDATED` | → WAIT_H1 (desde WAIT_LTF / SETUP_READY) |
| `H4_INVALIDATED` | → WAIT_H4 |
| `D1_INVALIDATED` | → WAIT_D1 |

Reglas:

- No se borra el historial de transiciones.
- `invalidation_reason` obligatorio.
- Solo evidencia con `time ≤ t` y **posterior** al `transition_time` del lock que se invalida.

Invalidación v1 (heurística documentada, no tesis completa):

- **D1:** bias estructural pasa de BULLISH↔BEARISH respecto del lock.
- **H4:** bias H4 opuesto al D1_LOCKED direction_hint de forma sostenida (cambio de label).
- **H1:** seq_depth visible cae a 0 tras haber pasado H1_PASS (pérdida de evidencia de secuencia) — raro; o BOS contrario explícito en snapshot.

---

## 5. Campos obligatorios por transición

```text
state
active_tf
confirmed_context   # snapshots locked
transition_event
transition_time
parent_state
invalidation_reason  # null si avance
```

Todo evaluado `as-of(t)`.

---

## 6. Policy

```text
AHF_STATE ≠ ENTRY
SETUP_READY ≠ ORDER
```

---

## 7. Gate v1

- Tests de avance D1→…→SETUP_READY en datos sintéticos.
- Tests de no look-ahead HTF.
- Tests de retroceso con `invalidation_reason`.
- Smoke sobre EURUSD sin claim de edge.
