"""Launch ICT's local desktop terminal. Opening it never arms the bot."""
from __future__ import annotations

import argparse
import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import webbrowser
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def open_desktop(url):
    edge = next((p for p in [Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
                            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft/Edge/Application/msedge.exe"] if p.is_file()), None)
    if edge:
        subprocess.Popen([str(edge), f"--app={url}", "--window-size=1480,1000"])
    else:
        webbrowser.open(url)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8790)
    parser.add_argument("--terminal-path", default=r"C:\Program Files\FundedNext MT5 Terminal\terminal64.exe")
    parser.add_argument("--desktop", action="store_true")
    parser.add_argument("--server-utc-offset-hours", type=float, default=3,
                        help="Desfase explícito del reloj MT5 observado: +3 h el 2026-09-07; ajustar si cambia broker/DST")
    parser.add_argument("--execution-enabled", action="store_true", help="Permite ejecución mecánica después de armado manual y snapshot válido")
    parser.add_argument("--demo-test", action="store_true", help="Prueba armable solo en la cuenta DEMO fijada; permite esperar snapshot")
    args = parser.parse_args()
    url = f"http://127.0.0.1:{args.port}"
    try:
        with urlopen(url + "/api/state?bars_version=0&engine_version=0", timeout=1) as response:
            existing = json.load(response)
        if existing.get("application_id") == "ICT_DESKTOP_TERMINAL_V1":
            if args.execution_enabled and not existing.get("bot", {}).get("execution_enabled"):
                raise SystemExit("La instancia abierta tiene ejecución deshabilitada; no se cambia su autoridad al reabrirla.")
            if args.desktop:
                open_desktop(url)
            return
    except (OSError, ValueError):
        pass
    from runtime.desktop_terminal.backend import LockedMT5, TerminalRuntime
    from runtime.desktop_terminal.server import create_server, UI_DIST
    from mechanical_bot.core import BotConfig
    from mechanical_bot.service import MechanicalBotService
    from mechanical_bot.mt5_adapter import MT5Adapter
    if not (UI_DIST / "index.html").is_file():
        raise SystemExit("Falta build. Ejecuta npm run build en runtime/desktop_terminal/ui.")
    mt5, adapter, error = None, None, None
    try:
        if not Path(args.terminal_path).is_file():
            raise RuntimeError("El terminal seleccionado no existe; no se permite fallback")
        import MetaTrader5
        mt5 = LockedMT5(MetaTrader5)
        adapter = MT5Adapter(terminal_path=args.terminal_path, execution_enabled=args.execution_enabled, mt5=mt5,
                             server_utc_offset_seconds=int(args.server_utc_offset_hours * 3600))
        adapter.connect()
        if args.demo_test:
            if not args.execution_enabled:
                raise RuntimeError("DEMO_TEST_REQUIRES_EXECUTION_FLAG")
            account = adapter.account_status()
            if not account.is_demo:
                raise RuntimeError("DEMO_TEST_REQUIRES_DEMO_ACCOUNT")
            adapter.configure_demo_guard(account.login, account.server)
        if not mt5.symbol_select("EURUSD", True):
            raise RuntimeError("EURUSD no está disponible en el terminal seleccionado")
    except Exception as exc:
        error, adapter, mt5 = str(exc), None, None
    service = MechanicalBotService(BotConfig(enabled=True), adapter=adapter)
    service.demo_wait_enabled = bool(args.demo_test and adapter is not None)
    # ICT Terminal treats the documented London/New York window as an entry
    # gate in every mode. Arming may still start the scan loop outside it.
    service.entry_sessions_enabled = True
    runtime = TerminalRuntime(mt5, service, server_offset_seconds=int(args.server_utc_offset_hours * 3600))
    try:
        server = create_server(runtime, args.port)
    except OSError:
        if adapter:
            adapter.close()
        raise SystemExit(f"Puerto {args.port} ocupado. No se inició una segunda instancia.")
    if error:
        runtime.event("MT5_UNAVAILABLE", error)
    runtime.start()
    url = f"http://127.0.0.1:{server.server_port}"
    print(json.dumps({"url": url, "pid": os.getpid(), "execution_enabled": args.execution_enabled,
                      "bot_state": "OFF", "mt5_error": error}), flush=True)
    if args.desktop:
        open_desktop(url)
    try:
        server.serve_forever(poll_interval=.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        runtime.close()
        if adapter:
            adapter.close()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
