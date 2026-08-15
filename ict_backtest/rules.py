"""ict_backtest/rules.py — SHIM: killzone vive en engine.killzone (Ley).

La unica fuente de killzone_en es engine.killzone. Este modulo lo re-exporta para
no romper el dashboard/observador. El checklist PO3 (intradia/scalping) queda.
"""
from __future__ import annotations  # diferir anotaciones (datetime | None en firmas)

import datetime  # noqa: F401  (usado en firmas de funciones mas abajo; requerido en entorno limpio)

from engine.killzone import (  # noqa: F401
    KILLZONES_UTC,
    KILLZONES_ET,
    _KZ_ET_TO_SHORT,
    server_to_utc,
    _et_band_to_utc,
    _killzone_en_utc,
    killzone_en,
    short_label,
)



def _dir_setup(bias: str, votes: dict | None, m15: dict, counter_trend: bool = False) -> str:
    """Direccion del setup.

    A-favor (counter_trend=False): la direccion sigue al BOS/votos del exec TF
    (que coincide con la marea del HTF).
    Contratendencia (counter_trend=True): el setup opera la REVERSION, por lo
    que la direccion es el BOS/choch del exec TF TAL CUAL (ese break YA es el
    movimiento contrario a la marea del HTF). No se invierte nada.
    """
    v = votes or {}
    if v.get("LONG", 0) > v.get("SHORT", 0):
        raw = "LONG"
    elif v.get("SHORT", 0) > v.get("LONG", 0):
        raw = "SHORT"
    else:
        bd = int(m15.get("bos_dir", 0) or 0)
        raw = "LONG" if bd > 0 else "SHORT" if bd < 0 else "NEUTRAL"
    if counter_trend:
        # En contratendencia el setup opera la REVERSION: direccion OPUESTA al sesgo HTF.
        want = -1 if bias == "BULLISH" else 1 if bias == "BEARISH" else 0
        return "LONG" if want == 1 else "SHORT" if want == -1 else "NEUTRAL"
    return raw


def _sweep_dir(estructura: dict, tfs: tuple[str, ...]) -> str:
    up = any(estructura.get(tf, {}).get("sweep_up") for tf in tfs)
    down = any(estructura.get(tf, {}).get("sweep_down") for tf in tfs)
    if up and down:
        return "both"
    return "up" if up else "down" if down else "none"


def _bos_exec(estructura: dict, exec_tf: str = "M15") -> str:
    m15 = estructura.get(exec_tf, {})
    bd = int(m15.get("bos_dir", 0) or 0)
    st = m15.get("bos_status", "")
    if bd == 1 and st == "active":
        return "alcista"
    if bd == -1 and st == "active":
        return "bajista"
    if bd != 0:
        return "intentando"
    return "no"


