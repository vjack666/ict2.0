from pathlib import Path
from runtime.live_scanner.cache import IncrementalCache

def test_cache_writes_chunk_and_manifest(tmp_path: Path):
    cache = IncrementalCache(tmp_path)
    chunk = cache.write_chunk("EURUSD_M15_2026-09-03", [{"observation_time": "2026-09-03T10:00:00Z", "close": 1.1}])
    manifest = cache.update_manifest(chunks=[chunk], last_closed_by_tf={"M15": "2026-09-03T10:00:00Z"}, engine_commit="local", config={"closed_only": True})
    assert manifest.status == "READY"
    assert cache.load_manifest().chunks[0]["sha256"] == chunk["sha256"]
