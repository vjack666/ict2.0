# Scripts — Funnel 20Y + anti-indicadores (Grok cloud)

**Tarea:** Funnel 20Y completo (FVG/OB + Sequence + MTF dense) + corrección anti-OTE en `dealing_range`.  
**Repo:** `vjack666/ict2.0`  
**Norma:** SIN EMA, SIN ATR como bias, SIN OTE/Fibonacci 62–79%.  
**Fecha corrida:** 2026-08-20  

Salidas:

- `reports/audits/mtf_seq_funnel.json`
- `reports/audits/mtf_seq_funnel_20Y.md`
- `engine/dealing_range.py` (EQ50 only)

---

## 0. Prerequisitos

```bash
git clone https://github.com/vjack666/ict2.0.git
cd ict2.0
python3 -m pip install pandas pyarrow numpy
mkdir -p data/raw/EURUSD reports/audits
cp datasets/eurusd_dukascopy_20y/EURUSD_*.csv data/raw/EURUSD/
```

Dataset esperado:

| TF | barras (aprox) |
|----|----------------|
| H1 | 124377 |
| H4 | 32133 |
| D1 | 6258 |

---

## 1. Corrección anti-indicadores — `engine/dealing_range.py`

Reemplaza el archivo completo. Elimina OTE_LONG/OTE_SHORT y bandas Fibonacci 0.62–0.79.  
Solo zonas canónicas: `DISCOUNT | EQ | PREMIUM` (EQ = 50% ± banda 12%).

```python
"""Premium/Discount EQ50%. SIN indicadores, SIN OTE/Fibonacci (ICT_RULEBOOK §9)."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd

BULLISH, BEARISH, NEUTRAL = "BULLISH", "BEARISH", "NEUTRAL"
_EQ_BAND, _EPS = 0.12, 1e-9


@dataclass(frozen=True)
class DealingRangeConfig:
    lookback: int = 10
    eq_band: float = _EQ_BAND


def compute_dealing_range(frame, lookback=10, config=None):
    if config is None:
        config = DealingRangeConfig(lookback=lookback)
    data = frame.copy()
    rh = data["high"].rolling(config.lookback, min_periods=1).max()
    rl = data["low"].rolling(config.lookback, min_periods=1).min()
    span = (rh - rl).clip(lower=_EPS)
    data["range_high"] = rh
    data["range_low"] = rl
    data["zone_high"] = rh
    data["zone_low"] = rl
    data["zone_mid"] = (rh + rl) / 2.0
    c, m = data["close"], data["zone_mid"]
    band = span * float(config.eq_band)
    in_eq = (c - m).abs() <= band
    data["premium_discount_zone"] = np.select(
        [in_eq, (~in_eq) & (c < m), (~in_eq) & (c >= m)],
        ["EQ", "DISCOUNT", "PREMIUM"],
        default="EQ",
    )
    data["premium_distance"] = np.where(
        c >= m,
        (c - m) / (data["zone_high"] - m + _EPS),
        -(m - c) / (m - data["zone_low"] + _EPS),
    )
    return data


def _is_favorable(zone, direction):
    return (direction == BULLISH and zone == "DISCOUNT") or (
        direction == BEARISH and zone == "PREMIUM"
    )


def dealing_range_htf(frame, htf_bias, lookback=10):
    if frame is None or len(frame) == 0:
        return {
            "zone": "EQ",
            "distance": 0.0,
            "bias": getattr(htf_bias, "direction", NEUTRAL),
            "is_favorable": False,
        }
    last = compute_dealing_range(frame, lookback=lookback).iloc[-1]
    z = str(last["premium_discount_zone"])
    d = getattr(htf_bias, "direction", NEUTRAL) or NEUTRAL
    return {
        "zone": z,
        "distance": float(last["premium_distance"]),
        "bias": d,
        "is_favorable": _is_favorable(z, d),
    }
```

---

## 2. Runner principal — Funnel 20Y con checkpoints

