#!/usr/bin/env python3
"""Build M15 AI shadow funnel and diagnostic backtest v1.

This is a diagnostic backtest, not an economic or execution backtest. It
compares the TensorFlow outcome model alone against the selected failure-risk
shadow fusion, using immutable local rows and TEST_OOS only as final review.

No MT5, orders, paper/demo trading, dataset download, or production fusion is
performed.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.lab.experiments.evaluate_shadow_fusion_v1 import (
    Candidate,
    IDX_TO_LABEL,
    ROOT,
    apply_candidate,
    load_outcome_predictions,
    load_risk_probs,
    load_rows,
    multiclass_metrics,
    sha256_path,
    split_rows,
)


REPORT_DIR = ROOT / "reports/audits/experiments/ai"
RISK_RUN = ROOT / "data/ml/tensorflow/failure_risk_v1"
SHADOW_FUSION = RISK_RUN / "shadow_fusion_v1.json"
OUT_JSON = REPORT_DIR / "m15_ai_shadow_funnel_backtest_v1.json"
REPORT_MD = REPORT_DIR / "m15_ai_shadow_funnel_backtest_v1.md"
FUNNEL_PNG = REPORT_DIR / "m15_ai_shadow_funnel_v1.png"
BACKTEST_PNG = REPORT_DIR / "m15_ai_shadow_backtest_v1.png"
CONFUSION_PNG = REPORT_DIR / "m15_ai_shadow_confusion_v1.png"

LONDON_NY_START_UTC = 7
LONDON_NY_END_UTC = 16


def _event_hour_utc(row: dict[str, Any]) -> int:
    text = str(row.get("event_time", ""))
    if len(text) < 13:
        return -1
    try:
        return int(text[11:13])
    except ValueError:
        return -1


def _in_london_ny_window(row: dict[str, Any]) -> bool:
    hour = _event_hour_utc(row)
    return LONDON_NY_START_UTC <= hour <= LONDON_NY_END_UTC


def _align_split(split: str, outcome: dict[str, Any], risk: dict[str, Any], rows_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    risk_by_id = {event_id: i for i, event_id in enumerate(risk["event_ids"])}
    risk_idx = [risk_by_id[event_id] for event_id in outcome["event_ids"]]
    rows = [rows_by_id[event_id] for event_id in outcome["event_ids"]]
    return {
        "split": split,
        "event_ids": list(outcome["event_ids"]),
        "rows": rows,
        "y": np.asarray(outcome["y"], dtype=int),
        "base_probs": np.asarray(outcome["probs"], dtype=float),
        "risk": {
            "raw": np.asarray(risk["raw"], dtype=float)[risk_idx],
            "platt": np.asarray(risk["platt"], dtype=float)[risk_idx],
        },
    }


def _selection_table(y: np.ndarray, probs: np.ndarray) -> dict[str, Any]:
    pred = np.argmax(probs, axis=1)
    selected = pred != 2
    failures = y == 2
    selected_count = int(selected.sum())
    avoided_count = int((~selected).sum())
    selected_failures = int((selected & failures).sum())
    avoided_failures = int((~selected & failures).sum())
    selected_non_failures = int((selected & ~failures).sum())
    non_failures = int((~failures).sum())
    return {
        "total": int(len(y)),
        "selected": selected_count,
        "avoided": avoided_count,
        "selected_failures": selected_failures,
        "avoided_failures": avoided_failures,
        "selected_non_failures": selected_non_failures,
        "coverage": float(selected_count / len(y)) if len(y) else 0.0,
        "failure_rate_selected": float(selected_failures / selected_count) if selected_count else 0.0,
        "failure_avoidance_recall": float(avoided_failures / int(failures.sum())) if int(failures.sum()) else 0.0,
        "non_failure_capture": float(selected_non_failures / non_failures) if non_failures else 0.0,
    }


def _subset_payload(aligned: dict[str, Any], mask: np.ndarray) -> dict[str, Any]:
    return {
        "event_ids": [event_id for event_id, keep in zip(aligned["event_ids"], mask) if bool(keep)],
        "rows": [row for row, keep in zip(aligned["rows"], mask) if bool(keep)],
        "y": aligned["y"][mask],
        "base_probs": aligned["base_probs"][mask],
        "risk": {key: values[mask] for key, values in aligned["risk"].items()},
    }


def _metrics_block(aligned: dict[str, Any], candidate: Candidate) -> dict[str, Any]:
    fused = apply_candidate(candidate, aligned["base_probs"], aligned["risk"][candidate.risk_source])
    return {
        "base_multiclass": multiclass_metrics(aligned["y"], aligned["base_probs"]),
        "ai_shadow_multiclass": multiclass_metrics(aligned["y"], fused),
        "base_selection": _selection_table(aligned["y"], aligned["base_probs"]),
        "ai_shadow_selection": _selection_table(aligned["y"], fused),
        "confusion_base": _confusion_labels(aligned["y"], aligned["base_probs"]),
        "confusion_ai_shadow": _confusion_labels(aligned["y"], fused),
    }


def _confusion_labels(y: np.ndarray, probs: np.ndarray) -> dict[str, dict[str, int]]:
    pred = np.argmax(probs, axis=1)
    out = {label: {inner: 0 for inner in IDX_TO_LABEL.values()} for label in IDX_TO_LABEL.values()}
    for truth, guessed in zip(y, pred):
        out[IDX_TO_LABEL[int(truth)]][IDX_TO_LABEL[int(guessed)]] += 1
    return out


def _funnel_counts(aligned: dict[str, Any], candidate: Candidate) -> dict[str, int]:
    fused = apply_candidate(candidate, aligned["base_probs"], aligned["risk"][candidate.risk_source])
    base_selected = np.argmax(aligned["base_probs"], axis=1) != 2
    ai_selected = np.argmax(fused, axis=1) != 2
    window = np.asarray([_in_london_ny_window(row) for row in aligned["rows"]], dtype=bool)
    y = aligned["y"]
    return {
        "source_rows": int(len(y)),
        "london_ny_window_proxy": int(window.sum()),
        "motor_base_selected": int(base_selected.sum()),
        "ai_shadow_selected": int(ai_selected.sum()),
        "ai_shadow_selected_london_ny": int((ai_selected & window).sum()),
        "ai_shadow_selected_non_failure": int((ai_selected & (y != 2)).sum()),
    }


def _delta(a: float, b: float) -> float:
    return float(b - a)


def _plot_funnel(counts: dict[str, int]) -> None:
    labels = [
        "TEST_OOS rows",
        "London-NY proxy",
        "Motor selects",
        "AI shadow selects",
        "AI selects in window",
        "AI selected non-failure",
    ]
    values = [
        counts["source_rows"],
        counts["london_ny_window_proxy"],
        counts["motor_base_selected"],
        counts["ai_shadow_selected"],
        counts["ai_shadow_selected_london_ny"],
        counts["ai_shadow_selected_non_failure"],
    ]
    colors = ["#4c78a8", "#72b7b2", "#f58518", "#54a24b", "#b279a2", "#eeca3b"]
    fig, ax = plt.subplots(figsize=(11, 6))
    y = np.arange(len(labels))
    ax.barh(y, values, color=colors)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel("Count")
    ax.set_title("M15 AI Shadow Funnel v1")
    ax.grid(axis="x", alpha=0.25)
    for i, value in enumerate(values):
        ax.text(value + max(values) * 0.01, i, str(value), va="center", fontsize=9)
    fig.text(0.5, 0.01, "Diagnostic funnel only. London-NY proxy = UTC hour 07:00-16:59. can_trade=false.", ha="center", fontsize=8)
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(FUNNEL_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_backtest(metrics: dict[str, Any], window_metrics: dict[str, Any]) -> None:
    labels = ["failure_avoidance_recall", "failure_rate_selected", "non_failure_capture", "coverage"]
    pretty = ["Avoid failures", "Failure rate", "Good setup capture", "Coverage"]
    base = [metrics["base_selection"][key] for key in labels]
    ai = [metrics["ai_shadow_selection"][key] for key in labels]
    win_base = [window_metrics["base_selection"][key] for key in labels]
    win_ai = [window_metrics["ai_shadow_selection"][key] for key in labels]
    x = np.arange(len(labels))
    width = 0.2
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(x - 1.5 * width, base, width, label="OOS motor", color="#4c78a8")
    ax.bar(x - 0.5 * width, ai, width, label="OOS AI shadow", color="#54a24b")
    ax.bar(x + 0.5 * width, win_base, width, label="Window motor", color="#f58518")
    ax.bar(x + 1.5 * width, win_ai, width, label="Window AI shadow", color="#b279a2")
    ax.set_xticks(x)
    ax.set_xticklabels(pretty, rotation=10)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Rate")
    ax.set_title("Diagnostic Backtest: Motor vs AI Shadow")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(ncols=2)
    fig.text(0.5, 0.01, "Selection = predicted class is not failure. This is not an economic PnL backtest.", ha="center", fontsize=8)
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(BACKTEST_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_confusion(confusion: dict[str, dict[str, int]]) -> None:
    labels = list(IDX_TO_LABEL.values())
    matrix = np.asarray([[confusion[t][p] for p in labels] for t in labels], dtype=float)
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(matrix, cmap="Blues")
    ax.set_xticks(np.arange(len(labels)))
    ax.set_yticks(np.arange(len(labels)))
    ax.set_xticklabels(labels)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title("AI Shadow Confusion Matrix - TEST_OOS")
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(j, i, int(matrix[i, j]), ha="center", va="center", color="#111827")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(CONFUSION_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    shadow = json.loads(SHADOW_FUSION.read_text(encoding="utf-8"))
    candidate = Candidate(**shadow["selected"]["candidate"])

    rows_all = load_rows()
    rows_split = split_rows(rows_all)
    rows_by_id = {row["event_id"]: row for row in rows_all}
    outcome = load_outcome_predictions()
    risk = load_risk_probs()
    aligned = {
        split: _align_split(split, outcome[split], risk[split], rows_by_id)
        for split in ["VALIDATION", "TEST_OOS"]
    }
    test = aligned["TEST_OOS"]
    window_mask = np.asarray([_in_london_ny_window(row) for row in test["rows"]], dtype=bool)
    window = _subset_payload(test, window_mask)

    metrics = _metrics_block(test, candidate)
    window_metrics = _metrics_block(window, candidate)
    funnel_counts = _funnel_counts(test, candidate)

    base_sel = metrics["base_selection"]
    ai_sel = metrics["ai_shadow_selection"]
    final_status = "REVIEW_DIAGNOSTIC_BACKTEST"
    if (
        ai_sel["failure_avoidance_recall"] > base_sel["failure_avoidance_recall"]
        and ai_sel["failure_rate_selected"] <= base_sel["failure_rate_selected"]
        and ai_sel["coverage"] >= 0.10
        and funnel_counts["ai_shadow_selected_london_ny"] >= 1
    ):
        final_status = "PASS_DIAGNOSTIC_SHADOW_FUNNEL"

    payload = {
        "schema_version": "M15_AI_SHADOW_FUNNEL_BACKTEST_V1",
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": final_status,
        "can_trade": False,
        "entry_authorized": False,
        "economic_backtest": False,
        "diagnostic_only": True,
        "selection_rule": "selected when predicted class is not failure",
        "london_ny_proxy": {
            "timezone": "UTC",
            "start_hour": LONDON_NY_START_UTC,
            "end_hour": LONDON_NY_END_UTC,
            "note": "Proxy window for diagnostic filtering; not broker-session certification.",
        },
        "source_artifacts": {
            "shadow_fusion": str(SHADOW_FUSION.relative_to(ROOT)),
            "shadow_fusion_sha256": sha256_path(SHADOW_FUSION),
            "tf_outcome_model": shadow["tf_outcome_model"],
            "failure_risk_predictions": shadow["risk_predictions"],
        },
        "candidate": asdict(candidate),
        "row_counts": {
            "TRAIN": len(rows_split["TRAIN"]),
            "VALIDATION": len(rows_split["VALIDATION"]),
            "TEST_OOS": len(rows_split["TEST_OOS"]),
        },
        "funnel_counts_test_oos": funnel_counts,
        "test_oos": metrics,
        "test_oos_london_ny_proxy": window_metrics,
        "deltas": {
            "failure_avoidance_recall": _delta(base_sel["failure_avoidance_recall"], ai_sel["failure_avoidance_recall"]),
            "failure_rate_selected": _delta(base_sel["failure_rate_selected"], ai_sel["failure_rate_selected"]),
            "coverage": _delta(base_sel["coverage"], ai_sel["coverage"]),
            "failure_recall_multiclass": _delta(metrics["base_multiclass"]["failure_recall"], metrics["ai_shadow_multiclass"]["failure_recall"]),
            "failure_f1_multiclass": _delta(metrics["base_multiclass"]["failure_f1"], metrics["ai_shadow_multiclass"]["failure_f1"]),
        },
        "artifacts": {
            "report": str(REPORT_MD.relative_to(ROOT)),
            "funnel_png": str(FUNNEL_PNG.relative_to(ROOT)),
            "backtest_png": str(BACKTEST_PNG.relative_to(ROOT)),
            "confusion_png": str(CONFUSION_PNG.relative_to(ROOT)),
        },
        "limitations": [
            "Diagnostic class/outcome backtest only; no spread, slippage, commission, fill, SL/TP, or PnL.",
            "London-NY is a UTC-hour proxy, not a live broker session certification.",
            "AI remains shadow-only and does not modify the engine.",
        ],
    }

    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _plot_funnel(funnel_counts)
    _plot_backtest(metrics, window_metrics)
    _plot_confusion(metrics["confusion_ai_shadow"])
    _write_report(payload)
    print(json.dumps({
        "status": final_status,
        "funnel_counts_test_oos": funnel_counts,
        "base_selection": metrics["base_selection"],
        "ai_shadow_selection": metrics["ai_shadow_selection"],
        "window_ai_shadow_selection": window_metrics["ai_shadow_selection"],
        "artifacts": payload["artifacts"],
    }, indent=2, sort_keys=True))
    return 0


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _write_report(payload: dict[str, Any]) -> None:
    base = payload["test_oos"]["base_selection"]
    ai = payload["test_oos"]["ai_shadow_selection"]
    win_ai = payload["test_oos_london_ny_proxy"]["ai_shadow_selection"]
    report = [
        "# M15 AI Shadow Funnel + Diagnostic Backtest v1",
        "",
        "**Fecha:** 2026-09-15",
        f"**Estado:** `{payload['status']}`",
        "**Politica:** `can_trade=false`, `entry_authorized=false`, `shadow_mode=true`",
        "",
        "## Resumen simple",
        "",
        "Se hizo el embudo y un backtest diagnostico con las neuronas en sombra. En palabras simples: el motor propone candidatos, la IA decide si los dejaria pasar o los rechazaria, y luego medimos contra el resultado historico.",
        "",
        "Esto todavia no es backtest economico de dinero: no incluye spread, slippage, comision, fill, SL/TP ni PnL.",
        "",
        "## Imagenes",
        "",
        f"![Funnel M15 AI Shadow]({FUNNEL_PNG.resolve().as_posix()})",
        "",
        f"![Backtest diagnostico motor vs IA]({BACKTEST_PNG.resolve().as_posix()})",
        "",
        f"![Matriz de confusion IA sombra]({CONFUSION_PNG.resolve().as_posix()})",
        "",
        "## Candidato neuronal usado",
        "",
        "```json",
        json.dumps(payload["candidate"], indent=2),
        "```",
        "",
        "## Resultado TEST_OOS",
        "",
        "| Metrica | Motor solo | Motor + IA sombra |",
        "| --- | ---: | ---: |",
        f"| Cobertura seleccionada | {_pct(base['coverage'])} | {_pct(ai['coverage'])} |",
        f"| Tasa de fallos entre seleccionados | {_pct(base['failure_rate_selected'])} | {_pct(ai['failure_rate_selected'])} |",
        f"| Fallos evitados | {_pct(base['failure_avoidance_recall'])} | {_pct(ai['failure_avoidance_recall'])} |",
        f"| Captura de no-fallos | {_pct(base['non_failure_capture'])} | {_pct(ai['non_failure_capture'])} |",
        "",
        "## Ventana Londres-NY proxy",
        "",
        f"Se uso una ventana diagnostica UTC `{LONDON_NY_START_UTC}:00-{LONDON_NY_END_UTC}:59`. En TEST_OOS la IA sombra selecciono `{win_ai['selected']}` candidatos dentro de esa ventana y capturo `{win_ai['selected_non_failures']}` no-fallos.",
        "",
        "## Lectura tecnica",
        "",
        "La IA sombra mejora la deteccion de la clase `failure` frente al motor base en el dictamen de fusion previo. En este funnel/backtest diagnostico se mide el efecto como filtro: si predice `failure`, el candidato se evita; si predice `continuation` o `reversal`, el candidato pasa.",
        "",
        "## Dictamen",
        "",
    ]
    if payload["status"] == "PASS_DIAGNOSTIC_SHADOW_FUNNEL":
        report.append("El funnel diagnostico pasa minimos: la IA evita mas fallos, no sube la tasa de fallos entre seleccionados, mantiene cobertura minima y deja al menos un candidato en la ventana Londres-NY proxy.")
    else:
        report.append("El funnel queda en REVIEW: hay evidencia util, pero no alcanza para declarar mejora diagnostica estable bajo los minimos definidos.")
    report.extend([
        "",
        "## Limites",
        "",
        "- No hay permiso de trade.",
        "- No hay backtest economico todavia.",
        "- No se activo MT5, DEMO ni live.",
        "- La IA no modifica el motor; solo filtra en sombra.",
        "",
        "## Siguiente paso",
        "",
        "Como el estado es REVIEW, el siguiente paso no es activar backtest economico todavia. Primero se debe redisenar el filtro con TRAIN/VALIDATION para bajar la tasa de fallos seleccionados sin destruir la captura de no-fallos. Solo despues de un nuevo candidato congelado se vuelve a evaluar TEST_OOS.",
        "",
    ])
    REPORT_MD.write_text("\n".join(report), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
