"""yt_bulk_cc.utils

Utility helpers previously defined in the monolithic script.  This thin
facade lets other modules migrate away from ``yt_bulk_cc.yt_bulk_cc``
while we incrementally refactor the internals.
"""
from __future__ import annotations

from .yt_bulk_cc import (
    slug,
    _stats as stats,
    detect,
    _shorten_for_windows as shorten_path,
    _BAD as BAD_REGEX,
)

__all__ = [
    "slug",
    "stats",
    "detect",
    "shorten_path",
    "BAD_REGEX",
] 