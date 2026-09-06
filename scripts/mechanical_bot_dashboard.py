"""Panel local del bot mecánico MT5.

Rol: DELIVERY.  Este servidor solo enlaza controles locales con la interfaz del
servicio mecánico; no contiene reglas de entrada ni llama a MetaTrader5.
Escucha exclusivamente en loopback y arranca apagado.
"""
from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.parse import urlparse

CANONICAL_AUTHORITY = False
ROOT = Path(__file__).resolve().parents[1]
CHARTS = {
    "D1": ROOT / "reports" / "charts" / "EURUSD_D1_tradingview.png",
    "H4": ROOT / "reports" / "charts" / "EURUSD_H4_tradingview.png",
    "H1": ROOT / "reports" / "charts" / "EURUSD_H1_tradingview.png",
    "M15": ROOT / "reports" / "charts" / "EURUSD_M15_tradingview.png",
}
ACTIONS = {
    "analyze": ("analyze_options", "analyze"),
    "arm": ("arm", "start"),
    "disarm": ("disarm", "stop"),
    "close-cycle": ("close_cycle", "request_close_cycle"),
}


class MechanicalService(Protocol):
    def status(self) -> dict[str, Any]: ...


class UnavailableService:
    """Fail-closed fallback used until the separate service is installed."""

    reason = "MECHANICAL_SERVICE_UNAVAILABLE"

    def status(self) -> dict[str, Any]:
        return {
            "state": "OFF",
            "can_trade": False,
            "service_available": False,
            "reason": self.reason,
            "message": "El servicio mecánico no está disponible; no se envió ninguna orden.",
        }


def default_service() -> MechanicalService:
    """Late import prevents dashboard startup from arming or starting a bot."""
    try:
        from mechanical_bot.service import MechanicalBotService  # type: ignore[import-not-found]

        return MechanicalBotService()
    except (ImportError, ModuleNotFoundError):
        return UnavailableService()


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, default=str).encode("utf-8")


def _status(service: object) -> dict[str, Any]:
    method = getattr(service, "status", None)
    if not callable(method):
        return UnavailableService().status()
    result = method()
    if not isinstance(result, dict):
        raise TypeError("MECHANICAL_SERVICE_STATUS_MUST_BE_DICT")
    return result


def invoke_action(service: object, action: str) -> dict[str, Any]:
    """Call one explicit service action; unknown/absent methods fail closed."""
    if action not in ACTIONS:
        return {"ok": False, "error": "UNKNOWN_ACTION", "can_trade": False}
    for name in ACTIONS[action]:
        method = getattr(service, name, None)
        if callable(method):
            result = method()
            payload = result if isinstance(result, dict) else {"result": result}
            # ``can_trade`` remains the intelligent engine's policy.  The
            # standalone executor exposes its own explicit submission flag.
            return {"ok": True, "action": action, "can_trade": False, **payload}
    return {
        "ok": False,
        "action": action,
        "error": "MECHANICAL_SERVICE_ACTION_UNAVAILABLE",
        "can_trade": False,
    }


def dashboard_html() -> bytes:
    cards = "".join(
        f'<figure><figcaption>{tf}</figcaption><img src="/charts/{tf}" alt="Gráfica {tf}"></figure>'
        for tf in CHARTS
    )
    return f"""<!doctype html><html lang=\"es\"><meta charset=\"utf-8\">
<title>Bot mecánico MT5</title>
<style>body{{font-family:system-ui;margin:2rem;max-width:1200px;background:#10151d;color:#e7edf5}}button{{padding:.65rem;margin:.2rem}}pre{{background:#1c2530;padding:1rem;white-space:pre-wrap}}section{{margin-block:1rem}}figure{{display:inline-block;width:46%;margin:1%}}img{{width:100%;background:#fff}}.warn{{color:#ffd166}}</style>
<h1>Bot mecánico MT5</h1><p class=\"warn\">Control local. El dashboard no inicia trading al abrirse.</p>
<section><button onclick=\"act('analyze')\">Analizar opciones</button><button onclick=\"act('arm')\">Encender bot</button><button onclick=\"act('disarm')\">Apagar bot</button><button onclick=\"act('close-cycle')\">Cerrar ciclo</button></section>
<h2>Estado, cuenta y registro</h2><pre id=\"status\">Cargando…</pre>
<h2>Contexto y gráficas</h2><p>M5/M1 se muestran solo como diagnóstico: no vetan ni autorizan las acciones del bot.</p><div>{cards}</div>
<script>
async function load(){{const r=await fetch('/api/status');document.getElementById('status').textContent=JSON.stringify(await r.json(),null,2)}}
async function act(a){{const r=await fetch('/api/actions/'+a,{{method:'POST'}});document.getElementById('status').textContent=JSON.stringify(await r.json(),null,2);setTimeout(load,250)}}
load();setInterval(load,5000);
</script></html>""".encode("utf-8")


def make_handler(service: object) -> type[BaseHTTPRequestHandler]:
    class DashboardHandler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            try:
                if path == "/":
                    self._send(HTTPStatus.OK, dashboard_html(), "text/html; charset=utf-8")
                elif path == "/api/status":
                    self._send(HTTPStatus.OK, _json_bytes(_status(service)), "application/json; charset=utf-8")
                elif path.startswith("/charts/"):
                    tf = path.removeprefix("/charts/")
                    chart = CHARTS.get(tf)
                    if not chart or not chart.is_file():
                        self._send(HTTPStatus.NOT_FOUND, _json_bytes({"error": "CHART_NOT_FOUND", "tf": tf}), "application/json")
                    else:
                        self._send(HTTPStatus.OK, chart.read_bytes(), "image/png")
                else:
                    self._send(HTTPStatus.NOT_FOUND, _json_bytes({"error": "NOT_FOUND"}), "application/json")
            except Exception as exc:  # service faults never unlock execution
                self._send(HTTPStatus.SERVICE_UNAVAILABLE, _json_bytes({"error": type(exc).__name__, "can_trade": False}), "application/json")

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            action = path.removeprefix("/api/actions/")
            if not path.startswith("/api/actions/"):
                self._send(HTTPStatus.NOT_FOUND, _json_bytes({"error": "NOT_FOUND"}), "application/json")
                return
            try:
                payload = invoke_action(service, action)
                self._send(HTTPStatus.OK if payload.get("ok") else HTTPStatus.CONFLICT, _json_bytes(payload), "application/json")
            except Exception as exc:
                self._send(HTTPStatus.SERVICE_UNAVAILABLE, _json_bytes({"ok": False, "error": type(exc).__name__, "can_trade": False}), "application/json")

        def log_message(self, _format: str, *_args: object) -> None:
            return

    return DashboardHandler


def create_server(service: object | None = None, host: str = "127.0.0.1", port: int = 8780) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler(service or default_service()))


def main() -> None:
    server = create_server()
    print(f"Dashboard mecánico local: http://127.0.0.1:{server.server_port}")
    print("Estado inicial seguro: OFF. El dashboard no arma ni ejecuta órdenes al iniciar.")
    server.serve_forever()


if __name__ == "__main__":
    main()
