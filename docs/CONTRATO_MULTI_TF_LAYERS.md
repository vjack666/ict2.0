# Contrato — Capas Multi-TF (`htf` / `itf` / `exec_tf`)

**Estado:** NORMATIVO  
**SDD padre:** `docs/SDD_CONTEXT_STATE_MTF_NAVIGATION.md` (§4.3 AHF, §4.4 anti-look-ahead)  
**Fecha:** 2026-08-18

---

## 1. Capas

| Rol | Nombre canónico | TF típicos | Decide |
|-----|-----------------|------------|--------|
| **HTF** | `htf` | D1 (o H4 si no hay D1) | Contexto, location, regime, liquidity targets |
| **ITF** | `itf` | H4 (o H1 si exec es LTF) | Estructura intermedia, posición en dealing range HTF |
| **EXEC** | `exec_tf` | H1 / M15 / M5 | Timing, secuencia, retest/trigger |

Reglas:

1. Las tres capas son **separadas** en el contrato de datos (no `exec_tf == ltf` implícito sin declararlo).
2. Una decisión en `exec_tf` en tiempo \(t\) solo lee HTF/ITF con **velas cerradas** `close_time ≤ t`.
3. Ninguna capa reescribe el pasado de otra.

---

## 2. Timestamps

```text
as_of(tf, t) = última barra de tf con time ≤ t
```

- Si `as_of` es vacío → esa capa no aporta evidencia en \(t\).
- Prohibido: centrar pivotes HTF usando barras con `time > t`.

---

## 3. Qué puede / no puede cada capa

| Capa | Puede | No puede |
|------|-------|----------|
| HTF | LOCK de contexto, constraints, invalidar hacia abajo | Emitir entry |
| ITF | LOCK de estructura relativa al HTF | Invalidar HTF sin evidencia HTF |
| EXEC | Avanzar a SETUP_READY solo con HTF+ITF locked (salvo modo degradado documentado) | Usar HTF futuro |

---

## 4. Relación con AHF

El AHF (`engine/ahf.py`) es la máquina que **camina** estas capas:

```text
WAIT_D1 → D1_LOCKED → WAIT_H4 → H4_LOCKED → WAIT_H1 → WAIT_LTF → SETUP_READY → OUTCOME
```

Invalidación superior fuerza retroceso (ver `CONTRATO_AHF.md`).

---

## 5. Gate

PASS cuando:

- Este contrato está en `main`.
- AHF ejecutable respeta `as_of` por capa.
- Tests demuestran que datos futuros HTF no alteran estado en \(t\).
