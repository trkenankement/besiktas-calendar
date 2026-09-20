"""Sağlayıcıların ortak yardımcıları."""

from __future__ import annotations

from ..http import SourceError

SKIPPED_WITHOUT_ANY_MATCH = 3


def guard_skipped(source: str, skipped: int, kept: int) -> None:
    """Tek tük maçın atlanması normaldir (ör. ertelenmiş); hiçbir maç okunamıyorsa kaynak biçimi değişmiştir."""
    if skipped >= SKIPPED_WITHOUT_ANY_MATCH and kept == 0:
        raise SourceError(
            f"{source}: {skipped} maçın tarihi okunamadı ve hiçbir maç alınamadı; kaynağın biçimi değişmiş olabilir"
        )
