"""engine/zone_authority.py — Evaluador de autoridad de zona (RESCATE de la capa backtest).

RESCATE (2026-08-07): migrado desde ict_backtest/zone_authority.py para cumplir la
Ley Fundamental (motor = fuente unica). El original se borro por vivir en
ict_backtest/ (capa desechable). La LOGICA era pura (solo dependia de
ict_backtest.htf_pd_index, que ahora vive en engine.htf_pd_index), asi que se
reencausa el import y se rescata. CERO imports de ict_backtest/.

Este modulo es PERCEPCION, no decision. Recibe una zona LTF ya trazada por el motor
+ los PD arrays HTF vigentes (del indice engine.htf_pd_index) y devuelve la
AUTORIDAD CONTEXTUAL de esa zona.

Contrato de no invasion:
  - NO decide direccion / entry / SL / TP.
  - NO crea zonas: solo lee las que el detector/motor ya trazaron.
  - NO altera el conteo de senales (su efecto sobre el motor es CERO por diseno).
  - Solo aporta informacion: "esta zona merece atencion" (Alta/Media/Baja).

Salida: ZoneAuthority
  has_htf_anchor : bool   ¿el HTF tiene PD array en la direccion de la zona?
  tier            : str    mejor tier del ancla (T1 BPR > T2 FVG/OB > T3 rejection)
  stacking_level  : int    nº de capas TF distintas que respaldan (apilado)
  confidence_weight: float  0..1  PESO DE CONFIANZA (no "bonus=comprar")
  level           : str    Alta | Media | Baja (derivado del peso)

Regla de hierro (R4 / auditoria Fase E): C es PESO DE CONFIANZA, NUNCA gate duro.
El consumidor (observador / umbral) decide si filtra; C no. La tesis 21 sec4 dice
POI = bonus; convertirlo en gate duro destruye edge (PF 0.900 vs 1.511).
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.htf_pd_index import HtfPdZone


TIER_RANK = {"T1": 3, "T2": 2, "T3": 1, "NONE": 0}


@dataclass(frozen=True)
class ZoneAuthority:
    has_htf_anchor: bool
    tier: str
    stacking_level: int
    confidence_weight: float
    level: str

    def __post_init__(self):
        # Defensa de invariantes (no invasion): el peso siempre en [0,1].
        if not (0.0 <= self.confidence_weight <= 1.0):
            raise ValueError(f"confidence_weight fuera de [0,1]: {self.confidence_weight}")


def _higher_tier(a: str, b: str) -> str:
    return a if TIER_RANK.get(a, 0) >= TIER_RANK.get(b, 0) else b


def evaluate_zone_authority(
    ltf_zone: HtfPdZone | None,
    htf_zones: list[HtfPdZone],
) -> ZoneAuthority:
    """Evalua la calidad CONTEXTUAL de una zona LTF ya existente.

    `ltf_zone` es la zona que el motor YA trazo (FVG/OB del LTF). C la RECIBE;
    si es None (el motor no trazo zona), C no inventa nada -> sin ancla.
    `htf_zones` son los PD arrays HTF vigentes (engine.htf_pd_index) en la misma vela.

    Peso de confianza (monotono, determinista, SIN indicadores):
      base 0.0 si no hay ancla HTF,
      +0.5 si hay ancla HTF en la direccion de la zona,
      +hasta 0.3 por tier (T1=+0.3, T2=+0.15, T3=+0.05),
      +hasta 0.2 por stacking (1 capa=+0.0, 2=+0.1, 3+=+0.2).
    Maximo 1.0. Nunca negativo.
    """
    if ltf_zone is None:
        return ZoneAuthority(
            has_htf_anchor=False, tier="NONE", stacking_level=0,
            confidence_weight=0.0, level="Baja",
        )

    direction = ltf_zone.direction
    # Anclas del HTF en la MISMA direccion que la zona LTF.
    anchors = [z for z in htf_zones if z.direction == direction]
    if not anchors:
        return ZoneAuthority(
            has_htf_anchor=False, tier="NONE", stacking_level=0,
            confidence_weight=0.0, level="Baja",
        )

    has_anchor = True
    # Mejor tier entre los anclas (T1 > T2 > T3).
    best_tier = "NONE"
    for z in anchors:
        best_tier = _higher_tier(best_tier, z.pd_tier)
    # Stacking: capas TF distintas que respaldan (libro 21 sec3).
    stacking = len({z.tf for z in anchors})

    w = 0.5  # ancla HTF presente
    tier_bonus = {"T1": 0.3, "T2": 0.15, "T3": 0.05}.get(best_tier, 0.0)
    stack_bonus = {1: 0.0, 2: 0.1}.get(stacking, 0.2 if stacking >= 3 else 0.0)
    w = min(1.0, w + tier_bonus + stack_bonus)

    level = "Alta" if w >= 0.8 else ("Media" if w >= 0.5 else "Baja")
    return ZoneAuthority(
        has_htf_anchor=has_anchor,
        tier=best_tier,
        stacking_level=stacking,
        confidence_weight=round(w, 4),
        level=level,
    )
