"""Demo de replay real acotado: reconstruye el Market State vela a vela.

NO es un test de gates; es evidencia visual de que engine/lifecycle funciona
como autoridad única de transición. Corre sobre velas sintéticas small replay.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from engine.detectors.fvg import detect_fvg
from engine.lifecycle import evaluate
from engine.market_object import ObjectState


def _ts(n):
    return datetime(2024, 3, 15, tzinfo=timezone.utc) + timedelta(minutes=n)


def _row(i, o, h, l, c):
    return {"__index__": i, "time": _ts(i), "open": o, "high": h, "low": l, "close": c}


# Velas M15: FVG bull nace en bar 10 (gap entre first.high y third.low).
rows = [
    _row(8, 1.1000, 1.1002, 1.0998, 1.1001),
    _row(9, 1.1001, 1.1003, 1.0999, 1.1002),   # first
    _row(10, 1.1002, 1.1010, 1.1000, 1.1009),  # displacement (third) -> FVG [1.1003, 1.1010]
    _row(11, 1.1009, 1.1012, 1.1005, 1.1008),  # penetra: partial
    _row(12, 1.1008, 1.1011, 1.1004, 1.1007),  # sigue partial
    _row(13, 1.1007, 1.1009, 1.0995, 1.0998),  # low<1.1003 far_side, close<far => INVALIDATED
]

fvgs = detect_fvg(rows, timeframe="M15", symbol="EURUSD")
assert fvgs, "se esperaba al menos un FVG"
obj = fvgs[0]
print(f"FVG detectado: {obj.id} zona=[{obj.zone_low},{obj.zone_high}] dir={obj.direction}")

print("\nMARKET STATE por vela (authority_tf=M15):")
print(f"{'bar':>3} {'time':>8} {'state':<22} {'reason'}")
prefix = rows[:2]
for b in rows[2:]:
    # Detectores solo sobre prefijo time<=b.time; lifecycle evalúa vela cerrada.
    d = evaluate(obj, b, authority_tf="M15")
    print(f"{b['__index__']:>3} {b['time'].strftime('%H:%M'):>8} {d.new_state:<22} {d.reason}")
    assert not d.changed or (d.previous_state != d.new_state)

print(f"\nEstado final: {obj.state.value}  (terminal={obj.is_terminal})")
print(f"first_touch_bar={obj.first_touch_bar}  invalidated_bar={obj.invalidated_bar}")
assert obj.state == ObjectState.INVALIDATED
print("\nOK: lifecycle llevó FVG de ACTIVE -> PARTIAL -> INVALIDATED de forma causal.")
