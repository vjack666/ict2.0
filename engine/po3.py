"""signals/po3.py — Estado canonico PO3 (Power of Three / AMD).

R1.1: `po3_state` con fases A / M / D, `complete` y `direction`.
R1.2: `evaluate(model="po3")` separado de Turtle Soup (ver ict_backtest/rules.py).

Fuente de verdad: docs/ict/08_POWER_OF_THREE.md (contrato §0, aprobado 2026-07-13).

Diseno:
- Helpers PUROS locales (NO importa de ict_backtest.rules) para evitar el
  ciclo de import: ict_backtest.__init__ -> rules -> signals.po3 -> rules.
  Los helpers aqui son la MISMA logica que rules.py (DRY semantico: mismo
  contrato, mismo nombre de campos del dict estructura). Quien cambie uno
  debe cambiar el otro (ver nota en rules.py evaluate_po3).
- `build_po3_state` es DETERMINISTA y sin look-ahead: solo lee el dict
  `estructura` que el llamador ya construyo con velas CERRADAS. No consulta
  el futuro. Quien arma `estructura` es responsable de no inyectar datos
  futuros (regla dura del libro 08: "solo velas cerradas").

Estado devuelto (PO3State):
    A, M, D        : bool  (fase presente)
    complete       : bool  (= A and M and D and aligned)
    direction      : "LONG" | "SHORT" | "NEUTRAL"
    aligned        : bool  (setup_dir == bias_dir; si no -> Turtle Soup, no PO3)
    incomplete_reason: list[str] (fases faltantes / fallo de alineacion)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PO3State:
    """Estado canonico del ciclo PO3 para un instante de tiempo dado."""

    A: bool = False
    M: bool = False
    D: bool = False
    complete: bool = False
    direction: str = "NEUTRAL"
    aligned: bool = False
    broke_open: bool = False
    incomplete_reason: list[str] = field(default_factory=list)

    def phases_present(self) -> str:
        """Etiqueta compacta A/M/D para UI y grafo."""
        return "".join(
            [
                "A" if self.A else "-",
                "M" if self.M else "-",
                "D" if self.D else "-",
            ]
        )


# --- Helpers PUROS (misma logica que ict_backtest/rules.py; sin import cruzado) ---

def _dir_setup(bias: str, votes: dict | None, m15: dict, counter_trend: bool = False) -> str:
    """Direccion del setup (a-favor; en PO3 counter_trend siempre False)."""
    v = votes or {}
    if v.get("LONG", 0) > v.get("SHORT", 0):
        raw = "LONG"
    elif v.get("SHORT", 0) > v.get("LONG", 0):
        raw = "SHORT"
    else:
        bd = int(m15.get("bos_dir", 0) or 0)
        raw = "LONG" if bd > 0 else "SHORT" if bd < 0 else "NEUTRAL"
    if counter_trend:
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


# --- Fases del contrato (docs/ict/08_POWER_OF_THREE.md §0) ---

def _has_htf_bias(bias: str) -> bool:
    """Fase A (parcial): el sesgo HTF esta definido (no NEUTRAL)."""
    return bool(bias) and "NEUTRAL" not in bias


def _has_session_range(estructura: dict, htf: str) -> bool:
    """Fase A alternativa: rango explicito con high/low de sesion/Asian marcados.

    El libro 08 acepta sesgo HTF O rango explicito. Hoy el sistema no modela
    el rango de sesion como campo dedicado; lo senalamos como extension R3
    (PO3-2). Si el llamador lo popularemos, lo leemos de `estructura[htf]`
    bajo la clave `session_range`. Mientras tanto: False.
    """
    return bool(estructura.get(htf, {}).get("session_range"))


def _phase_a(estructura: dict, bias: str, htf: str) -> bool:
    """A — Accumulation: sesgo HTF o rango de sesion explicito."""
    return _has_htf_bias(bias) or _has_session_range(estructura, htf)


def _phase_m(estructura: dict, bias: str, htf: str, exec_tf: str) -> tuple[bool, bool]:
    """M — Manipulation: sweep EN CONTRA del sesgo (caza de stops).

    sweep_opposes_bias:
      - sesgo BULLISH  -> el sweep debe ser BAJISTA (sweep_down, barre SSL)
      - sesgo BEARISH  -> el sweep debe ser ALCISTA (sweep_up, barre BSL)
    Si no hay sesgo (NEUTRAL) no hay manipulacion en contra definible -> False.

    Filtro duro del OPEN DEL DIA (R3 / PO3-2, docs/ict/08_POWER_OF_THREE.md
    paso 3): si el llamador pobló `estructura["D1"]["session_open"]` (precio de
    la vela D1 YA CERRADA, sin look-ahead), la manipulacion debe romper ese
    open. Es decir: el sweep en contra ademas debe haber quebrado el open del
    día (low < open si es sweep bajista; high > open si es alcista). Si NO hay
    session_open en el dict, se degrada al comportamiento R1 (solo sweep en
    contra) para no romper pipelines que aun no lo calculan.

    Devuelve (presente, broke_open) para que la UI informe si la trampa fue
    mas alla del open del dia.
    """
    if not _has_htf_bias(bias):
        return False, False
    sw = _sweep_dir(estructura, (htf, exec_tf))
    opposes = (bias == "BULLISH" and sw == "down") or (bias == "BEARISH" and sw == "up")
    if not opposes:
        return False, False

    session_open = estructura.get("D1", {}).get("session_open")
    if session_open is None:
        # Sin ancla de open del dia: comportamiento R1 (sweep en contra basta).
        return True, False

    # Con ancla: exigir que el sweep haya roto el open del dia.
    m15 = estructura.get(exec_tf, {})
    if bias == "BULLISH":
        # Manipulacion bajista: el low del TF de ejecucion debe haber roto el open.
        low = m15.get("sweep_low") if m15.get("sweep_low") is not None else m15.get("low")
        broke = low is not None and float(low) < float(session_open)
    else:
        high = m15.get("sweep_high") if m15.get("sweep_high") is not None else m15.get("high")
        broke = high is not None and float(high) > float(session_open)
    return broke, broke


def compute_session_open(d1_df) -> float | None:
    """Precio de apertura del dia ANTERIOR ya cerrado (sin look-ahead).

    Recibe un DataFrame D1 ordenado cronologicamente. Usa la ULTIMA vela del
    DataFrame asumiendo que el llamador YA dejo fuera la vela del dia en curso
    (regla dura del libro 08: open = vela ya cerrada, no la del dia en curso).
    Si el DataFrame tiene la vela en curso, el llamador debe pasar el slice
    hasta iloc[-2]. Devuelve None si no hay datos.
    """
    if d1_df is None or len(d1_df) == 0:
        return None
    try:
        return float(d1_df["open"].iloc[-1])
    except (KeyError, IndexError, ValueError, TypeError):
        return None


def _phase_d(estructura: dict, bias: str, exec_tf: str, m_present: bool) -> tuple[bool, str]:
    """D — Distribution: CHOCH/BOS A FAVOR + zona FVG/OB en LTF, TRAS M.

    Regla dura del contrato: D requiere que M haya ocurrido (after(M)). Si M
    es False, D no puede ser True (no se adelanta el futuro).
    Devuelve (presente, zona) donde zona es la lectura del BOS/CHOCH.
    """
    if not m_present:
        return False, "no"
    m15 = estructura.get(exec_tf, {})
    bos = _bos_exec(estructura, exec_tf)
    choch = str(m15.get("choch_status", "-")).lower()
    choch_bull = choch in ("choch_bullish", "bullish", "active") and bias == "BULLISH"
    choch_bear = choch in ("choch_bearish", "bearish", "active") and bias == "BEARISH"
    bos_alc = bos == "alcista" and bias == "BULLISH"
    bos_baj = bos == "bajista" and bias == "BEARISH"
    if not (choch_bull or choch_bear or bos_alc or bos_baj):
        return False, bos
    fvg = str(m15.get("fvg_state", "-")).lower() not in ("-", "none", "nan", "")
    ob = str(m15.get("ob_dir", "-")).lower() not in ("-", "none", "nan", "")
    if not (fvg or ob):
        return False, bos
    return True, bos


def build_po3_state(
    estructura: dict,
    bias: str,
    votes: dict | None = None,
    exec_tf: str = "M15",
    htf: str = "H4",
) -> PO3State:
    """Construye el estado PO3 determinista (sin look-ahead) a partir de la
    estructura ya calculada con velas CERRADAS.

    Parametros
    ----------
    estructura : dict por TF con claves esperadas:
        {tf: {"trend", "sweep_up", "sweep_down", "bos_dir", "bos_status",
              "choch_status", "fvg_state", "ob_dir", "session_range"}}
    bias : str sesgo HTF ("BULLISH" | "BEARISH" | "NEUTRAL" | "")
    votes : dict de votos L/S del motor (opcional)
    exec_tf, htf : timeframes de ejecucion y contexto
    """
    a = _phase_a(estructura, bias, htf)
    m, broke_open = _phase_m(estructura, bias, htf, exec_tf)
    d, _ = _phase_d(estructura, bias, exec_tf, m)

    dir_setup = _dir_setup(bias, votes, estructura.get(exec_tf, {}), counter_trend=False)
    aligned = bool(dir_setup) and dir_setup != "NEUTRAL" and (
        (dir_setup == "LONG" and bias == "BULLISH")
        or (dir_setup == "SHORT" and bias == "BEARISH")
    )
    if not _has_htf_bias(bias):
        aligned = False

    reasons: list[str] = []
    if not a:
        reasons.append("A (acumulacion: falta sesgo HTF o rango)")
    if not m:
        reasons.append("M (manipulacion: falta sweep en contra del sesgo)")
    if a and m and not d:
        reasons.append("D (distribucion: falta CHOCH/BOS a favor + FVG/OB tras M)")
    if not aligned:
        reasons.append("alineacion (setup no a-favor del HTF -> Turtle Soup, no PO3)")

    complete = a and m and d and aligned
    return PO3State(
        A=a,
        M=m,
        D=d,
        complete=complete,
        direction=dir_setup,
        aligned=aligned,
        broke_open=broke_open,
        incomplete_reason=reasons,
    )


@dataclass
class Po3MotorConfig:
    """Contexto que necesita compute_po3_complete para delegar en build_po3_state.

    El llamador (canonical.evaluate_signals) lo popula con el sesgo HTF ya
    calculado, los votos L/S del LTF y los timeframes de ejecución/contexto.
    """

    bias: str = ""               # sesgo HTF: "BULLISH" | "BEARISH" | "NEUTRAL" | ""
    votes: dict | None = None    # votos L/S del motor (opcional)
    exec_tf: str = "M15"         # timeframe de ejecución
    htf: str = "H4"              # timeframe de contexto


def compute_po3_complete(
    structure_data: dict | None,
    config: Po3MotorConfig | None = None,
) -> bool | None:
    """¿El ciclo PO3/AMD estaba COMPLETO al momento de la entrada?

    Función PURA: no accede a disco ni a bar_index, no muta nada. Solo lee
    `structure_data` (dict por TF, velas CERRADAS) y delega en
    `build_po3_state`.

    Devuelve
    --------
    bool | None :
        True  -> PO3 completo (A/M/D + alineación a-favor) en la dirección.
        False -> ciclo presente pero incompleto/judas (falta D o desalineado).
        None  -> sin datos de estructura (comportamiento histórico intacto).
    """
    if not structure_data:
        return None
    cfg = config if config is not None else Po3MotorConfig()
    state = build_po3_state(
        structure_data,
        bias=cfg.bias,
        votes=cfg.votes,
        exec_tf=cfg.exec_tf,
        htf=cfg.htf,
    )
    return bool(state.complete)


def evaluate_po3(
    model: str,
    estructura: dict,
    bias: str,
    votes: dict | None = None,
    ts: Any = None,
    exec_tf: str = "M15",
    htf: str = "H4",
    counter_trend: bool = False,
) -> dict[str, Any]:
    """Adaptador `evaluate(model="po3")` para ict_backtest/rules.evaluate.

    Mantiene la MISMA firma que evaluate() de rules.py (model primero) para
    que engine/backtest lo invoque sin ramas especiales. Separado de Turtle
    Soup: aca counter_trend SIEMPRE es False (PO3 es a-favor; la contratendencia
    es responsabilidad de Turtle Soup en rules.py).
    """
    if model != "po3":
        raise ValueError(f"evaluate_po3 solo acepta model='po3', recibio: {model}")
    st = build_po3_state(estructura, bias, votes, exec_tf=exec_tf, htf=htf)
    checks = [
        f"OK: Sesgo HTF: {bias}." if st.A else "FALTA: A (sesgo HTF o rango de sesion).",
        f"OK: Sweep en contra del sesgo (M){' + roto open del dia' if st.broke_open else ''}." if st.M else "FALTA: M (sweep en contra del sesgo).",
        f"OK: CHOCH/BOS a favor + FVG/OB (D)." if st.D else "FALTA: D (CHOCH/BOS a favor + zona tras M).",
        f"OK: Direccion alineada ({st.direction})." if st.aligned else "FALTA: alineacion a-favor (seria Turtle Soup).",
    ]
    passed = sum(1 for c in checks if c.startswith("OK:"))
    return {
        "model": "po3",
        "phases": st.phases_present(),
        "complete": st.complete,
        "direction": st.direction,
        "aligned": st.aligned,
        "broke_open": st.broke_open,
        "incomplete_reason": st.incomplete_reason,
        "checks": checks,
        "passed": passed,
        "total": len(checks),
        "ready": st.complete,
    }
