"""T7d entrypoint for the preregistered sibling-event DAG."""
from __future__ import annotations

import argparse
from pathlib import Path

from audits.codigo.mtf_replay_t7 import ROOT
from audits.codigo.mtf_replay_t7b import execute


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir", type=Path,
        default=ROOT / "reports" / "audits" / "mtf_replay" / "t7d_2025_01",
    )
    report = execute(parser.parse_args().output_dir.resolve(), run_id="t7d")
    if report["status"] == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