Script usado: `/tmp/run_funnel_20y_full.py`  
Ejecuta FVG/OB (H1/H4/D1) + Sequence H1 + MTF dense. Escribe checkpoint tras cada etapa.

```python
#!/usr/bin/env python3
"""Funnel 20Y FULL — FVG/OB (H1/H4/D1) + Sequence H1 + MTF nav dense.

Quality run: no dataset truncation. MTF sample_every=100 (~1.2k points).
Writes checkpoint JSON after each major stage. No PnL / no entry.
Anti-indicator: detectors + sequential + MTFNavigator (structure/BOS), no EMA.
"""
from __future__ import annotations
import json, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/home/workdir/ict2.0")
sys.path.insert(0, str(ROOT))

from audits.codigo.mtf_seq_funnel import (
    funnel_fvg_ob,
    funnel_sequence,
    funnel_mtf_navigation,
    _load_tf,
)

OUT = ROOT / "reports" / "audits" / "mtf_seq_funnel.json"
ART = Path("/home/workdir/artifacts") / "mtf_seq_funnel.json"
CKPT = Path("/tmp/funnel_ckpt.json")


def save(report: dict, tag: str) -> None:
    report["checkpoint"] = tag
    report["updated_at"] = datetime.now(timezone.utc).isoformat()
    text = json.dumps(report, indent=2, default=str)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text)
    ART.parent.mkdir(parents=True, exist_ok=True)
    ART.write_text(text)
    CKPT.write_text(text)
    print(f"[CKPT] {tag} written", flush=True)


def main() -> None:
    t0 = time.time()
    print("FUNNEL 20Y FULL START", flush=True)
    frames = {tf: _load_tf(tf) for tf in ("H1", "H4", "D1")}
    for tf, df in frames.items():
        print(f"  loaded {tf}: {len(df)} bars", flush=True)

    report = {
        "dataset": "dukascopy EURUSD 20Y",
        "symbol": "EURUSD",
        "policy": "AUDIT_FUNNEL_NO_PNL_NO_ENTRY",
        "anti_indicators": {
            "ema": False,
            "atr_as_bias": False,
            "ote_fibonacci": False,
            "source": "structure/BOS + FVG/OB detectors + sequential + MTFNavigator",
            "dealing_range": "EQ50_ONLY_NO_OTE",
        },
        "fvg_ob": {},
        "sequence": {},
        "mtf_navigation": {},
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    for tf in ("H1", "H4", "D1"):
        print(f"=== FVG/OB funnel {tf} ===", flush=True)
        t1 = time.time()
        report["fvg_ob"][tf] = funnel_fvg_ob(frames[tf], tf)
        report["fvg_ob"][tf]["elapsed_s"] = round(time.time() - t1, 2)
        print(
            json.dumps(
                {
                    k: report["fvg_ob"][tf].get(k)
                    for k in (
                        "fvg_count",
                        "ob_count",
                        "relation_count",
                        "audit_status",
                        "elapsed_s",
                    )
                },
                indent=2,
            ),
            flush=True,
        )
        save(report, f"after_fvg_ob_{tf}")

    print("=== SEQUENCE H1 (canonical_bos, full 20Y) ===", flush=True)
    t1 = time.time()
    report["sequence"]["H1"] = funnel_sequence(frames["H1"], "H1")
    report["sequence"]["H1"]["elapsed_s"] = round(time.time() - t1, 2)
    print(
        json.dumps(
            {
                "n_chains": report["sequence"]["H1"].get("n_chains"),
                "n_complete": report["sequence"]["H1"].get("n_complete"),
                "summary": report["sequence"]["H1"].get("summary"),
                "elapsed_s": report["sequence"]["H1"].get("elapsed_s"),
            },
            indent=2,
            default=str,
        ),
        flush=True,
    )
    save(report, "after_sequence_H1")

    print("=== MTF navigation dense sample_every=100 (full span) ===", flush=True)
    t1 = time.time()
    report["mtf_navigation"] = funnel_mtf_navigation(frames, sample_every=100)
    report["mtf_navigation"]["elapsed_s"] = round(time.time() - t1, 2)
    print(
        json.dumps(
            {
                "n_samples": report["mtf_navigation"].get("n_samples"),
                "sample_every": report["mtf_navigation"].get("sample_every"),
                "audit_status": report["mtf_navigation"].get("audit_status"),
                "elapsed_s": report["mtf_navigation"].get("elapsed_s"),
            },
            indent=2,
            default=str,
        ),
        flush=True,
    )

    report["elapsed_s"] = round(time.time() - t0, 2)
    report["status"] = "COMPLETE"
    save(report, "COMPLETE")
    print(
        json.dumps(
            {
                "status": "COMPLETE",
                "elapsed_s": report["elapsed_s"],
                "out": str(OUT),
                "fvg_ob_H1_rel": report["fvg_ob"]["H1"].get("relation_count"),
                "seq_complete": report["sequence"]["H1"].get("n_complete"),
                "seq_chains": report["sequence"]["H1"].get("n_chains"),
                "mtf_samples": report["mtf_navigation"].get("n_samples"),
            },
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
```

