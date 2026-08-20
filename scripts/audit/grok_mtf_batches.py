#!/usr/bin/env python3
"""Grok cloud runner — MTF dense por batches (resume-friendly).

Usado cuando el MTF denso (sample_every=100, ~1239 puntos) se corta por
timeout de sesión. Reanuda desde RESUME_FROM (índice en la lista de samples).

Commiteado en scripts/ para trazabilidad.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
from audits.codigo.funnel import FunnelAudit  # noqa: E402
from engine.mtf_navigation import MTFNavigator, NavigatorConfig  # noqa: E402

OUT = ROOT / "reports" / "audits" / "mtf_seq_funnel.json"
BATCH = 150
EVERY = 100
RESUME_FROM = 0  # set 600 / 900 / 1050 según checkpoint n_samples


def load_tf(tf: str) -> pd.DataFrame:
    for base in (
        ROOT / "data" / "raw" / "EURUSD",
        ROOT / "datasets" / "eurusd_dukascopy_20y",
    ):
        p = base / f"EURUSD_{tf}.csv"
        if p.exists():
            df = pd.read_csv(p)
            df["time"] = pd.to_datetime(df["time"])
            return df
    raise FileNotFoundError(f"EURUSD_{tf}.csv not found")


def main() -> None:
    if not OUT.exists():
        raise SystemExit(f"missing prior report: {OUT} (run grok_run_funnel_20y_full first)")

    report = json.loads(OUT.read_text())
    prior_n = int((report.get("mtf_navigation") or {}).get("n_samples") or 0)
    prior_ok = float((report.get("mtf_navigation") or {}).get("ok_rate") or 1.0)

    frames = {tf: load_tf(tf) for tf in ("H1", "H4", "D1")}
    h1 = frames["H1"]
    idxs = list(range(500, len(h1), EVERY))
    rest = idxs[RESUME_FROM:]
    print(
        f"resume prior_n={prior_n} remaining={len(rest)} target={len(idxs)} RESUME_FROM={RESUME_FROM}",
        flush=True,
    )

    nav = MTFNavigator(
        frames, NavigatorConfig(precompute_sequences=False, sequence_tf="H1")
    )
    records: list[dict] = []
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
            "ok_rate": ok_count / total_n if total_n else 0.0,
            "complete": done,
        }
        report["checkpoint"] = "COMPLETE" if done else f"mtf_resume_{total_n}"
        report["status"] = "COMPLETE" if done else None
        report["runner"] = "scripts/grok_mtf_batches.py"
        report["updated_at"] = datetime.now(timezone.utc).isoformat()
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2, default=str))
        print(
            f"  total_n={total_n} ok_rate={ok_count / total_n:.3f} done={done}",
            flush=True,
        )

    print("DONE", total_n, flush=True)


if __name__ == "__main__":
    main()
