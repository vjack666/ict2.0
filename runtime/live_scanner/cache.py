"""Disk-backed chunks for the MT5 scanner; no network or broker side effects."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib, json
from pathlib import Path
from typing import Any

@dataclass
class CacheManifest:
    schema_version: str = "LIVE_SCANNER_CACHE_V1"
    symbol: str = "EURUSD"
    timeframes: list[str] = field(default_factory=lambda: ["H4", "H1", "M15", "M5"])
    last_closed_by_tf: dict[str, str | None] = field(default_factory=dict)
    chunks: list[dict[str, Any]] = field(default_factory=list)
    engine_commit: str | None = None
    config_hash: str | None = None
    status: str = "WAIT"

class IncrementalCache:
    def __init__(self, root: Path | str, *, symbol: str = "EURUSD", timeframes: tuple[str, ...] = ("H4", "H1", "M15", "M5")):
        self.root = Path(root); self.manifest_path = self.root / "manifest.json"
        self.default = CacheManifest(symbol=symbol, timeframes=list(timeframes))

    def load_manifest(self) -> CacheManifest:
        if not self.manifest_path.is_file(): return self.default
        raw = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        return CacheManifest(**{**asdict(self.default), **raw})

    def write_chunk(self, chunk_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        """Write one deterministic chunk atomically; caller owns closed-only filtering."""
        self.root.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
        digest = hashlib.sha256(payload).hexdigest()
        path = self.root / f"{chunk_id}.json"
        tmp = path.with_suffix(".tmp"); tmp.write_bytes(payload); tmp.replace(path)
        return {"id": chunk_id, "path": path.name, "bytes": len(payload), "sha256": digest, "rows": len(rows)}

    def update_manifest(self, *, chunks: list[dict[str, Any]], last_closed_by_tf: dict[str, str | None], engine_commit: str | None, config: dict[str, Any]) -> CacheManifest:
        config_hash = hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        manifest = CacheManifest(symbol=self.default.symbol, timeframes=self.default.timeframes, chunks=chunks, last_closed_by_tf=last_closed_by_tf, engine_commit=engine_commit, config_hash=config_hash, status="READY")
        self.root.mkdir(parents=True, exist_ok=True); tmp = self.manifest_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(manifest), indent=2, ensure_ascii=False), encoding="utf-8"); tmp.replace(self.manifest_path)
        return manifest
