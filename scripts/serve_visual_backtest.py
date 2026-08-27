"""Serve one immutable visual-backtest run and the local viewer build."""

from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import mimetypes
from pathlib import Path, PurePosixPath
import sys
from urllib.parse import unquote, urlsplit
import webbrowser


ROOT = Path(__file__).resolve().parents[1]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--viewer-dir", type=Path, default=ROOT / "backtest" / "viewer" / "dist")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4173)
    parser.add_argument("--open", action="store_true", help="open the viewer in the default browser on start")
    return parser


def _safe_relative(url_path: str) -> PurePosixPath | None:
    decoded = unquote(urlsplit(url_path).path)
    if "\x00" in decoded or "\\" in decoded:
        return None
    relative = PurePosixPath(decoded.lstrip("/"))
    if any(part in {"", ".", ".."} for part in relative.parts):
        return None
    return relative


def _handler(viewer_dir: Path, run_dir: Path) -> type[BaseHTTPRequestHandler]:
    class ReadOnlyHandler(BaseHTTPRequestHandler):
        server_version = "ICTStructureLab/1.1"

        def do_GET(self) -> None:  # noqa: N802
            self._serve(send_body=True)

        def do_HEAD(self) -> None:  # noqa: N802
            self._serve(send_body=False)

        def do_POST(self) -> None:  # noqa: N802
            self.send_error(HTTPStatus.METHOD_NOT_ALLOWED, "read-only server")

        do_PUT = do_POST
        do_PATCH = do_POST
        do_DELETE = do_POST

        def _resolve(self) -> Path | None:
            raw_path = urlsplit(self.path).path
            if raw_path in {"", "/"}:
                return viewer_dir / "index.html"
            relative = _safe_relative(raw_path)
            if relative is None:
                return None
            if relative.as_posix() == "run/visual_backtest.json":
                return run_dir / "visual_backtest.json"
            if relative.as_posix() == "run/manifest.json":
                return run_dir / "manifest.json"
            candidate = (viewer_dir / Path(*relative.parts)).resolve()
            try:
                candidate.relative_to(viewer_dir)
            except ValueError:
                return None
            return candidate

        def _serve(self, *, send_body: bool) -> None:
            target = self._resolve()
            if target is None:
                self.send_error(HTTPStatus.BAD_REQUEST, "invalid path")
                return
            if not target.is_file():
                self.send_error(HTTPStatus.NOT_FOUND, "file not found")
                return
            data = target.read_bytes()
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if target.suffix == ".json":
                content_type = "application/json; charset=utf-8"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store" if target.suffix == ".json" else "no-cache")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            if send_body:
                self.wfile.write(data)

        def log_message(self, fmt: str, *args: object) -> None:
            print(f"{self.client_address[0]} - {fmt % args}")

    return ReadOnlyHandler


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    viewer_dir = args.viewer_dir.resolve()
    run_dir = args.run_dir.resolve()
    if not (viewer_dir / "index.html").is_file():
        raise SystemExit(f"viewer build not found: {viewer_dir / 'index.html'}")
    for filename in ("visual_backtest.json", "manifest.json"):
        if not (run_dir / filename).is_file():
            raise SystemExit(f"run file not found: {run_dir / filename}")
    server = ThreadingHTTPServer((args.host, args.port), _handler(viewer_dir, run_dir))
    host, port = server.server_address[:2]
    print(f"viewer=http://{host}:{port}/")
    print(f"run={run_dir.name}")
    print("mode=READ_ONLY_LOCAL; Ctrl+C to stop")
    if args.open:
        webbrowser.open(f"http://{host}:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("stopping")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
