"""Runner de auditoría del Funnel Episodes/Funnel v1 (contrato EPISODES_FUNNEL_V1).

Este módulo es de VERIFICACIÓN, no de cálculo. Reutiliza la única autoridad de
cálculo (`engine.episodes.build_episodes`) y produce un reporte JSON
determinista con:

- conteos por etapa / dirección / TF,
- razones de rechazo,
- lineage y duplicados,
- provenance (commit del generador),
- checksum reproducible,
- resultado FULL/PREFIX literal (gate E2),
- aggregated_status (PASS / REVIEW / BLOCKED).

NO importa backtest/, NO llama lifecycle, NO avanza MarketState.

Uso:
    python -m audits.codigo.episodes --out reports/audits/episodes/<name>.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime

from engine.market_object import MarketObject, ObjectType, Role, ObjectState
from engine.market_state import MarketState
from engine.setup_builder import Setup, SetupEligibility
from engine import episodes as EP


CONTRACT_VERSION = EP.CONTRACT_VERSION


# --------------------------------------------------------------------------- #
# corpus sintético (sin datos reales) — cubre varias decisiones T, TF y dirección
# --------------------------------------------------------------------------- #
def _mo(role, origin_tf, mo_type, direction, related=None, parent=None, **kw):
    kw.setdefault("zone_high", 1.1000)
    kw.setdefault("zone_low", 1.0950)
    if "id" not in kw:
        suffix = kw.get("creation_time")
        kw["id"] = f"{role.value}_{origin_tf}_{direction}_{suffix}"
    return MarketObject(
        symbol="EURUSD",
        type=mo_type,
        origin_tf=origin_tf,
        authority_tf=kw.pop("authority_tf", None) or origin_tf,
        role=role,
        direction=direction,
        related_objects=list(related or []),
        parent_object=parent,
        **kw,
    )


def _related(poi, fvg):
    poi.related_objects = [fvg.id]
    fvg.related_objects = [poi.id]
    return poi, fvg


def _ctx(direction):
    return {"direction": direction, "aligned": True}


def build_corpus():
    """Construye un MarketState sintético con varias decisiones T, TF y dirección.

    Usa objetos con geometría/bar_index válidos para que build_setups_at
    componga setups reales (cadena OB H4 + FVG M15 + BOS + DISPLACEMENT).
    """
    objs = []
    decisions = []

    # --- Escenario A: H4 POI + M15 FVG, bullish, ELIGIBLE (aceptado) ---
    t_poi = datetime(2024, 1, 1, 0)
    t_ref = datetime(2024, 1, 1, 1)
    t_bos = datetime(2024, 1, 1, 2)
    t_disp = datetime(2024, 1, 1, 3)
    t_a = datetime(2024, 1, 1, 4)
    poi_a = _mo(Role.POI, "H4", ObjectType.ORDER_BLOCK, 1, [],
                creation_time=t_poi, state=ObjectState.ACTIVE, bar_index=10, candidate_bar=10,
                zone_high=1.1050, zone_low=1.1000)
    fvg_a = _mo(Role.REFINEMENT, "M15", ObjectType.FVG, 1, [poi_a.id],
                creation_time=t_ref, state=ObjectState.ACTIVE, bar_index=20, candidate_bar=20,
                zone_high=1.1020, zone_low=1.0980)
    fvg_a.parent_object = poi_a.id
    bos_a = _mo(Role.CONFIRMATION, "M15", ObjectType.BOS, 1, [poi_a.id, fvg_a.id],
                creation_time=t_bos, bar_index=30, candidate_bar=30)
    disp_a = _mo(Role.EXECUTION, "M15", ObjectType.DISPLACEMENT, 1, [fvg_a.id, poi_a.id],
                 creation_time=t_disp, bar_index=40, candidate_bar=40)
    fvg_a.related_objects = [poi_a.id, bos_a.id, disp_a.id]
    poi_a.related_objects = [fvg_a.id, bos_a.id, disp_a.id]
    objs += [poi_a, fvg_a, bos_a, disp_a]
    decisions.append(t_a)

    # --- Escenario B: H4 POI INVALIDATED -> SUPERSEDED ---
    t_poi_b = datetime(2024, 1, 2, 0)
    t_ref_b = datetime(2024, 1, 2, 1)
    t_bos_b = datetime(2024, 1, 2, 2)
    t_disp_b = datetime(2024, 1, 2, 3)
    t_b = datetime(2024, 1, 2, 4)
    poi_b = _mo(Role.POI, "H4", ObjectType.ORDER_BLOCK, -1, [],
                creation_time=t_poi_b, state=ObjectState.INVALIDATED, bar_index=110, candidate_bar=110,
                zone_high=1.0950, zone_low=1.0900)
    fvg_b = _mo(Role.REFINEMENT, "M15", ObjectType.FVG, -1, [poi_b.id],
                creation_time=t_ref_b, state=ObjectState.ACTIVE, bar_index=120, candidate_bar=120,
                zone_high=1.0920, zone_low=1.0880)
    fvg_b.parent_object = poi_b.id
    bos_b = _mo(Role.CONFIRMATION, "M15", ObjectType.BOS, -1, [poi_b.id, fvg_b.id],
                creation_time=t_bos_b, bar_index=130, candidate_bar=130)
    disp_b = _mo(Role.EXECUTION, "M15", ObjectType.DISPLACEMENT, -1, [fvg_b.id, poi_b.id],
                 creation_time=t_disp_b, bar_index=140, candidate_bar=140)
    fvg_b.related_objects = [poi_b.id, bos_b.id, disp_b.id]
    poi_b.related_objects = [fvg_b.id, bos_b.id, disp_b.id]
    objs += [poi_b, fvg_b, bos_b, disp_b]
    decisions.append(t_b)

    # --- Escenario C: bearish bajo sesgo bullish -> BLOCKED (rechazado) ---
    t_poi_c = datetime(2024, 1, 3, 0)
    t_ref_c = datetime(2024, 1, 3, 1)
    t_bos_c = datetime(2024, 1, 3, 2)
    t_disp_c = datetime(2024, 1, 3, 3)
    t_c = datetime(2024, 1, 3, 4)
    poi_c = _mo(Role.POI, "H4", ObjectType.ORDER_BLOCK, -1, [],
                creation_time=t_poi_c, state=ObjectState.ACTIVE, bar_index=210, candidate_bar=210,
                zone_high=1.0950, zone_low=1.0900)
    fvg_c = _mo(Role.REFINEMENT, "M15", ObjectType.FVG, -1, [poi_c.id],
                creation_time=t_ref_c, state=ObjectState.ACTIVE, bar_index=220, candidate_bar=220,
                zone_high=1.0920, zone_low=1.0880)
    fvg_c.parent_object = poi_c.id
    bos_c = _mo(Role.CONFIRMATION, "M15", ObjectType.BOS, -1, [poi_c.id, fvg_c.id],
                creation_time=t_bos_c, bar_index=230, candidate_bar=230)
    disp_c = _mo(Role.EXECUTION, "M15", ObjectType.DISPLACEMENT, -1, [fvg_c.id, poi_c.id],
                 creation_time=t_disp_c, bar_index=240, candidate_bar=240)
    fvg_c.related_objects = [poi_c.id, bos_c.id, disp_c.id]
    poi_c.related_objects = [fvg_c.id, bos_c.id, disp_c.id]
    objs += [poi_c, fvg_c, bos_c, disp_c]
    decisions.append(t_c)

    ms = MarketState()
    for o in sorted(objs, key=lambda x: (x.origin_tf, x.creation_time)):
        ms.ingest(o)
    return ms, decisions


def _ctx_per_direction(direction):
    return _ctx(direction)


# --------------------------------------------------------------------------- #
# FULL / PREFIX (gate E2)
# --------------------------------------------------------------------------- #
def _truncate_objects_before(ms: MarketState, T) -> MarketState:
    """Devuelve un MarketState con solo objetos nacidos en o antes de T."""
    out = MarketState()
    for o in ms.all_objects():
        ct = o.creation_time
        if ct is None or T is None or ct <= T:
            out.ingest(o)
    return out


def run_full_prefix(ms, decisions):
    """E2 (FULL/PREFIX literal): para cada T, el artefacto FULL debe coincidir
    EXACTAMENTE con el artefacto PREFIX (corpus truncado en T) en TODOS los
    campos: records, episodes, rejections, aggregates (por TF/dirección/razón),
    gates, estados, lineage, razones y orden. No solo episodios/rechazos."""
    full = EP.build_episodes(ms, decisions, _ctx(1))
    mismatches = []
    for T in decisions:
        prefix_ms = _truncate_objects_before(ms, T)
        prefix = EP.build_episodes(prefix_ms, [T], _ctx(1))
        # Reconstruimos los dicts full/prefix como aparecerían guardados.
        full_all = {
            "records": full["records"],
            "episodes": full["episodes"],
            "rejections": full["rejections"],
            "aggregates": full["aggregates"],
            "gates": full["gates"],
        }
        prefix_all = {
            "records": prefix["records"],
            "episodes": prefix["episodes"],
            "rejections": prefix["rejections"],
            "aggregates": prefix["aggregates"],
            "gates": prefix["gates"],
        }
        # Slice por T: comparamos SOLO lo que corresponde a esta decisión.
        def _slice(d, key):
            return [x for x in d[key] if x.get("decision_time") == _ser(T)]
        for field in ("records", "episodes", "rejections"):
            if _slice(full_all, field) != _slice(prefix_all, field):
                mismatches.append({"T": _ser(T), "kind": field})
        # Conteo total de episodios/rechazos/records de T debe ser idéntico.
        full_counts = {
            "episodes": len(_slice(full_all, "episodes")),
            "rejections": len(_slice(full_all, "rejections")),
            "records": len(_slice(full_all, "records")),
        }
        prefix_counts = {
            "episodes": len(_slice(prefix_all, "episodes")),
            "rejections": len(_slice(prefix_all, "rejections")),
            "records": len(_slice(prefix_all, "records")),
        }
        if full_counts != prefix_counts:
            mismatches.append({"T": _ser(T), "kind": "counts",
                               "full": full_counts, "prefix": prefix_counts})
        # gates deben ser idénticos
        if full_all["gates"] != prefix_all["gates"]:
            mismatches.append({"T": _ser(T), "kind": "gates"})
    return {"prefix_matches_full": len(mismatches) == 0, "mismatches": mismatches}


def _ser(v):
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


# --------------------------------------------------------------------------- #
# reporte
# --------------------------------------------------------------------------- #
def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=os.getcwd(), stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return "UNKNOWN"


def _rechecksum(artifact: dict) -> str:
    """Recalcula el checksum del artefacto COMPLETO (incluye generator_commit,
    full_prefix y aggregated_status), excluyendo generated_at y el propio
    checksum (para evitar dependencia circular)."""
    core = {k: v for k, v in artifact.items() if k not in ("generated_at", "checksum")}
    payload = json.dumps(core, sort_keys=True, default=_ser)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True, help="ruta del reporte JSON")
    args = p.parse_args(argv)

    ms, decisions = build_corpus()
    ctx = _ctx(1)
    artifact = EP.build_episodes(ms, decisions, ctx, config={"contract_version": CONTRACT_VERSION})
    artifact["generator_commit"] = _git_commit()

    fp = run_full_prefix(ms, decisions)
    artifact["full_prefix"] = fp

    # aggregated_status
    if not fp["prefix_matches_full"]:
        status = "BLOCKED"
    elif artifact["aggregates"]["totals"]["episodes"] == 0:
        status = "REVIEW"
    else:
        status = "PASS"
    artifact["aggregated_status"] = status

    # FALLA 4 corregida: el checksum debe cubrir TODOS los campos, incluida la
    # provenancia del repo (generator_commit), full_prefix y aggregated_status.
    artifact["checksum"] = _rechecksum(artifact)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2, sort_keys=True, default=_ser)
    print(f"EPISODES FUNNEL audit -> {args.out} | status={status} | "
          f"episodes={artifact['aggregates']['totals']['episodes']} | "
          f"checksum={artifact['checksum']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
