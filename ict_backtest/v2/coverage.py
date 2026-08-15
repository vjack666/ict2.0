"""Coverage Matrix C0x + automatic Coverage Report (BACKTEST_V2_SPEC §8)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

CapabilityStatus = Literal["implemented", "partial", "missing", "n/a_model"]

# required_for_full_thesis: counted in coverage_pct denominator when status != n/a_model
_CAPABILITIES: list[dict[str, Any]] = [
    {"id": "C01", "name": "Bias HTF (>=1 TF)", "required": True},
    {"id": "C02", "name": "D1 context in decision", "required": True},
    {"id": "C03", "name": "Dealing range + Premium/Discount", "required": True},
    {"id": "C04", "name": "H1 zone validation", "required": True},
    {"id": "C05", "name": "POI anchored to narrative", "required": True},
    {"id": "C06", "name": "Multi-TF POI stacking", "required": True},
    {"id": "C07", "name": "Sweep→BOS→mitigation sequence", "required": True},
    {"id": "C08", "name": "Killzone", "required": True},
    {"id": "C09", "name": "Structural SL on exec TF", "required": True},
    {"id": "C10", "name": "Nearest-liquidity TP", "required": True},
    {"id": "C11", "name": "Min RR 1:3 quality gate", "required": True},
    {"id": "C12", "name": "M5 confirmation", "required": False},  # model-conditional
    {"id": "C13", "name": "M1 entry", "required": False},
    {"id": "C14", "name": "Narrative invalidation by event", "required": True},
    {"id": "C15", "name": "Trade management (BE/partials)", "required": True},
    {"id": "C16", "name": "Realistic fill", "required": True},
    {"id": "C17", "name": "Real costs", "required": True},
    {"id": "C18", "name": "HTF closed-only clock", "required": True},
    {"id": "C19", "name": "Metrics labeled by coverage", "required": True},
    {"id": "C20", "name": "Strategy/Sim/Plan separation", "required": True},
]


def default_registry(coverage_mode: str = "legacy_subset") -> dict[str, CapabilityStatus]:
    """Implementation status — single source for Coverage Report.

    Update when phases land.
    """
    if coverage_mode == "legacy_subset":
        return {
            "C01": "implemented",
            "C02": "missing",
            "C03": "missing",
            "C04": "missing",
            "C05": "missing",
            "C06": "missing",
            "C07": "implemented",
            "C08": "implemented",
            "C09": "partial",
            "C10": "partial",
            "C11": "partial",
            "C12": "n/a_model",
            "C13": "n/a_model",
            "C14": "partial",
            "C15": "missing",
            "C16": "implemented",
            "C17": "implemented",
            "C18": "implemented",
            "C19": "implemented",
            "C20": "partial",
        }
    if coverage_mode in ("v2_partial", "v2_full", "mtf_intraday"):
        # mtf_intraday path: D1→H4→H1→M15 + nearest TP + Plan/Sim split
        return {
            "C01": "implemented",
            "C02": "implemented",  # D1 gate
            "C03": "implemented",  # P/D dealing range
            "C04": "implemented",  # H1 oppose filter
            "C05": "partial",  # PD side as soft POI proxy; full POI narrative later
            "C06": "missing",
            "C07": "implemented",
            "C08": "implemented",
            "C09": "implemented",
            "C10": "implemented",  # nearest swing TP
            "C11": "implemented",  # min RR 3
            "C12": "n/a_model",  # intraday exec M15
            "C13": "n/a_model",
            "C14": "partial",
            "C15": "partial",  # max_hold elevated default 40
            "C16": "implemented",
            "C17": "implemented",
            "C18": "implemented",
            "C19": "implemented",
            "C20": "implemented",
        }
    return {c["id"]: "missing" for c in _CAPABILITIES}


@dataclass
class CoverageReport:
    model_id: str
    coverage_mode: str
    required: int
    implemented: int
    partial: int
    missing: int
    coverage_pct: float
    per_capability: dict[str, CapabilityStatus] = field(default_factory=dict)
    verdict: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def format_human(self) -> str:
        lines = [
            "Coverage Report",
            "─" * 40,
            f"model_id:       {self.model_id}",
            f"coverage_mode:  {self.coverage_mode}",
            f"required:       {self.required}",
            f"implemented:    {self.implemented}",
            f"partial:        {self.partial}",
            f"missing:        {self.missing}",
            f"coverage_pct:   {self.coverage_pct:.1f}%",
            f"verdict:        {self.verdict}",
            "",
            "per_capability:",
        ]
        for cid, st in sorted(self.per_capability.items()):
            name = next((c["name"] for c in _CAPABILITIES if c["id"] == cid), "")
            lines.append(f"  {cid}: {st:12s}  {name}")
        return "\n".join(lines)

    def save_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


def build_coverage_report(
    model_id: str,
    coverage_mode: str,
    registry: dict[str, CapabilityStatus] | None = None,
) -> CoverageReport:
    reg = registry if registry is not None else default_registry(coverage_mode)
    # Ensure all known ids present
    for c in _CAPABILITIES:
        reg.setdefault(c["id"], "missing")

    required_ids = []
    for c in _CAPABILITIES:
        if not c["required"]:
            continue
        st = reg.get(c["id"], "missing")
        if st == "n/a_model":
            continue
        required_ids.append(c["id"])

    implemented = partial = missing = 0
    for cid in required_ids:
        st = reg[cid]
        if st == "implemented":
            implemented += 1
        elif st == "partial":
            partial += 1
        else:
            missing += 1

    n_req = len(required_ids)
    coverage_pct = 0.0 if n_req == 0 else 100.0 * (implemented + 0.5 * partial) / n_req

    if coverage_mode != "v2_full" or coverage_pct < 85.0:
        verdict = (
            "resultado de implementacion parcial — "
            "NO interpretar como edge de la tesis ICT completa"
        )
    else:
        verdict = "candidato a edge de estrategia objetivo (sujeto a OOS/WF)"

    return CoverageReport(
        model_id=model_id,
        coverage_mode=coverage_mode,
        required=n_req,
        implemented=implemented,
        partial=partial,
        missing=missing,
        coverage_pct=round(coverage_pct, 1),
        per_capability=dict(reg),
        verdict=verdict,
    )
