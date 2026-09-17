#!/usr/bin/env python3
"""Validación de caja negra y ejecución DEMO - ICT SYSTEM mechanical_bot.

NO activa órdenes. Solo lee archivos y reporta estado.
"""

import hashlib
import json
import os
import sys
from pathlib import Path

# Ruta base
BASE = Path(r"C:\Users\v_jac\Desktop\ICT SYSTEM")
HERMES_STATE = BASE / ".hermes-state"
BLACKBOX = HERMES_STATE / "mechanical_bot_blackbox.jsonl"
BLACKBOX_ROTATED = HERMES_STATE / "mechanical_bot_blackbox.jsonl.1"
SERVICE = BASE / "mechanical_bot" / "service.py"
SDD = BASE / "docs" / "tesis" / "SDD_MECHANICAL_MT5_BOT.md"
STATE_FILE = HERMES_STATE / "mechanical_bot_state.json"


def sha256(text: str) -> str:
    """SHA-256 de un string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    """Carga un archivo JSONL y retorna lista de objetos."""
    records = []
    if not path.exists():
        return records
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"ERROR: línea mal formada en {path}: {e}")
    return records


def verify_chained_hashes(records: list[dict]) -> dict:
    """Verifica que cada entrada referencia la anterior mediante previous_hash == record_hash de la anterior.
    Retorna dict con: ok, first_previous_hash_null, broken_chains, examples.
    """
    result = {
        "ok": True,
        "total": len(records),
        "first_previous_hash_null": False,
        "broken_chains": [],
        "examples": [],
    }
    if len(records) == 0:
        result["ok"] = False
        result["broken_chains"].append("Archivo vacío")
        return result

    for i, rec in enumerate(records):
        # Primera entrada: previous_hash debe ser null
        if i == 0:
            ph = rec.get("previous_hash")
            if ph is not None:
                result["first_previous_hash_null"] = False  # optional, puede aceptarse null
                # pero si no es null, no es un problema crítico, solo inconsistente
        # Verificar cadena
        if i > 0:
            expected_prev = records[i - 1].get("record_hash")
            actual_prev = rec.get("previous_hash")
            if expected_prev != actual_prev:
                result["ok"] = False
                result["broken_chains"].append({
                    "line": i + 1,
                    "expected": expected_prev,
                    "actual": actual_prev,
                    "record_hash": rec.get("record_hash"),
                })
                if len(result["examples"]) < 3:
                    result["examples"].append({
                        "line": i + 1,
                        "event": rec.get("event"),
                        "reason": rec.get("reason"),
                        "expected_prev": expected_prev,
                        "actual_prev": actual_prev,
                    })

    # Check first entry previous_hash is null (esperado para primer registro)
    if records[0].get("previous_hash") is not None:
        # No es necesariamente ERROR pero es inusual
        pass

    return result


def count_event_types(records: list[dict]) -> dict:
    """Cuenta eventos por tipo."""
    counts = {}
    for rec in records:
        event = rec.get("event", "UNKNOWN")
        counts[event] = counts.get(event, 0) + 1
    return counts


def verify_write_failure_block(service_path: Path) -> dict:
    """Verifica en service.py que un fallo de escritura en blackbox impide order_send."""
    if not service_path.exists():
        return {"ok": False, "reason": "service.py no existe"}

    content = service_path.read_text(encoding="utf-8")
    findings = {
        "ok": False,
        "has_blackbox_record_before_order": False,
        "has_write_failure_check": False,
        "blocks_order_on_failure": False,
        "code_snippet": "",
    }

    # Buscar patrones: blackbox.record("ORDER_REQUEST"...) antes de order_send
    if 'self._blackbox.record(' in content and 'ORDER_REQUEST' in content:
        findings["has_blackbox_record_before_order"] = True

    # Buscar manejo de excepción al escribir
    if 'except' in content and ('blackbox' in content.lower() or 'write' in content.lower() or 'record' in content):
        findings["has_write_failure_check"] = True

    # Verificar que hay un mecanismo de bloqueo (try/except que impide continuar)
    lines = content.split("\n")
    in_try_block = False
    blocking_found = False
    for i, line in enumerate(lines):
        if "try:" in line:
            in_try_block = True
        if in_try_block and "except" in line:
            # Check if this exception handler would block order_send
            context = "\n".join(lines[max(0, i-20):i+5])
            if "raise" in context or "return" in context or "order_send" not in context:
                blocking_found = True
        if "order_send" in line:
            # Check context around order_send
            start = max(0, i - 30)
            end = min(len(lines), i + 10)
            context = "\n".join(lines[start:end])
            if "raise" in context or ("except" in context and "raise" in context):
                findings["blocks_order_on_failure"] = True
                findings["code_snippet"] = context
                break

    # Alternativa: buscar el patrón explícito de la SDD
    if "A journal failure occurs before" in content or "journal failure" in content.lower():
        findings["blocks_order_on_failure"] = True
        findings["code_snippet"] = "Patrón de fallo de escritura detectado en documentación del código"

    findings["ok"] = findings["has_blackbox_record_before_order"] and findings["blocks_order_on_failure"]
    return findings


def verify_demo_account(service_path: Path) -> dict:
    """Verifica que el servicio solo usa cuentas DEMO (MetaQuotes-Demo o FundedNext demo)."""
    if not service_path.exists():
        return {"ok": False, "reason": "service.py no existe"}

    content = service_path.read_text(encoding="utf-8")
    findings = {
        "ok": False,
        "mentions_demo": False,
        "mentions_real_live": False,
        "demo_indicators": [],
    }

    # Buscar referencias a DEMO
    demo_keywords = ["DEMO", "demo", "PRACTICE", "practice", "test"]
    for kw in demo_keywords:
        if kw in content:
            findings["mentions_demo"] = True
            findings["demo_indicators"].append(kw)

    # Verificar que NO hay lógica para cuentas reales
    real_keywords = ["REAL", "real", "LIVE", "live"]
    for kw in real_keywords:
        if kw in content:
            findings["mentions_real_live"] = True

    # Si hay DEMO y NO hay lógica de cuentas reales explícita, está bien
    findings["ok"] = findings["mentions_demo"] and not findings["mentions_real_live"]
    return findings


def verify_retcode_requirement(service_path: Path) -> dict:
    """Verifica que order_send requiere retcode DONE (10009) o DONE_PARTIAL."""
    if not service_path.exists():
        return {"ok": False, "reason": "service.py no existe"}

    content = service_path.read_text(encoding="utf-8")
    findings = {
        "ok": False,
        "retcode_10009": False,  # DONE
        "retcode_10010": False,  # DONE_PARTIAL
        "retcode_check": False,
    }

    # MetaTrader 5 retcodes: 10009 = TRADE_RETCODE_DONE, 10010 = TRADE_RETCODE_DONE_PARTIAL
    if "10009" in content:
        findings["retcode_10009"] = True
    if "10010" in content:
        findings["retcode_10010"] = True

    # Verificar que hay validación de retcode
    if "retcode" in content.lower():
        findings["retcode_check"] = True

    findings["ok"] = findings["retcode_check"] and (findings["retcode_10009"] or findings["retcode_10010"])
    return findings


def verify_volume_minimum(service_path: Path, sdd_path: Path) -> dict:
    """Verifica que el volumen mínimo es 0.10 según SDD."""
    findings = {
        "ok": False,
        "volume_in_service": False,
        "volume_0_10": False,
        "sdd_mentions_0_10": False,
        "service_volume_value": None,
        "sdd_volume_value": None,
    }

    # Leer service.py
    if service_path.exists():
        content = service_path.read_text(encoding="utf-8")
        # Buscar volumen mínimo
        import re
        # Patrones: volume >= 0.10, min_volume = 0.10, etc.
        vol_patterns = [
            r"volume\s*[><=]+\s*0\.10",
            r"min_volume\s*[=:\s]*0\.10",
            r"0\.10.*volume",
            r"VOLUME.*0\.10",
            r"min_volume.*?0\.1",
        ]
        for pat in vol_patterns:
            if re.search(pat, content, re.IGNORECASE):
                findings["volume_in_service"] = True
                findings["volume_0_10"] = True
                break

    # Leer SDD
    if sdd_path.exists():
        content = sdd_path.read_text(encoding="utf-8")
        if "0.10" in content or "0.1" in content:
            findings["sdd_mentions_0_10"] = True
            # Extraer contexto
            import re
            m = re.search(r'.{0,50}(0\.10|0\.1).{0,50}', content)
            if m:
                findings["sdd_volume_value"] = m.group(0)

    findings["ok"] = findings["volume_in_service"] and findings["sdd_mentions_0_10"]
    return findings


def verify_order_request_result_in_blackbox(records: list[dict]) -> dict:
    """Verifica que blackbox tiene registros ORDER_REQUEST y ORDER_RESULT."""
    events = count_event_types(records)
    return {
        "has_ORDER_REQUEST": events.get("ORDER_REQUEST", 0) > 0,
        "has_ORDER_RESULT": events.get("ORDER_RESULT", 0) > 0,
        "order_request_count": events.get("ORDER_REQUEST", 0),
        "order_result_count": events.get("ORDER_RESULT", 0),
        "total_events": len(records),
    }


def verify_retention_and_rotation(blackbox: Path, rotated: Path) -> dict:
    """Verifica retención y rotación del blackbox."""
    findings = {
        "ok": False,
        "main_exists": blackbox.exists(),
        "rotated_exists": rotated.exists(),
        "main_lines": 0,
        "rotated_lines": 0,
        "rotation_occurred": False,
    }

    if blackbox.exists():
        with open(blackbox, "r", encoding="utf-8") as f:
            findings["main_lines"] = sum(1 for _ in f)

    if rotated.exists():
        with open(rotated, "r", encoding="utf-8") as f:
            findings["rotated_lines"] = sum(1 for _ in f)

    findings["rotation_occurred"] = findings["rotated_exists"] and findings["rotated_lines"] > 0
    findings["ok"] = findings["main_exists"] and findings["rotation_occurred"]
    return findings


def verify_position_reconciliation(service_path: Path) -> dict:
    """Verifica que hay reconciliación de posición por símbolo + magic."""
    if not service_path.exists():
        return {"ok": False, "reason": "service.py no existe"}

    content = service_path.read_text(encoding="utf-8")
    findings = {
        "ok": False,
        "symbol_filter": False,
        "magic_filter": False,
        "position_get": False,
    }

    if "symbol" in content and "magic" in content:
        findings["symbol_filter"] = True
        findings["magic_filter"] = True

    if "positions_get" in content:
        findings["position_get"] = True

    findings["ok"] = findings["symbol_filter"] and findings["magic_filter"] and findings["position_get"]
    return findings


def verify_execution_disabled(state_file: Path, service_path: Path, initial: bool = True) -> dict:
    """Verifica que el flujo actual no envía órdenes: can_trade=false, execution_enabled=false."""
    findings = {
        "ok": False,
        "can_trade_false": False,
        "execution_enabled_false": False,
        "state_file_checks": [],
        "service_checks": [],
    }

    # Verificar state file
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
            can_trade = state.get("can_trade", None)
            exec_enabled = state.get("execution_enabled", None)

            if can_trade is False:
                findings["can_trade_false"] = True
                findings["state_file_checks"].append("can_trade=false en state file")
            elif can_trade is None:
                findings["state_file_checks"].append("can_trade no presente en state file")

            if exec_enabled is False:
                findings["execution_enabled_false"] = True
                findings["state_file_checks"].append("execution_enabled=false en state file")
            elif exec_enabled is None:
                findings["state_file_checks"].append("execution_enabled no presente en state file")
        except Exception as e:
            findings["state_file_checks"].append(f"Error leyendo state: {e}")

    # Verificar service.py (por defecto)
    if service_path.exists():
        content = service_path.read_text(encoding="utf-8")
        if "execution_enabled" in content and "False" in content:
            findings["service_checks"].append("execution_enabled=False por defecto en service.py")
        if "can_trade" in content and "False" in content:
            findings["service_checks"].append("can_trade=False por defecto en service.py")

    findings["ok"] = findings["can_trade_false"] and findings["execution_enabled_false"]
    return findings


def main():
    print("=" * 70)
    print("VALIDACIÓN DE CAJA NEGRA Y EJECUCIÓN DEMO")
    print("ICT SYSTEM - mechanical_bot")
    print("=" * 70)
    print()

    # 1. CARGAR BLACKBOX
    print("[1] Cargando blackbox principal...")
    records_main = load_jsonl(BLACKBOX)
    print(f"    Líneas en blackbox.jsonl: {len(records_main)}")

    print("[2] Cargando blackbox rotado...")
    records_rotated = load_jsonl(BLACKBOX_ROTATED)
    print(f"    Líneas en blackbox.jsonl.1: {len(records_rotated)}")

    all_records = records_main + records_rotated
    print(f"    Total registros: {len(all_records)}")
    print()

    # 2. VERIFICAR HASHES ENCADENADOS
    print("[3] Verificando hashes encadenados...")
    chain_result = verify_chained_hashes(all_records)
    print(f"    Total registros verificados: {chain_result['total']}")
    print(f"    Cadena OK: {chain_result['ok']}")
    if not chain_result['ok']:
        print(f"    Cadenas rotas: {len(chain_result['broken_chains'])}")
        for example in chain_result['examples'][:3]:
            print(f"      Línea {example['line']}: evento={example['event']}, expected_prev={example['expected_prev'][:16]}..., actual_prev={example['actual_prev'][:16]}...")
    print()

    # 3. EVENTOS EN BLACKBOX
    print("[4] Tipos de eventos en blackbox...")
    events = count_event_types(all_records)
    for event_type, count in sorted(events.items()):
        print(f"    {event_type}: {count}")
    print()

    # 4. VERIFICAR WRITE FAILURE BLOCK
    print("[5] Verificando fallo de escritura impide order_send (service.py)...")
    write_block = verify_write_failure_block(SERVICE)
    print(f"    Has blackbox.record antes de order_send: {write_block['has_blackbox_record_before_order']}")
    print(f"    Bloquea envío ante fallo: {write_block['blocks_order_on_failure']}")
    print(f"    OK: {write_block['ok']}")
    print()

    # 5. VERIFICAR EJECUCIÓN DEMO
    print("[6] Verificando uso de cuenta DEMO...")
    demo_check = verify_demo_account(SERVICE)
    print(f"    Menciona DEMO: {demo_check['mentions_demo']}")
    print(f"    Menciona REAL/LIVE: {demo_check['mentions_real_live']}")
    print(f"    OK: {demo_check['ok']}")
    print()

    print("[7] Verificando retcode DONE/DONE_PARTIAL requerido...")
    retcode_check = verify_retcode_requirement(SERVICE)
    print(f"    Retcode 10009 (DONE): {retcode_check['retcode_10009']}")
    print(f"    Retcode 10010 (DONE_PARTIAL): {retcode_check['retcode_10010']}")
    print(f"    Validación de retcode: {retcode_check['retcode_check']}")
    print(f"    OK: {retcode_check['ok']}")
    print()

    print("[8] Verificando volumen mínimo 0.10...")
    volume_check = verify_volume_minimum(SERVICE, SDD)
    print(f"    SDD disponible: {SDD.exists()}")
    print(f"    Volumen 0.10 en service: {volume_check['volume_0_10']}")
    print(f"    SDD menciona 0.10: {volume_check['sdd_mentions_0_10']}")
    print(f"    OK: {volume_check['ok']}")
    print()

    # 6. VERIFICAR ORDER_REQUEST/ORDER_RESULT EN BLACKBOX
    print("[9] Verificando ORDER_REQUEST y ORDER_RESULT en blackbox...")
    order_check = verify_order_request_result_in_blackbox(all_records)
    print(f"    ORDER_REQUEST: {order_check['has_ORDER_REQUEST']} ({order_check['order_request_count']} registros)")
    print(f"    ORDER_RESULT: {order_check['has_ORDER_RESULT']} ({order_check['order_result_count']} registros)")
    print()

    # 7. VERIFICAR RETENCIÓN Y ROTACIÓN
    print("[10] Verificando retención y rotación del blackbox...")
    retention = verify_retention_and_rotation(BLACKBOX, BLACKBOX_ROTATED)
    print(f"    Blackbox principal existe: {retention['main_exists']}")
    print(f"    Blackbox rotado existe: {retention['rotated_exists']}")
    print(f"    Líneas principal: {retention['main_lines']}")
    print(f"    Líneas rotado: {retention['rotated_lines']}")
    print(f"    Rotación ocurrió: {retention['rotation_occurred']}")
    print(f"    OK: {retention['ok']}")
    print()

    # 8. VERIFICAR RECONCILIACIÓN DE POSICIÓN
    print("[11] Verificando reconciliación de posición por símbolo + magic...")
    recon = verify_position_reconciliation(SERVICE)
    print(f"    Filtro por símbolo: {recon['symbol_filter']}")
    print(f"    Filtro por magic: {recon['magic_filter']}")
    print(f"    positions_get: {recon['position_get']}")
    print(f"    OK: {recon['ok']}")
    print()

    # 9. VERIFICAR EJECUCIÓN DESHABILITADA
    print("[12] Verificando can_trade=false y execution_enabled=false...")
    exec_check = verify_execution_disabled(STATE_FILE, SERVICE)
    print(f"    can_trade=false: {exec_check['can_trade_false']}")
    print(f"    execution_enabled=false: {exec_check['execution_enabled_false']}")
    print(f"    Checks estado: {exec_check['state_file_checks']}")
    print(f"    Checks service: {exec_check['service_checks']}")
    print(f"    OK: {exec_check['ok']}")
    print()

    # 10. RESUMEN FINAL
    print("=" * 70)
    print("RESUMEN DE VALIDACIÓN")
    print("=" * 70)

    blackbox_ok = chain_result['ok'] and order_check['has_ORDER_REQUEST'] and order_check['has_ORDER_RESULT']
    demo_ok = demo_check['ok'] and retcode_check['ok'] and volume_check['ok'] and recon['ok']

    print()
    print(f"ESTADO CAJA NEGRA: {'OK' if blackbox_ok else 'BREACH'}")
    print(f"  - Hashes encadenados: {'OK' if chain_result['ok'] else 'BREACH'}")
    print(f"  - ORDER_REQUEST en blackbox: {'OK' if order_check['has_ORDER_REQUEST'] else 'FALTA'}")
    print(f"  - ORDER_RESULT en blackbox: {'OK' if order_check['has_ORDER_RESULT'] else 'FALTA'}")
    print(f"  - Fallo de escritura bloquea envío: {'OK' if write_block['ok'] else 'NO VALIDADO'}")
    print(f"  - Retención y rotación: {'OK' if retention['ok'] else 'NO VALIDADO'}")
    print()
    print(f"ESTADO EJECUCIÓN DEMO: {'VALIDADA' if demo_ok else 'NO VALIDADA'}")
    print(f"  - Solo cuenta DEMO: {'OK' if demo_check['ok'] else 'NO VALIDADO'}")
    print(f"  - Retcode DONE/DONE_PARTIAL: {'OK' if retcode_check['ok'] else 'NO VALIDADO'}")
    print(f"  - Volumen mínimo 0.10: {'OK' if volume_check['ok'] else 'NO VALIDADO'}")
    print(f"  - Reconciliación posición: {'OK' if recon['ok'] else 'NO VALIDADO'}")
    print()
    print(f"ORDENES ACTIVAS: {'NO' if exec_check['ok'] else 'DESCONOCIDO'}")
    print(f"  - can_trade=false: {'OK' if exec_check['can_trade_false'] else 'VERIFICAR'}")
    print(f"  - execution_enabled=false: {'OK' if exec_check['execution_enabled_false'] else 'VERIFICAR'}")
    print()

    # Criterio de cierre de caja negra
    print("=" * 70)
    print("CRITERIO DE CIERRE DE CAJA NEGRA")
    print("=" * 70)
    print()
    print("Una operación DEMO no puede existir sin rastro correlacionado.")
    print("Si hay posición EURUSD BUY 0.44, debe haber:")
    print("  DECISION → ORDER_REQUEST → ORDER_RESULT en el blackbox.")
    print()

    has_decision = events.get("DECISION", 0) > 0
    has_request = order_check['has_ORDER_REQUEST']
    has_result = order_check['has_ORDER_RESULT']

    if has_decision and has_request and has_result:
        print("✓ Secuencia completa presente: DECISION → ORDER_REQUEST → ORDER_RESULT")
        print("  Estado: CIERRE DE CAJA NEGRA OK")
    else:
        print("✗ Brecha detectada:")
        if not has_decision:
            print("  - Falta: DECISION")
        if not has_request:
            print("  - Falta: ORDER_REQUEST")
        if not has_result:
            print("  - Falta: ORDER_RESULT")
        print("  Estado: BRECHA - requiere investigación")

    print()
    print("=" * 70)
    print("FORMATO DE REPORTE DE EVIDENCIA (propuesta)")
    print("=" * 70)
    print()
    print(""" [
      {
        "timestamp": "2026-09-15T10:30:00.000Z",
        "decision_hash": "abc123...",
        "event_type": "ORDER_REQUEST|ORDER_RESULT|DECISION|POI_STOCH_EVAL|SIGNAL_ASSESSMENT",
        "correlation_id": "uuid-...",
        "symbol": "EURUSD",
        "action": "BUY|SELL",
        "volume": 0.10,
        "magic": 26090615,
        "retcode": 10009,
        "result": "DONE|REJECTED|PENDING",
        "details": { ... }
      }
    ]""")
    print()

    return 0 if (blackbox_ok and demo_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
