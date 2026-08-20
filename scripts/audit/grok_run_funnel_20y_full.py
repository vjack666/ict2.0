#!/usr/bin/env python3
"""Grok cloud runner — Funnel 20Y FULL (FVG/OB + Sequence + MTF dense).

Commiteado en scripts/ para trazabilidad. No es el módulo canónico
(audits/codigo/mtf_seq_funnel.py); es el orquestador pesado usado en la nube
con checkpoints y densificación MTF (sample_every=100).

Policy: AUDIT_FUNNEL_NO_PNL_NO_ENTRY. Anti-indicadores: no EMA/ATR/OTE.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from audits.codigo.mtf_seq_funnel import (  # noqa: E402
    _load_tf,
    funnel_fvg_ob,
    funnel_mtf_navigation,
    funnel_sequence,
)

OUT = ROOT / "reports" / "audits" / "mtf_seq_funnel.json"
CKPT = Path("/tmp/funnel_ckpt.json")


def save(report: dict, tag: str) -> None:
    report["checkpoint"] = tag
    report["updated_at"] = datetime.now(timezone.utc).isoformat()
    text = json.dumps(report, indent=2, default=str)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text)
    try:
        CKPT.write_text(text)
    except OSError:
        pass
    print(f"[CKPT] {tag} written → {OUT}", flush=True)


def main() -> None:
    t0 = time.time()
    print("FUNNEL 20Y FULL START", flush=True)
    frames = {tf: _load_tf(tf) for tf in ("H1", "H4", "D1")}
    for tf, df in frames.items():
        print(f"  loaded {tf}: {len(df)} bars", flush=True)

    report: dict = {
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
        "runner": "scripts/grok_run_funnel_20y_full.py",
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
                        "causal_links",
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

    print("=== MTF navigation dense sample_every=100 ===", flush=True)
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
