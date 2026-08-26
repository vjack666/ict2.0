"""REVIEWSER 3 — Auditoria ESTADISTICA (independiente).

Confirma 3 puntos de la ORDEN CEO sobre el JSON auditable en cdf45f1
(reports/audits/experiments/wyckoff_ict_01/feasibility_counts_v2.json):

 R3.1  Potencia y requisito ~389 por grupo (recomputa el n para MDE 10pp,
       potencia 0.80, alfa 0.05 dos colas, prueba de dos proporciones).
 R3.2  H1 TOTAL = 515 < 778 (778 = 2 x 389, el total minimo para UN diseno
       de 2 grupos a n>=389 por grupo).
 R3.3  El fallo de factibilidad permanece AUN SI cambia la distribucion entre
       celdas: con total=515 < 778 es IMPOSIBLE llenar siquiera un par de
       celdas a 389 cada una, cualquiera sea la redistribucion. Ademas, cada
       celda primaria individual ya esta muy por debajo de 389.

Salida: .hermes-cert/reviewer3_statistical_audit.json
"""
from __future__ import annotations
import json, math, sys
from pathlib import Path
from scipy.stats import norm

REPO = Path(__file__).resolve().parents[1]
AUDITED_JSON = REPO / "reports" / "audits" / "experiments" / "wyckoff_ict_01" / "feasibility_counts_v2.json"

j = json.loads(AUDITED_JSON.read_text(encoding="utf-8"))
N_REQUIRED = j["n_required_per_group"]  # 389
r = {}

# ---------- R3.1 recompute required n per group ----------
alpha = 0.05
power = 0.80
p1 = 0.50
p2 = 0.60  # MDE 10pp respecto a p1
za = norm.ppf(1 - alpha / 2)
zb = norm.ppf(power)
n_per_group = (za + zb) ** 2 * (p1 * (1 - p1) + p2 * (1 - p2)) / (p2 - p1) ** 2
# continuidad (correction de Fleiss): +1/(p2-p1) approx; lo reportamos sin y con.
n_continuity = n_per_group + 1.0 / (p2 - p1)
r["R3.1"] = {
    "alpha": alpha,
    "power": power,
    "p1": p1,
    "p2": p2,
    "mde_pp": int(round((p2 - p1) * 100)),
    "z_alpha_2": round(float(za), 4),
    "z_beta": round(float(zb), 4),
    "n_per_group_computed": round(float(n_per_group), 1),
    "n_per_group_with_cc": round(float(n_continuity), 1),
    "n_required_in_json": N_REQUIRED,
    "match": bool(abs(n_per_group - N_REQUIRED) <= 10 or abs(n_continuity - N_REQUIRED) <= 10),
    "note": "389 del prerregistro es congruente con MDE 10pp / potencia 0.80 / alfa 0.05 (sin cc ~385; con cc ~395).",
}

# ---------- R3.2 H1 TOTAL vs 778 ----------
h1 = j["counts"]["H1"]["n_observations_after_dedup"]
h4 = j["counts"]["H4"]["n_observations_after_dedup"]
d1 = j["counts"]["D1"]["n_observations_after_dedup"]
min_total_for_one_2group = 2 * N_REQUIRED  # 778
r["R3.2"] = {
    "H1_total": h1,
    "H4_total": h4,
    "D1_total": d1,
    "n_required_per_group": N_REQUIRED,
    "min_total_for_one_2group_design": min_total_for_one_2group,
    "H1_lt_778": bool(h1 < min_total_for_one_2group),
    "note": f"H1 TOTAL={h1} < {min_total_for_one_2group}; ningun TF alcanza el total minimo para un par de grupos a 389.",
}

# ---------- R3.3 invarianza a redistribucion de celdas ----------
# Maximo n alcanzable en una sola celda si concentramos TODAS las obs ahi = h1.
# Para satisfacer DOS celdas a >=389 cada una se requieren >=778 obs totales.
# Como h1=515 < 778, es IMPOSIBLE incluso en la mejor redistribucion.
max_possible_single_cell = h1
can_fill_two_groups = h1 >= 2 * N_REQUIRED
# maxima suma de DOS celdas posibles (a lo sumo todo el total en dos celdas):
max_sum_two_cells = min(h1, 2 * N_REQUIRED)  # nunca llega a 778
# Tambien: cada celda primaria individual vs 389
primary_cells = j["counts"]["H1"]["cells_primary"]
max_individual_cell = max(
    (v.get("NON_CONFLICT", 0) + v.get("CONFLICT", 0)) for v in primary_cells.values()
)
r["R3.3"] = {
    "total_h1": h1,
    "n_required": N_REQUIRED,
    "two_group_minimum_total": 2 * N_REQUIRED,
    "can_fill_two_groups_at_389": bool(can_fill_two_groups),
    "max_single_cell_if_all_concentrated": max_possible_single_cell,
    "max_individual_primary_cell_observed": max_individual_cell,
    "every_cell_below_389": bool(max_individual_cell < N_REQUIRED),
    "invariant_to_redistribution": bool((not can_fill_two_groups) and (max_individual_cell < N_REQUIRED)),
    "note": ("Con total=515<778 es imposible llenar dos celdas a 389 cada una, cualquiera sea la "
             "distribucion. Ademas la celda primaria maxima observada es "
             f"{max_individual_cell} << 389. El fallo es estructural, no un artefacto de distribucion."),
}

overall = "PASS" if (r["R3.1"]["match"] and r["R3.2"]["H1_lt_778"] and r["R3.3"]["invariant_to_redistribution"]) else "FAIL"
r["overall"] = overall

out = REPO / ".hermes-cert" / "reviewer3_statistical_audit.json"
out.write_text(json.dumps(r, indent=2, ensure_ascii=False))
print(json.dumps(r, indent=2, ensure_ascii=False))
print(f"\nREVIEWER 3 OVERALL: {overall}")
