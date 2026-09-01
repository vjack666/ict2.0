"""Teacher rubric: el "humano" expresado como codigo (HEAD A del sistema de aprendizaje).

NO es una red neuronal. Es tu rúbrica ICT documentada (02_MSS_CHOCH.md,
ICT_RULEBOOK.md, SPEC_TESIS_FORMAL.md) convertida en una funcion pura que,
dado un CHOCH y su contexto de mercado, devuelve human_score 0-100 + clase +
desglose de por que. Esto es lo que el modelo "como humano" debe aprender a
imitar (teacher labeling), sin que TU llenes human_score a mano.

Fuentes (cita exacta, nada de invencion):
  - Estructura real: 02_MSS_CHOCH.md §0/#2, ICT_RULEBOOK §3
      CHOCH = rompe el swing CONTRARIO al ultimo BOS (nivel del ultimo BOS,
      no del BOS mismo). momentum = racha >=2 HH (up) / LL (down).
  - Desplazamiento: ICT_RULEBOOK §6, SPEC §7
      cuerpo >= 70% del rango (desplazamiento institucional real);
      50-70% = debil (bonus, no gate). BONUS, no veto (resuelto 2026-08-15).
  - Confluencia: ICT_RULEBOOK Apéndice (pesos no tuneados -> usados como bonus)
      MTF align +3, displacement +2, FVG +2, OB +2, sweep +2,
      BOS a favor +1, CHOCH a favor +3, OTE +1 (escalados a puntos).
  - Contexto HTF: SPEC §1/§9  -> a_favor / contra / neutral.
  - Reclaim/invalidacion: tools/swing_state.py (ObjectState) -> pierde autoridad.
  - Killzone: SPEC §15 -> London/NY (bonus).

Salida: human_score 0-100, clase {premium>=90, useful 70-89, noise<70}
        (calibrado 2026-08-17; plan F2/F3 original usaba 85/70).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# Pesos de confluencia (ICT_RULEBOOK Apéndice, "not tuned" -> bonus relativo)
_CONFLUENCE = {
    "mtf_align": 3.0,
    "displacement": 2.0,
    "fvg": 2.0,
    "ob": 2.0,
    "sweep": 2.0,
    "bos_afavor": 1.0,
    "choch_afavor": 3.0,
    "ote": 1.0,
    "killzone": 1.5,
}
_MAX_CONFLUENCE = sum(_CONFLUENCE.values())  # normalizador


@dataclass
class RubricInput:
    signal: str                      # CHOCH_UP / CHOCH_DOWN
    choch_real: bool                 # rompe swing contrario al ultimo BOS (02_MSS_CHOCH §2)
    momentum: bool                   # racha >=2 HH/LL (SPEC §8)
    after_bos: bool                  # hubo BOS de mercado en dir opuesta (EXP-012)
    displacement: bool               # cuerpo >=70% rango (ICT_RULEBOOK §6 / SPEC §7)
    body_ratio: float = 0.0         # 0-1, para displacement debil (50-70%)
    htf_ctx: str = "neutral"         # a_favor / contra / neutral (SPEC §1/§9)
    reclaimed: bool = False          # nivel recuperado -> invalida (swing_state)
    conf_fill: dict = field(default_factory=dict)  # subconjunto de _CONFLUENCE -> True
    killzone: bool = False           # SPEC §15


@dataclass
class RubricOutput:
    human_score: float
    klass: str                       # premium / useful / noise
    breakdown: dict


def score_rubric(inp: RubricInput) -> RubricOutput:
    """Calcula human_score 0-100 segun la rubric ICT documentada."""
    # 1) Estructura real es el piso. Sin CHOCH real, es ruido por definicion.
    if not inp.choch_real:
        return RubricOutput(0.0, "noise", {"reason": "no es CHOCH real (no rompe swing contrario al ultimo BOS)"})

    base = 40.0  # piso por ser CHOCH real documentado (02_MSS_CHOCH §0)

    # 2) Momentum (racha de estructura) -> caracter de giro (EXP-012 (a))
    if inp.momentum:
        base += 10.0

    # 3) after_bos: el BOS que el CHOCH viene a revertir (EXP-012 (b))
    if inp.after_bos:
        base += 8.0

    # 4) Desplazamiento: bonus, no veto (resuelto 2026-08-15). Fuerte >=0.70, debil 0.50-0.70
    if inp.displacement:
        base += 12.0
    elif inp.body_ratio >= 0.50:
        base += 5.0   # displacement debil (bonus menor)

    # 5) Contexto HTF (SPEC §1/§9)
    if inp.htf_ctx == "a_favor":
        base += 12.0
    elif inp.htf_ctx == "contra":
        base += 4.0   # Turtle Soup vive en rango/contra (SPEC §18) -> menor pero valido
    # neutral -> 0

    # 6) Confluencia (ICT_RULEBOOK Apéndice, normalizada a 0-15)
    conf = 0.0
    for k, w in _CONFLUENCE.items():
        if k == "killzone":
            if inp.killzone:
                conf += w
        elif inp.conf_fill.get(k):
            conf += w
    base += 15.0 * (conf / _MAX_CONFLUENCE)

    # 7) Reclaim/invalidacion anula autoridad (swing_state ObjectState)
    if inp.reclaimed:
        base = 0.0

    score = float(max(0.0, min(100.0, base)))

    # Clase (plan F2/F3)
    # Calibrado 2026-08-17: premium>=90 (antes 85)
    from tools.confirmation_thresholds import choch_class_from_score
    klass = choch_class_from_score(score)

    return RubricOutput(score, klass, {
        "base_real": 40.0,
        "momentum": 10.0 if inp.momentum else 0.0,
        "after_bos": 8.0 if inp.after_bos else 0.0,
        "displacement": (12.0 if inp.displacement else (5.0 if inp.body_ratio >= 0.50 else 0.0)),
        "htf_ctx": (12.0 if inp.htf_ctx == "a_favor" else (4.0 if inp.htf_ctx == "contra" else 0.0)),
        "confluence": round(15.0 * (conf / _MAX_CONFLUENCE), 2),
        "reclaimed": inp.reclaimed,
        "final": score,
    })


def rubric_from_extra(extra: dict, signal: str) -> RubricOutput:
    """Construye RubricInput desde el dict extra de un ToolEvent CHOCH (tools/)."""
    conf_fill = {
        "mtf_align": extra.get("choch_htf_ctx") == "a_favor",
        "displacement": bool(extra.get("choch_displacement")),
        "bos_afavor": bool(extra.get("choch_after_bos")),
        "choch_afavor": True,  # el propio evento es CHOCH
    }
    # fvg/ob/sweep/ote no estan en extra hoy; se dejan como False (extensible)
    inp = RubricInput(
        signal=signal,
        choch_real=bool(extra.get("choch_real")),
        momentum=bool(extra.get("choch_momentum")),
        after_bos=bool(extra.get("choch_after_bos")),
        displacement=bool(extra.get("choch_displacement")),
        body_ratio=float(extra.get("choch_break_body_ratio", 0.0) or 0.0),
        htf_ctx=extra.get("choch_htf_ctx", "neutral"),
        reclaimed=(extra.get("choch_reclaimed") or extra.get("status") == "invalidated"),
        conf_fill=conf_fill,
        killzone=bool(extra.get("choch_killzone")),
    )
    return score_rubric(inp)


# ---------------------------------------------------------------------------
# Rúbrica BOS (HEAD A para eventos BOS) — fuentes:
#   ICT_RULEBOOK.md §2 (BOS = ruptura a favor, por cierre de cuerpo)
#   tools/quality_score.py (_compute_bos_quality rescatado de SMC-SYSTEMS)
#   tools/bos_validate.py (ACTIVE/INVALIDATED por geometria pura)
# Un BOS es continuacion de marea; se califica por FUERZA del break y
# CONFIRMACION, no por giro. Reusa RubricOutput (mismo contrato de salida).
# ---------------------------------------------------------------------------

@dataclass
class BosRubricInput:
    signal: str                      # BOS_UP / BOS_DOWN
    displacement_prev: bool          # displacement previo en la direccion (quality_score c1)
    body_ratio: float = 0.0         # cuerpo break / rango (quality_score c2)
    dist_to_level: float = 0.0       # close al nivel roto / rango prom (quality_score c3, cap 1)
    confirmed: bool = False          # no retorno inmediato (quality_score c4)
    status: str = "active"           # active / invalidated (bos_validate)
    htf_ctx: str = "neutral"         # a_favor / contra / neutral


def score_bos_rubric(inp: BosRubricInput) -> RubricOutput:
    """Calcula human_score 0-100 de un BOS segun la rubric ICT documentada.

    Pesos derivados de tools/quality_score.py (4 componentes igual peso 0.25
    cada uno, 0-1) + contexto HTF + estado. El BOS invalidado pierde autoridad.
    """
    # 4 componentes de quality_score.py (cada uno 0-1, peso 0.25 -> 0-100 escala)
    q = 0.0
    q += 0.25 * (1.0 if inp.displacement_prev else 0.0)
    q += 0.25 * float(min(1.0, max(0.0, inp.body_ratio)))
    q += 0.25 * float(min(1.0, max(0.0, inp.dist_to_level)))
    q += 0.25 * (1.0 if inp.confirmed else 0.0)
    base = 100.0 * q   # 0-100 por calidad geometrica del break

    # Contexto HTF (bonus, no veto): a_favor refuerza continuacion
    if inp.htf_ctx == "a_favor":
        base += 8.0
    elif inp.htf_ctx == "contra":
        base -= 6.0   # BOS contra la marea HTF es debil (Turtle Soup territory)

    # Estado: invalidado anula autoridad (bos_validate)
    if inp.status == "invalidated":
        base = 0.0

    score = float(max(0.0, min(100.0, base)))
    # Calibrado 2026-08-17: premium>=90 (antes 85)
    from tools.confirmation_thresholds import choch_class_from_score
    klass = choch_class_from_score(score)
    return RubricOutput(score, klass, {
        "geo_quality": round(base, 2),
        "displacement_prev": inp.displacement_prev,
        "body_ratio": round(inp.body_ratio, 3),
        "dist_to_level": round(inp.dist_to_level, 3),
        "confirmed": inp.confirmed,
        "htf_ctx": inp.htf_ctx,
        "status": inp.status,
        "final": score,
    })


if __name__ == "__main__":
    # Smoke: un CHOCH real fuerte a favor del HTF con displacement
    strong = RubricInput(
        signal="CHOCH_UP", choch_real=True, momentum=True, after_bos=True,
        displacement=True, htf_ctx="a_favor",
        conf_fill={"mtf_align": True, "displacement": True, "choch_afavor": True, "bos_afavor": True},
        killzone=True,
    )
    weak = RubricInput(signal="CHOCH_UP", choch_real=True, momentum=False,
                       after_bos=False, displacement=False, htf_ctx="neutral")
    print("STRONG:", score_rubric(strong))
    print("WEAK  :", score_rubric(weak))
    # Smoke BOS
    bos_strong = BosRubricInput(signal="BOS_UP", displacement_prev=True,
                                body_ratio=0.8, dist_to_level=0.9, confirmed=True,
                                htf_ctx="a_favor", status="active")
    bos_weak = BosRubricInput(signal="BOS_UP", displacement_prev=False,
                              body_ratio=0.2, dist_to_level=0.1, confirmed=False,
                              status="active")
    bos_inv = BosRubricInput(signal="BOS_UP", displacement_prev=True,
                             body_ratio=0.8, dist_to_level=0.9, confirmed=True,
                             status="invalidated")
    print("BOS STRONG:", score_bos_rubric(bos_strong))
    print("BOS WEAK  :", score_bos_rubric(bos_weak))
    print("BOS INV   :", score_bos_rubric(bos_inv))
