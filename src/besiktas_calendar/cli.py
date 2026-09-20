"""Komut satırı girişi: `besiktas-calendar` ya da `python -m besiktas_calendar`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .build import run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="besiktas-calendar",
        description="Beşiktaş erkek futbol ve basketbol maç takvimlerini (ICS) ve web sayfasını üretir.",
    )
    parser.add_argument("--out", type=Path, default=Path("docs"), help="çıktı klasörü (varsayılan: docs)")
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    return run(args.out)
