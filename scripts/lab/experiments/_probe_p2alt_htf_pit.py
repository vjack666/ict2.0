#!/usr/bin/env python3
"""P2-ALT PIT gate: FULL vs PREFIX on the H4 STRUCTURE columns AND on the
DERIVED filter series (htf_break_dir = forward-filled direction of the last
BOS/CHoCH structural break).

Checks the WHOLE prefix (not only the last bar) so retroactive relabelling is
detected. Writes reports/audits/data/p2alt_h4_pit.json.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.market_features import build_features  # noqa: E402

H4_CSV = ROOT / "datasets" / "eurusd_dukascopy_20y" / "EURUSD_H4.csv"
OUT = ROOT / "reports" / "audits" / "data" / "p2alt_h4_pit.json"

COLS = ["bos_direction", "choch_signal"]


def break_dir_series(feat: pd.DataFrame) -> np.ndarray:
    """Forward-filled direction of the most recent structural break.

    CHoCH takes precedence over BOS on the same bar (frozen tie rule).
    """
    bos = feat["bos_direction"].astype(str).to_numpy()
    ch = feat["choch_signal"].astype(str).to_numpy()
    out = np.zeros(len(feat), dtype=np.int8)
    cur = 0
    for i in range(len(feat)):
        ev = 0
        if ch[i] == "CHOCH_BULLISH":
            ev = 1
        elif ch[i] == "CHOCH_BEARISH":
            ev = -1
        elif bos[i] == "BULLISH":
            ev = 1
        elif bos[i] == "BEARISH":
            ev = -1
        if ev != 0:
            cur = ev
        out[i] = cur
    return out


def main() -> None:
    t0 = time.time()
    df = pd.read_csv(H4_CSV)
    n = len(df)
    full = build_features(df.copy())
    full_bd = break_dir_series(full)

    cuts = [int(n * f) for f in (0.1, 0.3, 0.5, 0.7, 0.9)]
    per_cut = []
    viol_cols = {c: 0 for c in COLS}
    viol_bd = 0
    for cut in cuts:
        pref = build_features(df.iloc[: cut + 1].copy())
        rec: dict = {"cut": cut}
        for c in COLS:
            a = full[c].iloc[: cut + 1].astype(str).to_numpy()
            b = pref[c].astype(str).to_numpy()
            nv = int((a != b).sum())
            viol_cols[c] += nv
            rec[c] = nv
        pb = break_dir_series(pref)
        nvb = int((full_bd[: cut + 1] != pb).sum())
        viol_bd += nvb
        rec["htf_break_dir"] = nvb
        per_cut.append(rec)
        print(rec, flush=True)

    total_viol = sum(viol_cols.values()) + viol_bd
    out = {
        "probe": "P2ALT_H4_PIT_FULL_VS_PREFIX",
        "h4_rows": n,
        "cuts": cuts,
        "per_cut_prefix_wide_violations": per_cut,
        "totals": {**viol_cols, "htf_break_dir": viol_bd},
        "n_cuts": len(cuts),
        "cuts_with_violations": sum(1 for r in per_cut if r["htf_break_dir"] > 0),
        "pit_stable": bool(total_viol == 0),
        "elapsed_s": round(time.time() - t0, 2),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("WROTE", OUT, flush=True)
    print(json.dumps(out["totals"]), "pit_stable=", out["pit_stable"], flush=True)


if __name__ == "__main__":
    main()
