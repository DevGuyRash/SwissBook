"""Header and statistics helpers for transcript files."""

from __future__ import annotations

import datetime
import logging
from pathlib import Path
from .utils import stats as _stats

# Fixed-width placeholders (12 chars each → fits 999 999 999 999)
_PH = "{:>12}"
_PH_W = _PH.format(0)
_PH_L = _PH.format(0)
_PH_C = _PH.format(0)


def _header_text(
    fmt: str,
    w: int,
    l: int,
    c: int,
    metas: list[tuple[str, str]] | None = None,
    _ts_override: str | None = None,
) -> str:
    """Return a stats header plus optional video list."""
    pre = "NOTE " if fmt in ("srt", "webvtt") else "# "
    lines = [
        f"{pre}stats: {w:,} words · {l:,} lines · {c:,} chars",
        f"{pre}generated: {_ts_override or datetime.datetime.now().isoformat()}",
    ]
    if metas:
        lines.append(f"{pre}videos:")
        for vid, title in metas:
            lines.append(f"{pre}  - https://youtu.be/{vid} — {title}")
    lines.append("")
    return "\n".join(lines) + "\n"


def _fixup_loop(
    body: tuple[int, int, int],
    fmt: str,
    metas: list[tuple[str, str]] | None,
) -> tuple[str, int, int, int]:
    """Return ``(header_text, W, L, C)`` self-consistently."""
    body_w, body_l, body_c = body
    w, l, c = body
    ts_frozen = datetime.datetime.now().isoformat()
    for _ in range(10):
        hdr = _header_text(fmt, w, l, c, metas, _ts_override=ts_frozen)
        hw, hl, hc = _stats(hdr)
        w2, l2, c2 = body_w + hw, body_l + hl, body_c + hc
        if (w, l, c) == (w2, l2, c2):
            return hdr, w, l, c
        w, l, c = w2, l2, c2
    logging.warning("Header stats failed to converge in 10 rounds; using last attempt")
    return hdr, w, l, c


def _single_file_header(fmt: str, body_txt: str, meta: dict[str, str]) -> str:
    """Return a header for an individual transcript file."""
    pre = "NOTE " if fmt in ("srt", "webvtt") else "# "
    aux_lines = [
        f"{pre}video-id: {meta['video_id']}",
        f"{pre}url:      {meta['url']}",
        f"{pre}title:    {meta['title']}",
    ]
    aux_txt = "\n".join(aux_lines) + "\n\n"
    bw, bl, bc = _stats(body_txt)
    aw, al, ac = _stats(aux_txt)
    hdr, _, _, _ = _fixup_loop((bw + aw, bl + al, bc + ac), fmt, None)
    return hdr + aux_txt + body_txt


def _prepend_header(path: Path, hdr: str) -> None:
    """Prepend ``hdr`` to the contents of ``path``."""
    txt = path.read_text(encoding="utf-8", errors="ignore")
    path.write_text(hdr + txt, encoding="utf-8")


__all__ = [
    "_header_text",
    "_fixup_loop",
    "_single_file_header",
    "_prepend_header",
]
