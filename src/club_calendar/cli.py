"""Komut satırı girişi: `club-calendar` ya da `python -m club_calendar`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .build import run
from .club import CLUBS, get_club, load_club


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="club-calendar",
        description="Bir kulübün erkek futbol ve basketbol maç takvimlerini (ICS) ve web sayfasını üretir.",
    )
    parser.add_argument("--out", type=Path, default=Path("docs"), help="çıktı klasörü (varsayılan: docs)")
    parser.add_argument(
        "--club",
        choices=sorted(CLUBS),
        help="takip edilen kulüp (varsayılan: deponun kökündeki club.toml dosyasındaki `club` değeri)",
    )
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    try:
        club = get_club(args.club) if args.club else load_club()
    except ValueError as exc:
        parser.error(str(exc))
    return run(args.out, club)