def checklist_intradia(estructura: dict, bias: str, votes: dict | None,
                       ts: datetime | None = None, exec_tf: str = "M15",
                       htf: str = "H4", counter_trend: bool = False) -> list[str]:
    """Checklist INTRADIA (PO3/Turtle Soup). Items numerados.

    ts: timestamp de la vela para killzone historica (si None, fuera de KZ).
    exec_tf: TF de ejecucion (M15 en vivo; H4 en backtest de opcion A).
    htf: TF de contexto alto para el sweep (H4 por defecto).
    counter_trend: si True, el setup opera CONTRA la marea del HTF.
    """
    items: list[str] = []
    d1 = estructura.get("D1", {})
    h4 = estructura.get(htf, {})
    m15 = estructura.get(exec_tf, {})
    label = "CONTRA-tendencia" if counter_trend else "a-favor"
    dir_setup = _dir_setup(bias, votes, m15, counter_trend)
    kz = killzone_en(ts) if ts is not None else ""

    # 1. Sesgo del dia
    if "NEUTRAL" in (bias or "") or not bias:
        items.append("FALTA: definir SESGO DEL DIA (L/S) desde H4/D1.")
    else:
        items.append(f"OK: Sesgo del dia: {bias} (setup {label}).")

    # 2. Contexto D1/H4 (en contratendencia, el HTF debe tener tendencia clara A OPONERSE)
    if counter_trend:
        if bias in ("BULLISH", "BEARISH"):
            items.append(f"OK: Contratendencia lista sobre {bias} en {htf}.")
        else:
            items.append(f"FALTA: contratendencia requiere HTF con tendencia ({bias}).")
    else:
        if d1.get("trend") in ("", "RANGING") and h4.get("trend") in ("", "RANGING"):
            items.append("FALTA: contexto D1/H4 definido (en rango -> sin marea).")
        else:
            items.append(f"OK: Contexto D1 {d1.get('trend','?')} / {htf} {h4.get('trend','?')}.")

    # 3. Killzone intradia
    if kz in ("London Open", "New York AM", "New York PM"):
        items.append(f"OK: Killzone intradia activa: {kz} (UTC).")
    else:
        items.append("FALTA: killzone intradia (London/NY) -> esperar ventana.")

    # 4. Sweep HTF/exec (en contratendencia, el sweep es de la liquidez OPUESTA al sesgo)
    sw = _sweep_dir(estructura, (htf, exec_tf))
    if sw == "none":
        items.append(f"FALTA: barrido de liquidez (sweep SSL/BSL) en {htf}/{exec_tf}.")
    else:
        items.append(f"OK: Liquidez barrida ({sw}) en {htf}/{exec_tf}.")

    # 5. BOS/CHOCH exec
    bos = _bos_exec(estructura, exec_tf)
    if counter_trend:
        # En contratendencia el disparo es un BOS en direccion OPUESTA al sesgo HTF.
        exec_row = estructura.get(exec_tf, {})
        bos_dir = int(exec_row.get("bos_dir", 0) or 0)
        choch = str(exec_row.get("choch_signal", "NONE"))
        # direccion objetivo: opuesta al sesgo
        want = -1 if bias == "BULLISH" else 1 if bias == "BEARISH" else 0
        ok = (bos_dir == want) or (want == 1 and choch == "CHOCH_BULLISH") or (want == -1 and choch == "CHOCH_BEARISH")
        if want != 0 and ok:
            nombre = "CHOCH/LONG" if want == 1 else "CHOCH/SHORT"
            items.append(f"OK: reversión {nombre} en {exec_tf} (contra {bias}).")
        else:
            items.append(f"FALTA: reversión en {exec_tf} contra {bias} (BOS={bos_dir}, CHOCH={choch}).")
    else:
        if bos == "no":
            items.append(f"FALTA: BOS/CHOCH en {exec_tf} (estructura intacta).")
        else:
            items.append(f"OK: {exec_tf} con BOS {bos}.")

    # 6. Direccion alineada
    if dir_setup == "NEUTRAL":
        items.append("FALTA: direccion del setup (votos/L-S o BOS M15).")
    else:
        items.append(f"OK: Direccion setup: {dir_setup}.")

    # 7-8. TP en liquidez opuesta + RR>=1:2 (regla de ejecucion, ver engine)
    items.append("PENDIENTE: TP en liquidez opuesta (BSL/SSL del mapa ICT).")
    items.append("PENDIENTE: RR >= 1:2 (regla Stellar).")
    return items


