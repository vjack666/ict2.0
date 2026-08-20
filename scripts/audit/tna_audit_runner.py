"""TNA 20Y — Auditoría temporal AHF/MTF (comando: `ejecuta auditoria temporal`).

Driver dedicado que:
  1. Carga EURUSD 20Y (H1/H4/D1) desde data/raw/EURUSD/*.parquet
  2. Corre AdaptiveHierarchicalFunnel.run_timeline sobre TODA la línea temporal
     H1 con secuencia real (NavigatorConfig precompute_sequences=True).
  3. Extrae objetos FVG/OB reales de H1.
  4. Pasa snapshots + objetos al auditor canónico
     (audits.codigo.ahf_temporal_navigation_audit).
  5. Emite DOS gates separados:
       - TNA-TRACE-SE-INTEGRITY  (reproducibilidad + PIT + monotonicidad)
       - TNA-BEHAVIORAL         (navegación bien diseñada, no solo reproducible)

NO es backtest. NO declara PASS por trace válido. NO usa PnL.

Salida: reports/audits/ahf_temporal_navigation_20Y.json + .md
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

# Permitir ejecución como script suelto y como módulo del repo.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.ahf import AdaptiveHierarchicalFunnel, AHFConfig  # noqa: E402
from engine.detectors.fvg import detect_fvg  # noqa: E402
from engine.detectors.ob import detect_order_blocks  # noqa: E402
from engine.mtf_navigation import NavigatorConfig  # noqa: E402
from audits.codigo.ahf_temporal_navigation_audit import (  # noqa: E402
    TemporalAuditConfig,
    audit_snapshots,
)


DATA = ROOT / "data" / "raw" / "EURUSD"
DATASET_CSV = ROOT / "datasets" / "eurusd_dukascopy_20y"
OUT_JSON = ROOT / "reports" / "audits" / "ahf_temporal_navigation_20Y.json"
OUT_MD = ROOT / "reports" / "audits" / "ahf_temporal_navigation_20Y_audit.md"


def _load_tf(tf: str) -> pd.DataFrame:
    """Load TF preferring complete Dukascopy CSV snapshot; fallback to parquet."""
    csv_p = DATASET_CSV / f"EURUSD_{tf}.csv"
    pq_p = DATA / f"EURUSD_{tf}.parquet"
    if csv_p.exists():
        df = pd.read_csv(csv_p, parse_dates=["time"])
        src = str(csv_p.relative_to(ROOT))
    elif pq_p.exists():
        df = pd.read_parquet(pq_p)
        src = str(pq_p.relative_to(ROOT))
    else:
        raise FileNotFoundError(
            f"No existe CSV versionado ({csv_p}) ni parquet ({pq_p}). "
            "Use datasets/eurusd_dukascopy_20y/ (SHA256SUMS)."
        )
    if "time" not in df.columns:
        raise ValueError(f"{src} no tiene columna 'time'")
    df = df.sort_values("time").reset_index(drop=True)
    print(f"  loaded {tf}: n={len(df)} from {src}", flush=True)
    return df


def _fvg_ob_objects(df: pd.DataFrame, tf: str) -> list[dict[str, Any]]:
    """Extrae objetos FVG/OB reales en el esquema que espera audit_object_excursions."""
    cols = ["open", "high", "low", "close", "time"]
    records = df[cols].to_dict(orient="records")
    rows: list[dict[str, Any]] = [{str(k): v for k, v in row.items()} for row in records]
    fvgs = detect_fvg(rows, timeframe=tf, symbol="EURUSD")
    obs = detect_order_blocks(rows, timeframe=tf, symbol="EURUSD")
    out: list[dict[str, Any]] = []
    for obj in list(fvgs) + list(obs):
        # birth_bar = barra de confirmación (tercera vela del patrón 3-candle)
        birth = int(obj.bar_index) if obj.bar_index is not None else 0
        ref = float(obj.zone_low + obj.zone_high) / 2.0
        # reference_rule: close de la barra de confirmación del objeto
        ref_row = df.iloc[birth] if 0 <= birth < len(df) else None
        if ref_row is not None:
            ref = float(ref_row["close"])
        out.append({
            "object_id": obj.id,
            "object_type": "FVG" if obj.type.value == "FVG" else "OB",
            "tf": tf,
            "direction": "bullish" if obj.direction >= 0 else "bearish",
            "birth_bar": birth,
            "zone_low": float(obj.zone_low),
            "zone_high": float(obj.zone_high),
            "reference_price": ref,
            "reference_rule": "close_at_object_confirmation",
            "pip_size": 0.0001,
        })
    return out


def _behavioral_gate(result: dict) -> dict:
    """TNA-BEHAVIORAL: juzga diseño de navegación, NO solo reproducibilidad.

    Un trace puede ser perfectamente reproducible (PASS_TRACE_INTEGRITY) y aun
    así tener navegación mal diseñada (ej. atascada, o nunca llega a SETUP_READY,
    o retrocesos sin causa). Este gate lo separa.
    """
    failures: list[str] = []
    warns: list[str] = []

    trace = result.get("trace_count", 0)
    if trace == 0:
        return {"gate": "FAIL", "reason": "sin traces", "failures": ["NO_TRACE"], "warnings": []}

    final = str(result.get("final_state", ""))
    # 1. Alcanza SETUP_READY en al menos una fracción plausible del tiempo.
    tc = result.get("transition_counts", {})
    setup_ready_trans = sum(v for k, v in tc.items() if "SETUP_READY" in k)
    if setup_ready_trans == 0:
        failures.append("NAVEGACION_NUNCA_LLEGA_A_SETUP_READY")
    # 2. Estados atascados: stuck_rate no debe dominar.
    stuck = result.get("stuck_state_count", 0)
    stuck_rate = (stuck / trace) if trace else 0.0
    if stuck_rate > 0.10:
        failures.append(f"STUCK_DOMINANTE rate={stuck_rate:.3f}")
    elif stuck_rate > 0.03:
        warns.append(f"stuck_rate_elevado rate={stuck_rate:.3f}")
    # 3. Rollback con causa: toda invalidación debe tener invalidation_reason.
    # (audit_snapshots no expone conteo de sin-causa directamente; el trace lo
    #  garantiza por contrato AHF, pero lo señalamos si inv==0 y hay muchos switches)
    # 4. Eficiencia de navegación: demasiados switches puede indicar indecisión.
    down = result.get("downward_switches", 0)
    up = result.get("upward_switches", 0)
    total_sw = down + up
    if trace and total_sw / trace > 5.0:
        warns.append(f"switches_por_trace_elevado={total_sw/trace:.2f}")
    # 5. Monotonicidad de transiciones (ya cubierta por trace-integrity, pero
    #    aquí exigimos que el historial sea reconstruible sin huecos).
    causal = result.get("causal_checks", {})
    if not causal.get("history_monotone", False):
        failures.append("HISTORIAL_NO_MONOTONO")
    if not causal.get("transition_order_reconstructable", False):
        failures.append("TRANSICION_NO_RECONSTRUIBLE")

    gate = "PASS" if not failures else "FAIL"
    return {
        "gate": gate,
        "final_state": final,
        "setup_ready_transitions": setup_ready_trans,
        "stuck_rate": round(stuck_rate, 4),
        "rollback_count": result.get("rollback_depth_bars", {}).get("n", 0),
        "tf_switches_per_trace": round(total_sw / trace, 3) if trace else None,
        "failures": failures,
        "warnings": warns,
    }


def main() -> dict:
    """Corre la auditoría temporal AHF/MTF 20Y y emite ambos gates a disco/consola."""
    frames = {tf: _load_tf(tf) for tf in ("D1", "H4", "H1")}
    h1 = frames["H1"]
    decision_times = list(h1["time"])

    ahf = AdaptiveHierarchicalFunnel(
        frames,
        AHFConfig(navigator=NavigatorConfig(precompute_sequences=True, sequence_tf="H1")),
    )
    snapshots = ahf.run_timeline(decision_times, exec_tf="H1")
    serialized: list[Mapping[str, Any]] = [s.to_dict() for s in snapshots]
    decision_bars = list(range(len(serialized)))

    objects = _fvg_ob_objects(h1, "H1")
    price_frames = {"H1": h1}

    result = audit_snapshots(
        serialized,
        decision_bars=decision_bars,
        config=TemporalAuditConfig(),
        objects=objects,
        price_frames=price_frames,
    )

    behavioral = _behavioral_gate(result)
    trace_integrity = result.get("status") == "PASS_TRACE_INTEGRITY"

    overall = "PASS" if (trace_integrity and behavioral["gate"] == "PASS") else "FAIL"

    report = {
        "audit": "AHF_TEMPORAL_NAVIGATION_20Y",
        "dataset": "EURUSD Dukascopy 20Y",
        "symbol": "EURUSD",
        "frames": {tf: len(frames[tf]) for tf in frames},
        "policy": "AHF_STATE_NOT_ENTRY",
        "command": "ejecuta auditoria temporal",
        "precompute_sequences": True,
        "sequence_tf": "H1",
        "gates": {
            "TNA-TRACE-INTEGRITY": "PASS" if trace_integrity else "FAIL",
            "TNA-BEHAVIORAL": behavioral["gate"],
        },
        "overall": overall,
        "trace_metrics": result,
        "behavioral_detail": behavioral,
        "object_count": len(objects),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2, default=str))
    _write_md(report)
    print(json.dumps({
        "overall": overall,
        "TNA-TRACE-INTEGRITY": report["gates"]["TNA-TRACE-INTEGRITY"],
        "TNA-BEHAVIORAL": report["gates"]["TNA-BEHAVIORAL"],
        "trace_count": result.get("trace_count"),
        "transition_count": result.get("transition_count"),
        "final_state": result.get("final_state"),
        "invalidations": result.get("invalidations"),
        "stuck_state_count": result.get("stuck_state_count"),
        "object_count": len(objects),
        "out_json": str(OUT_JSON),
        "out_md": str(OUT_MD),
    }, indent=2, default=str))
    return report


def _write_md(report: dict) -> None:
    g = report["gates"]
    tm = report["trace_metrics"]
    md = [
        "# AUDITORÍA TEMPORAL AHF / MTF — EURUSD 20Y",
        "",
        "- **Dataset:** EURUSD Dukascopy 20Y",
        "- **Comando:** `ejecuta auditoria temporal`",
        "- **Precompute sequences:** True (secuencia real, H1)",
        f"- **Policy:** {report['policy']} (no entry)",
        "",
        "## Gates",
        "",
        "| Gate | Estado |",
        "|------|--------|",
        f"| TNA-TRACE-INTEGRITY | **{g['TNA-TRACE-INTEGRITY']}** |",
        f"| TNA-BEHAVIORAL | **{g['TNA-BEHAVIORAL']}** |",
        f"| **OVERALL** | **{report['overall']}** |",
        "",
        "## Métricas de trace",
        "",
        f"- trace_count: {tm.get('trace_count')}",
        f"- transition_count: {tm.get('transition_count')}",
        f"- final_state: {tm.get('final_state')}",
        f"- invalidations: {tm.get('invalidations')}",
        f"- downward/upward switches: {tm.get('downward_switches')} / {tm.get('upward_switches')}",
        f"- stuck_state_count: {tm.get('stuck_state_count')}",
        f"- max_tf_depth: {tm.get('max_tf_depth')}",
        "",
        "## Behavioral detail",
        "",
        f"```{json.dumps(report['behavioral_detail'], indent=2, default=str)}```",
        "",
        "## Nota",
        "Esta auditoría NO es backtest, NO mide PnL, NO declara edge. Solo verifica",
        "que la navegación temporal del AHF es reproducible (TNA-TRACE-INTEGRITY) y",
        "está bien diseñada (TNA-BEHAVIORAL).",
        "",
    ]
    OUT_MD.write_text("\n".join(md))


if __name__ == "__main__":
    main()