Ejecución:

```bash
cd /home/workdir/ict2.0
nohup python3 -u /tmp/run_funnel_20y_full.py > /tmp/funnel_20y.log 2>&1 &
tail -f /tmp/funnel_20y.log
```

---

## 3. MTF denso por lotes (resiliencia a timeouts de sesión)

Si el MTF largo se corta, usar este runner por batches.  
Reanuda desde `RESUME_FROM` (índice en la lista de samples, no bar index).

```python
#!/usr/bin/env python3
"""MTF dense por batches — resume-friendly para sesiones largas."""
from __future__ import annotations
import json, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/home/workdir/ict2.0")
sys.path.insert(0, str(ROOT))
import pandas as pd
from engine.mtf_navigation import MTFNavigator, NavigatorConfig
from audits.codigo.funnel import FunnelAudit

ART = Path("/home/workdir/artifacts/mtf_seq_funnel.json")
OUT = ROOT / "reports" / "audits" / "mtf_seq_funnel.json"
BATCH = 150
EVERY = 100
RESUME_FROM = 0  # cambiar a 600 / 900 / 1050 según checkpoint


def load_tf(tf: str) -> pd.DataFrame:
    df = pd.read_csv(ROOT / "data" / "raw" / "EURUSD" / f"EURUSD_{tf}.csv")
    df["time"] = pd.to_datetime(df["time"])
    return df


def main() -> None:
    report = json.loads(ART.read_text())
    prior_n = int((report.get("mtf_navigation") or {}).get("n_samples") or 0)
    prior_ok = float((report.get("mtf_navigation") or {}).get("ok_rate") or 1.0)

    frames = {tf: load_tf(tf) for tf in ("H1", "H4", "D1")}
    h1 = frames["H1"]
    idxs = list(range(500, len(h1), EVERY))
    rest = idxs[RESUME_FROM:]
    print(f"resume prior_n={prior_n} remaining={len(rest)} target={len(idxs)}", flush=True)

    nav = MTFNavigator(
        frames, NavigatorConfig(precompute_sequences=False, sequence_tf="H1")
    )
    records = []
    t0 = time.time()
    ok_count = int(round(prior_ok * prior_n))
    total_n = prior_n

    for start in range(0, len(rest), BATCH):
        chunk = rest[start : start + BATCH]
        print(f"batch {start // BATCH + 1} n={len(chunk)}", flush=True)
        for i in chunk:
            t = h1["time"].iloc[i]
            st = nav.navigate(decision_time=t, exec_tf="H1")
            ok = st.status == "OK"
            if ok:
                ok_count += 1
            total_n += 1
            records.append(
                {
                    "stage": "MTF_NAV",
                    "id": f"nav_{i}",
                    "accepted": ok,
                    "rejection_reason": None if ok else st.status,
                    "timeframe": "H1",
                }
            )
            records.append(
                {
                    "stage": "MTF_CONSTRAINTS",
                    "id": f"ctx_{i}",
                    "accepted": st.constraints is not None,
                    "timeframe": "H1",
                }
            )

        result, summaries = FunnelAudit(audit_id="A7_MTF_NAV").run(records)
        status = getattr(result.status, "value", str(result.status))
        done = start + BATCH >= len(rest)
        report["mtf_navigation"] = {
            "n_samples": total_n,
            "sample_every": EVERY,
            "anti_lookahead": "docs/ANTI_LOOKAHEAD_MTF_SEQUENCE.md",
            "policy": "CONTEXT_STATE_NOT_ENTRY_SIGNAL",
            "precompute_sequences": False,
            "note": "Dense MTF full span; FVG/OB + sequence audited on full 20Y",
            "audit_status": status,
            "stages": [
                {
                    "stage": s.stage,
                    "input_count": s.input_count,
                    "accepted_count": s.accepted_count,
                    "rejected_count": s.rejected_count,
                }
                for s in summaries
            ],
            "findings": [getattr(f, "code", str(f)) for f in (result.findings or [])],
            "elapsed_s": round(time.time() - t0, 2),
            "ok_rate": ok_count / total_n if total_n else 0,
            "complete": done,
        }
        report["checkpoint"] = "COMPLETE" if done else f"mtf_resume_{total_n}"
        report["status"] = "COMPLETE" if done else None
        report["updated_at"] = datetime.now(timezone.utc).isoformat()
        text = json.dumps(report, indent=2, default=str)
        ART.write_text(text)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(text)
        print(
            f"  total_n={total_n} ok_rate={ok_count / total_n:.3f} done={done}",
            flush=True,
        )

    print("DONE", total_n, flush=True)


if __name__ == "__main__":
    main()
```

