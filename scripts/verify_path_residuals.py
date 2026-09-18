#!/usr/bin/env python3
"""Verifica paths residuales ejecutando el assignment de Path(__file__) de cada archivo
como script independiente — reproduce exactamente lo que sucede en runtime real."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (rel_path, variable_names_a_sondear)
TARGETS = [
    ("engine/data_feed.py", ["ROOT"]),
    ("engine/m15_evidence_assembler.py", ["_ROOT"]),
    ("engine/market_features.py", ["ROOT"]),
    ("mechanical_bot/service.py", ["ROOT"]),
    ("audits/codigo/a7_completion_audit.py", ["ROOT"]),
    ("audits/codigo/audit_stack.py", ["ROOT"]),
    ("audits/codigo/bootstrap.py", ["ROOT"]),
    ("audits/codigo/fvg_ob_funnel.py", ["ROOT"]),
    ("audits/codigo/mt5_operational_snapshot.py", ["ROOT"]),
    ("audits/codigo/mtf_replay_t7.py", ["ROOT"]),
    ("audits/codigo/mtf_seq_funnel.py", ["ROOT"]),
    ("audits/codigo/mtf_seq_funnel_a7.py", ["ROOT"]),
    ("audits/codigo/run_full_stack.py", ["ROOT"]),
    ("scripts/architecture_guard.py", ["ROOT"]),
    ("scripts/audit/audit_calib_h4d1_v3.py", ["BASE"]),
    ("scripts/audit/audit_extend_all_tf.py", ["BASE"]),
    ("scripts/audit/audit_train_h4d1.py", ["BASE"]),
    ("orchestration/mission_controller/router.py", ["ROOT"]),
    ("runtime/desktop_terminal/backend.py", ["ROOT"]),
    ("runtime/desktop_terminal/server.py", ["ROOT"]),
    ("reports/audits/experiments/wyckoff_ict_01/certification/reviewer2_methodology_audit.py", ["SCRIPT_DIR"]),
    ("reports/audits/experiments/wyckoff_ict_01/certification/reviewer3_statistical_audit.py", ["SCRIPT_DIR"]),
]


def run_assignment(rel: str, var_names: list[str]) -> tuple[bool, str]:
    """Ejecuta el assignment de Path(__file__) de un archivo y devuelve (ok, resultado_o_error)."""
    f = ROOT / rel
    if not f.exists():
        return False, f"MISSING: {f}"

    # Construye un script que:
    # 1. Define __file__ = path del archivo
    # 2. Ejecuta la línea del assignment
    # 3. Imprime el valor de la variable
    lines = f.read_text(encoding="utf-8").splitlines()
    assign_line = None
    for ln in lines:
        s = ln.strip()
        if any(s.startswith(v + " ") or s.startswith(v + "=") for v in var_names):
            assign_line = ln
            break

    if assign_line is None:
        return True, f"NO HAY asignación a {var_names} en este archivo (no es path bug)"

    # Script: definimos __file__ y ejecutamos la asignación
    script = (
        "import sys\n"
        "from pathlib import Path\n"
        + "__file__ = " + repr(str(f)) + "\n"
        + assign_line + "\n"
    )
    for v in var_names:
        script += f"print('{v}=' + str({v}))\n"

    r = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=10,
    )
    if r.returncode != 0:
        err = r.stderr.strip().splitlines()
        return False, f"ERROR al ejecutar: {err[-1] if err else '(sin stderr)'}"
    return True, r.stdout.strip()


def classify(result: str) -> str:
    """Clasifica el resultado como OK / PROBLEM / NO_ASIGNACION."""
    if "MISSING" in result or "ERROR" in result:
        return "ERROR"
    if "NO HAY" in result:
        return "NO_ASIGNACION"
    # Extraer los paths y verificar si están dentro de ROOT
    for line in result.splitlines():
        if "=" in line:
            _, val = line.split("=", 1)
            val = val.strip()
            try:
                p = Path(val)
                try:
                    p.relative_to(ROOT)
                    return "OK"
                except ValueError:
                    return f"PROBLEM: {val} apunta fuera de ROOT"
            except Exception:
                return f"PARSE_ERROR: {val}"
    return "UNKNOWN"


def main() -> int:
    print(f"ROOT = {ROOT}")
    print(f"archivos verificados: {len(TARGETS)}")
    print("=" * 70)

    ok_count = 0
    problem_count = 0
    no_assign_count = 0
    error_count = 0

    for rel, var_names in TARGETS:
        ok, result = run_assignment(rel, var_names)
        status = classify(result)
        print(f"\n--- {rel} [{status}] ---")
        print(result)

        if status == "OK":
            ok_count += 1
        elif status == "NO_ASIGNACION":
            no_assign_count += 1
        elif status.startswith("PROBLEM"):
            problem_count += 1
        else:
            error_count += 1

    print("\n" + "=" * 70)
    print(f"RESUMEN: {len(TARGETS)} archivos verificados")
    print(f"  OK (path correcto dentro de ROOT):      {ok_count}")
    print(f"  NO_ASIGNACION (no define ROOT/BASE):    {no_assign_count}")
    print(f"  PROBLEM (path apunta fuera de ROOT):   {problem_count}")
    print(f"  ERROR (no se pudo ejecutar):            {error_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
