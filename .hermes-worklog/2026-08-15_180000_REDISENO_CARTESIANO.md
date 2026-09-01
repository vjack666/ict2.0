# Bitácora — Rediseño cartesiano Task 1/2 (objeto persistente + linaje padre-hijo)

**Fecha:** 2026-08-15 18:00 UTC-5
**Plan:** `.hermes/plans/2026-08-15_143000-individual-tools-m5-learning.md`
**Veredicto aplicado:** SWING = objeto geométrico persistente; BOS = evento hijo que consume el nivel (método padre-hijo de SMC-SYSTEMS, llevado un paso más allá).

---

## Cambio de diseño (solicitado por el Director)
No basta con `parent_id`. El Director pidió que SWING sea un OBJETO PERSISTENTE con geometría cartesiana completa, y BOS un evento hijo que consume ese nivel, sin look-ahead ni coincidencia de precios.

## tools/event.py — extendido
ToolEvent ahora lleva:
- `event_kind`: "object" (persistente) | "event" (ruptura)
- `id`, `parent_id`
- `origin_bar` (vela del pivot), `confirmation_bar` (vela de confirmación sin look-ahead), `break_bar` (vela de ruptura, None si no roto)
- `price` (nivel cartesiano y), `status` (active|broken|confirmed)

## tools/swing.py — reescrito
- SwingTool emite SWING como objeto persistente: `id=SW_SH_0001`, `origin_bar`, `confirmation_bar=origin_bar+lookback` (SIN look-ahead: ventana central ya no reetiqueta), `price`, `status="active"`, `event_kind="object"`.
- El swing PERMANECE hasta que un BOS lo rompa (Task 3 marca break_bar).

## Verificación (EURUSD M5, 1 mes 2026-07-14→08-14)
- SWING events: 840 (HH 195, LH 223, HL 222, LL 200).
- Ejemplo objeto: `id=SW_SH_0001, origin_bar=10, confirmation_bar=15, price=1.13872, status=active, event_kind=object`.
- Log jsonl: campos completos (id, origin_bar, confirmation_bar, price, human_score=null).

## Por qué esto resuelve la línea horizontal cartesiana
Cuando Task 3 genere BOS con `parent_id=SW_SH_0001`, `break_bar=30`, `price=1.13872`:
- Línea estructural: origin_bar(10) ── precio 1.13872 ── break_bar(30).
- Es objeto DERIVADO DEL LINAJE, no dos precios que coinciden.
- Permite preguntar "¿qué swing originó este BOS?" y "¿hasta qué vela estuvo vigente el swing?".

## Aislamiento mantenido
tools/swing.py sigue importando SOLO pandas/numpy + tools.base/event. NO importa detectors/engine.

## Siguiente
Task 3: tools/bos.py — envuelve detect_bos de forma aislada; por cada BOS emite evento hijo con parent_id=último swing roto, break_bar, price=bos_level, status=broken sobre el swing padre.
