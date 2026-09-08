"""Same-origin loopback delivery with bounded, authenticated action endpoints."""
import json
import mimetypes
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote, parse_qs

UI_DIST = Path(__file__).parent / "ui" / "dist" / "client"
ROOT = Path(__file__).resolve().parents[2]


def document_paths():
    """Only known documentation roots, bounded and read-only; never arbitrary files."""
    candidates = [ROOT / ".hermes-index.md", ROOT / "docs" / "INDICE_AUTORIDAD.md"]
    for folder in [".hermes-worklog", "docs/tesis", "docs/ict", "docs/contratos", "docs/wyckoff"]:
        candidates.extend(sorted((ROOT / folder).glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:100])
    return {str(p.relative_to(ROOT)).replace("\\", "/"): p for p in candidates if p.is_file() and not p.is_symlink()}


def create_server(runtime, port=8790, ui_dist=UI_DIST):
    class Handler(BaseHTTPRequestHandler):
        def send(self, code, payload, mime="application/json; charset=utf-8"):
            body = payload if isinstance(payload, bytes) else json.dumps(payload, default=str, allow_nan=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store" if mime.startswith("application/json") else "no-cache")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def valid_host(self):
            return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

        def do_GET(self):
            if not self.valid_host():
                return self.send(403, {"error": "INVALID_HOST"})
            path = unquote(urlparse(self.path).path)
            if path == "/api/state":
                query = parse_qs(urlparse(self.path).query)
                return self.send(200, runtime.snapshot(query.get("bars_version", [None])[0], query.get("engine_version", [None])[0]))
            if path == "/api/documents":
                return self.send(200, {"documents": list(document_paths())})
            if path == "/api/document":
                name = parse_qs(urlparse(self.path).query).get("path", [""])[0]
                document = document_paths().get(name)
                if document is None:
                    return self.send(404, {"error": "DOCUMENT_NOT_FOUND"})
                with document.open("r", encoding="utf-8", errors="replace") as handle:
                    content = handle.read(120000)
                return self.send(200, {"path": name, "content": content, "truncated": document.stat().st_size > 120000})
            if path.startswith("/api/"):
                return self.send(404, {"error": "NOT_FOUND"})
            target = (ui_dist / ("index.html" if path == "/" else path.lstrip("/"))).resolve()
            if not target.is_relative_to(ui_dist.resolve()) or not target.is_file():
                return self.send(404, {"error": "NOT_FOUND"})
            return self.send(200, target.read_bytes(), mimetypes.guess_type(target.name)[0] or "application/octet-stream")

        def do_POST(self):
            origin = self.headers.get("Origin")
            expected = f"http://127.0.0.1:{self.server.server_port}"
            if not self.valid_host() or origin not in (None, expected):
                return self.send(403, {"ok": False, "error": "INVALID_ORIGIN"})
            if not secrets.compare_digest(self.headers.get("X-ICT-Token", ""), runtime.token):
                return self.send(403, {"ok": False, "error": "INVALID_TOKEN"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self.send(400, {"ok": False, "error": "INVALID_LENGTH"})
            if self.headers.get("Transfer-Encoding") or length < 0 or length > 1024:
                return self.send(413, {"ok": False, "error": "BODY_TOO_LARGE"})
            self.rfile.read(length)
            path = urlparse(self.path).path
            if not path.startswith("/api/actions/"):
                return self.send(404, {"ok": False, "error": "NOT_FOUND"})
            try:
                result = runtime.action(path.removeprefix("/api/actions/"))
                return self.send(200, result)
            except (ValueError, RuntimeError) as exc:
                return self.send(409, {"ok": False, "error": str(exc)})
            except Exception as exc:
                return self.send(503, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server