def checklist_scalping(estructura: dict, bias: str, votes: dict | None,
                       ts: datetime | None = None, exec_tf: str = "M15") -> list[str]:
    """Checklist SCALPING (M1/M5, Silver Bullet). Items numerados.

    ts: timestamp de la vela para ventana NY AM historica.
    exec_tf: TF de ejecucion cargado (M5/M15/M1). Lo pasa el engine de forma
    explicita (no se adivina) para evitar desincronizacion con el backtest.
    """
    items: list[str] = []
    # exec TF lo pasa el engine de forma explicita (no se adivina):
    # evita la desincronizacion que silenciaba Silver Bullet (ver AUDIT_BUG_SILVER_TF.md).
    m15 = estructura.get(exec_tf, {}) if exec_tf else {}
    dir_setup = _dir_setup(bias, votes, m15)
    kz = killzone_en(ts) if ts is not None else ""

    # 1. Ventana Silver Bullet (NY AM)
    if kz == "New York AM":
        items.append("OK: Ventana Silver Bullet activa (NY AM).")
    else:
        items.append("FALTA: ventana Silver Bullet (NY AM 10-11 ET) -> esperar.")

    # 2. Sesgo filtrado
    if "NEUTRAL" in (bias or "") or not bias:
        items.append("FALTA: sesgo del dia para filtrar solo setups a favor.")
    else:
        items.append(f"OK: Sesgo filtra setups: {bias}.")

    # 3. Sweep en el TF de ejecucion (exec_tf, explicito).
    sw = _sweep_dir(estructura, (exec_tf,)) if exec_tf else "none"
    if sw == "none":
        items.append("FALTA: sweep de SSL/BSL en el TF de ejecucion (previo al FVG M1/M5).")
    else:
        items.append(f"OK: Sweep {exec_tf} ({sw}) presente.")

    # 4. FVG M1/M5
    m5 = estructura.get("M5", {}) or {}
    m1 = estructura.get("M1", {}) or {}
    fvg_m5 = str(m5.get("fvg_state", "-")).lower() not in ("-", "none", "nan", "")
    fvg_m1 = str(m1.get("fvg_state", "-")).lower() not in ("-", "none", "nan", "")
    if not m5 and not m1:
        items.append("PENDIENTE: buscar FVG en M1/M5 tras el sweep (sin datos M1/M5).")
    elif fvg_m5 or fvg_m1:
        donde = "M5" if fvg_m5 else "M1"
        items.append(f"OK: FVG en {donde} presente tras sweep (Silver Bullet listo).")
    else:
        items.append("FALTA: sin FVG en M1/M5 aun (esperar tras el sweep).")

    # 5. Direccion coincide
    if dir_setup == "NEUTRAL":
        items.append("FALTA: direccion del setup para el scalp.")
    else:
        items.append(f"OK: Direccion scalp: {dir_setup}.")

    # 6. SL en FVG/OB
    ob_m5 = str(m5.get("ob_dir", "-")) not in ("-", "none", "nan", "")
    if ob_m5:
        items.append(f"OK: OB en M5 ({m5.get('ob_dir')}) -> SL sobre/fallo del OB.")
    else:
        items.append("PENDIENTE: SL bajo FVG alcista / sobre FVG bajista (o SSL/BSL).")

    # 7. RR 1:2
    items.append("PENDIENTE: RR >= 1:2, salida en liquidez opuesta (rapido).")
    return items


def evaluate(model: str, estructura: dict, bias: str, votes: dict | None,
             ts: datetime | None = None, exec_tf: str = "M15",
             htf: str = "H4", counter_trend: bool = False) -> dict[str, Any]:
    """Evalua un modelo ICT y devuelve checklist + puntuacion.

    model: "intradia" | "scalping" | "po3"
    exec_tf: TF de ejecucion (M15 en vivo; H4 en backtest opcion A).
    counter_trend: si True, setup opera contra la marea del HTF.
    Devuelve {"model":..., "checks":[...], "passed":int, "total":int,
              "ready":bool, "direction":"LONG"|"SHORT"|"NEUTRAL"}
    Para model="po3" tambien incluye "phases", "complete", "incomplete_reason".
    """
    if model == "intradia":
        checks = checklist_intradia(estructura, bias, votes, ts, exec_tf, htf, counter_trend)
    elif model == "scalping":
        checks = checklist_scalping(estructura, bias, votes, ts, exec_tf)
    elif model == "po3":
        return evaluate_po3("po3", estructura, bias, votes, ts, exec_tf, htf, counter_trend)
    else:
        raise ValueError(f"modelo desconocido: {model}")

    passed = sum(1 for c in checks if c.startswith("OK:"))
    total = len(checks)
    # "ready" = todos los OK (los PENDIENTE son de ejecucion, no bloquean senal)
    blocked = [c for c in checks if c.startswith("FALTA:")]
    dir_setup = _dir_setup(bias, votes, estructura.get(exec_tf, {}), counter_trend)
    return {
        "model": model,
        "checks": checks,
        "passed": passed,
        "total": total,
        "ready": len(blocked) == 0,
        "direction": dir_setup,
    }


if __name__ == "__main__":
    # Smoke test (sin pytest).
    est = {
        "D1": {"trend": "BULLISH"}, "H4": {"trend": "BULLISH"},
        "M15": {"bos_dir": 1, "bos_status": "active", "sweep_up": True},
        "M5": {"fvg_state": "bullish", "ob_dir": "bullish"},
    }
    from datetime import datetime, timezone
    ts = datetime(2026, 7, 10, 13, 30, tzinfo=timezone.utc)  # NY AM
    r = evaluate("scalping", est, "BULLISH", {"LONG": 3, "SHORT": 1}, ts)
    print("SCALPING:", r["ready"], r["direction"], f"({r['passed']}/{r['total']})")
    for c in r["checks"]:
        print("  -", c)
