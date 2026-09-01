"""Fase 1 — MultiTFContext: infraestructura de lectura multitemporal.

Objetivo único (Opción A, sin cambio de estrategia):
  - Exponer el snapshot closed-only de TODA la cadena
    D1 -> H4 -> H1 -> M15 -> M5 -> M1 en un único objeto por barra t.
  - Libre de look-ahead: reusa EXACTAMENTE el patrón de
    ict_backtest/v2/context_mtf.build_context_stack (closed_row_at_time
    por TF, time <= t). No se introduce ningún nuevo lookup.
  - El motor (run_sequence) sigue usando el MISMO HTF que hoy:
    extract_htf_layer(context, htf) entrega el dict plano con las
    mismas claves que consume run_sequence (trend / sweep_up /
    sweep_down / pd_zones). Los otros 5 TF viajan disponibles en el
    contexto pero run_sequence no los mira todavía (Fase 2 activará la
    cascada).

NO se activa ningún filtro nuevo (B/C/E siguen como anotación en la
señal). Esto es puramente infraestructura de lectura.
"""
from __future__ import annotations

from typing import Any


class MultiTFContext(dict):
    """Dict {tf: snapshot_closed_only} para todos los TF de la cadena.

    Es un dict plano para compatibilidad con el consumo por clave
    (ctx["D1"]), pero tipado para documentar que representa el contexto
    multitemporal completo en un tiempo t.
    """


def build_multitf_context(
    ms: dict[str, Any],
    t: Any,
    *,
    tfs: tuple[str, ...] = ("D1", "H4", "H1", "M15", "M5", "M1"),
    anchored_pd_zones: dict[str, Any] | None = None,
    closed_index: dict[str, int] | None = None,
) -> MultiTFContext:
    """Construye el MultiTFContext closed-only en t.

    Delega en build_context_stack (engine.plan), que ya garantiza
    anti-look-ahead vía closed_row_at_time por TF. Devuelve MultiTFContext.

    Opción 3 (2026-08-14, Change Gate): ``closed_index`` es un dict
    ``{tf: int}`` con el índice precomputado de la última vela HTF cerrada
    <= t. Si se pasa, build_context_stack usa df.iloc[idx] en vez de
    _closed_row_at_time (O(1) lookup, mismo procesamiento de fila). Si no
    se pasa, comportamiento original (retrocompatible).

    Import lazy de engine.plan para evitar ciclo de import.
    """
    from engine.plan import build_context_stack

    stack = build_context_stack(
        ms, t, tfs=tfs,
        anchored_pd_zones=anchored_pd_zones,
        closed_index=closed_index,
    )
    return MultiTFContext(stack)


def extract_htf_layer(context: MultiTFContext, htf: str) -> dict[str, Any]:
    """Extrae el dict plano del TF que hoy consume run_sequence (Opción A).

    Devuelve las claves que run_sequence lee de est_htf:
      - trend (sequence.py:358)
      - sweep_up / sweep_down (sequence.py:147-149)
      - pd_zones (sequence.py:381/409-413, anotación Fase C)
    Los demás TF quedan en context pero no se usan aquí. Esto hace que
    run_sequence se comporte 100% idéntico al baseline de 1 nivel.
    """
    layer = context.get(
        htf, {"tf": htf, "available": False, "trend": "RANGING"}
    )
    return {
        "trend": layer.get("trend", "RANGING"),
        "sweep_up": bool(layer.get("sweep_up", False)),
        "sweep_down": bool(layer.get("sweep_down", False)),
        "pd_zones": list(layer.get("pd_zones", []) or []),
    }