Ejecución (ejemplo reanudando desde 1050):

```bash
# Editar RESUME_FROM = 1050 en el script, luego:
nohup python3 -u /tmp/mtf_batches.py > /tmp/mtf_batches.log 2>&1 &
tail -f /tmp/mtf_batches.log
```

---

## 4. Driver canónico del repo (referencia)

El módulo del repo que el runner importa:

```
audits/codigo/mtf_seq_funnel.py
```

Funciones clave:

| Función | Qué hace |
|---------|----------|
| `funnel_fvg_ob(df, tf)` | detect_fvg + detect_order_blocks + relate_fvg_ob STRICT |
| `funnel_sequence(df, tf)` | `run_sequential` canonical_bos + FunnelAudit |
| `funnel_mtf_navigation(frames, sample_every)` | MTFNavigator.navigate en rejilla temporal |
| `main()` | orquesta las 3 etapas y escribe `reports/audits/mtf_seq_funnel.json` |

Para densificar MTF en el módulo del repo (si se quiere persistir el cambio):

```python
# en funnel_mtf_navigation default:
sample_every: int = 100   # antes 2000 / 2500
# y en main():
report["mtf_navigation"] = funnel_mtf_navigation(frames, sample_every=100)
```

---

## 5. Resultados de la corrida (referencia)

```text
FVG/OB H1: 22477 FVG, 2799 OB, 702 relaciones STRICT  → PASS
FVG/OB H4:  6497 FVG,  862 OB, 206 relaciones          → PASS
FVG/OB D1:  1543 FVG,  214 OB,  58 relaciones          → PASS

Sequence H1: 1460 chains, COMPLETE=3, depth≥4=29       → PASS

MTF dense: 1239 samples, ok_rate=1.0                   → PASS
status: COMPLETE
```

---

## 6. Orden de ejecución recomendado

```text
1. Aplicar engine/dealing_range.py (anti-OTE)
2. python3 -u run_funnel_20y_full.py
   → si se corta en MTF:
3. Ajustar RESUME_FROM según checkpoint n_samples
4. python3 -u mtf_batches.py hasta COMPLETE
5. git pull + copiar reports/audits/* a local
```

---

## 7. Policy recordatoria

```text
Funnel  =  auditoría de población / lineage / navegación
Funnel  ≠  edge, PnL, entry
EMA / ATR / OTE  ≠  bias o location normativos
```
