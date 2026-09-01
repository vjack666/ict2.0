"""Helper de provenance: hashes de fuente + commit para auditorías.

Centraliza la emisión de `generator_commit` y `generator_source_hashes` en los
reportes de auditoría, para cerrar la deuda de lineage (gate causal y TNA previos
no los guardaban). No cambia lógica de negocio ni resultados.
"""
from __future__ import annotations
import subprocess, hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _git_commit() -> str:
    try:
        p = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                            text=True, capture_output=True, check=False)
        return p.stdout.strip() or "UNKNOWN"
    except Exception:
        return "UNKNOWN"


def _sha256(path: Path) -> str:
    try:
        h = hashlib.sha256()
        h.update(path.read_bytes())
        return h.hexdigest()
    except Exception:
        return "UNREADABLE"


def source_hashes(files) -> dict:
    return {str(f): _sha256(ROOT / f) for f in files}


def provenance_block(files) -> dict:
    """Bloque a inyectar en cualquier reporte de auditoría."""
    return {
        "generator_commit": _git_commit(),
        "generator_worktree": "DIRTY" if _git_commit() == "UNKNOWN" else _git_status(),
        "generator_source_hashes": source_hashes(files),
    }


def _git_status() -> str:
    try:
        p = subprocess.run(["git", "status", "--porcelain"], cwd=str(ROOT),
                            text=True, capture_output=True, check=False)
        return "DIRTY" if p.stdout.strip() else "CLEAN"
    except Exception:
        return "UNKNOWN"
