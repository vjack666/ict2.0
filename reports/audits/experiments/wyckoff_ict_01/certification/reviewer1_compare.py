"""REVIEWSER 1 — Comparacion determinista de la reproduccion limpia.

Lee el JSON regenerado en el worktree limpio (basado en e9c9be9) y el JSON
auditado commiteado en cdf45f1, y los diferencia campo a campo. No re-corre
el pipeline pesado; solo compara los artefactos.

Uso:
  python reviewer1_compare.py <ruta_json_regenerado> <ruta_json_auditable>

Salida: reviewer1_comparison.json
"""
from __future__ import annotations
import json, sys
from pathlib import Path

def _counts_flat(c: dict) -> dict:
    out = {}
    for tf, d in c.items():
        out[f"{tf}.n_observations_after_dedup"] = d["n_observations_after_dedup"]
        for cell, flags in d.get("cells_primary", {}).items():
            for fl, n in flags.items():
                out[f"{tf}.cells.{cell}.{fl}"] = n
    return out

def main() -> None:
    regen = Path(sys.argv[1])
    audit = Path(sys.argv[2])
    a = json.loads(regen.read_text(encoding="utf-8"))
    b = json.loads(audit.read_text(encoding="utf-8"))

    fa, fb = _counts_flat(a["counts"]), _counts_flat(b["counts"])
    keys = sorted(set(fa) | set(fb))
    diffs = {k: {"regen": fa.get(k), "audit": fb.get(k)} for k in keys if fa.get(k) != fb.get(k)}

    # generator_commit debe coincidir con e9c9be9 en la regeneracion
    gen_ok = a.get("generator_commit", "").startswith("e9c9be9")
    # worktree state de la regen (puede ser CLEAN o DIRTY; lo reportamos)
    wt = a.get("generator_worktree")

    identical = (len(diffs) == 0) and gen_ok
    report = {
        "reviewer": "REVIEWER_1_INDEPENDENT_REPRODUCTION",
        "regen_generator_commit": a.get("generator_commit"),
        "audit_generator_commit": b.get("generator_commit"),
        "regen_worktree_state": wt,
        "counts_identical": identical,
        "n_differing_fields": len(diffs),
        "diffs": diffs,
        "H1_total_regen": a["counts"]["H1"]["n_observations_after_dedup"],
        "H1_total_audit": b["counts"]["H1"]["n_observations_after_dedup"],
        "verdict": "CERTIFIED_FEASIBILITY_FAIL_INSUFFICIENT_N" if identical else "REPRODUCTION_MISMATCH",
    }
    out = regen.parent / "reviewer1_comparison.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps(report, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
