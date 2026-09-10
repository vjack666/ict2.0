"""Lanzador seguro del dashboard mecánico local.

No crea ni arma el servicio de trading: solo aloja la interfaz HTTP loopback.
"""
from __future__ import annotations

import argparse
import atexit
import os
import sys
import webbrowser
from pathlib import Path

CANONICAL_AUTHORITY = False
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PID_FILE = ROOT / "reports" / "mechanical_bot" / "dashboard.pid"
# The same explicitly selected terminal that supplies the daily EURUSD feed.
# Passing it to the adapter prevents MetaTrader5 from silently attaching to a
# different installed terminal/account.
DEFAULT_TERMINAL_PATH = Path(r"C:\Program Files\FundedNext MT5 Terminal\terminal64.exe")


def pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def acquire_pid(pid_file: Path) -> bool:
    """Atomically claim the local dashboard PID file, recovering only stale files."""
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    if pid_file.exists():
        try:
            existing = int(pid_file.read_text(encoding="utf-8").strip())
        except ValueError:
            existing = 0
        if pid_is_running(existing):
            return False
        pid_file.unlink(missing_ok=True)
    try:
        descriptor = os.open(str(pid_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(str(os.getpid()))
    return True


def release_pid(pid_file: Path) -> None:
    try:
        if pid_file.is_file() and int(pid_file.read_text(encoding="utf-8").strip()) == os.getpid():
            pid_file.unlink()
    except (OSError, ValueError):
        return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inicia solo el dashboard local del bot mecánico.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8780, type=int)
    parser.add_argument("--pid-file", type=Path, default=DEFAULT_PID_FILE)
    parser.add_argument("--terminal-path", type=Path, default=DEFAULT_TERMINAL_PATH,
                        help="Terminal MT5 que debe usarse para el dashboard y la cuenta detectada.")
    parser.add_argument("--open-browser", action="store_true")
    parser.add_argument("--execution-enabled", action="store_true", help="Permite al adaptador enviar órdenes solo después de pulsar Encender bot.")
    args = parser.parse_args(argv)
    if args.host != "127.0.0.1":
        parser.error("El dashboard solo puede escuchar en 127.0.0.1")
    if not acquire_pid(args.pid_file):
        print(f"Dashboard ya está en ejecución (PID: {args.pid_file}).")
        return 0
    atexit.register(release_pid, args.pid_file)
    sys.path.insert(0, str(ROOT))
    from mechanical_bot.core import BotConfig
    from mechanical_bot.service import MechanicalBotService
    from scripts.mechanical_bot_dashboard import create_server

    # Connecting to MT5 is read-only until the adapter receives an OPEN/CLOSE
    # action.  A missing terminal/library leaves the dashboard useful for
    # analysis and clearly reports the unavailable account.
    adapter = None
    try:
        from mechanical_bot.mt5_adapter import MT5Adapter
        terminal_path = str(args.terminal_path) if args.terminal_path.is_file() else None
        adapter = MT5Adapter(terminal_path=terminal_path, execution_enabled=args.execution_enabled,
                             server_utc_offset_seconds=int(3 * 3600))
        adapter.connect()
    except Exception as exc:
        print(f"MT5 no disponible para el dashboard: {exc}")
        adapter = None
    service = MechanicalBotService(BotConfig(enabled=True), adapter=adapter)

    server = create_server(service, host=args.host, port=args.port)
    url = f"http://{args.host}:{server.server_port}"
    print(f"Dashboard mecánico listo: {url}")
    print("Estado inicial seguro: OFF; no se inició ni armó trading.")
    print("Ejecución de órdenes: habilitada" if args.execution_enabled and adapter is not None else "Ejecución de órdenes: deshabilitada")
    if args.open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        service.stop_runner()
        if adapter is not None:
            adapter.close()
        release_pid(args.pid_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
