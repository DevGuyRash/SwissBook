"""yt_bulk_cc.core – async download + iteration logic extracted from the
legacy script.

Only high-level routines are included here; lower-level utilities live in
other modules to keep responsibilities clear.
"""
from __future__ import annotations

import asyncio
import inspect
import logging
from pathlib import Path
from random import choice
from typing import Sequence

import scrapetube
from youtube_transcript_api import YouTubeTranscriptApi

from .errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
)
from .formatters import FMT
from .utils import stats, detect, coerce_attr  # type: ignore[attr-defined]
from .converter import coerce_attr  # fallback if utils misses it
from . import _single_file_header, _fixup_loop  # type: ignore

__all__ = [
    "grab",
    "video_iter",
]


async def grab(
    vid: str,
    title: str,
    path: Path,
    langs: Sequence[str] | None,
    fmt_key: str,
    sem: asyncio.Semaphore,
    tries: int = 6,
    *,
    cookies: list | None = None,
    proxy_pool: list[str] | None = None,
    include_stats: bool = True,
):
    """Download a single transcript asynchronously and write it to *path*."""
    async with sem:
        for attempt in range(1, tries + 1):
            try:
                sig_params = inspect.signature(
                    YouTubeTranscriptApi.get_transcript
                ).parameters
                kwargs: dict = {}
                if langs and "languages" in sig_params:
                    kwargs["languages"] = list(langs)
                if proxy_pool and "proxies" in sig_params:
                    url = proxy_pool[0] if len(proxy_pool) == 1 else choice(proxy_pool)
                    kwargs["proxies"] = {"http": url, "https": url}
                if cookies and "cookies" in sig_params:
                    kwargs["cookies"] = cookies

                tr = await asyncio.to_thread(
                    YouTubeTranscriptApi.get_transcript,
                    vid,
                    **kwargs,
                )

                meta = {
                    "video_id": vid,
                    "title": title,
                    "url": f"https://youtu.be/{vid}",
                    "language": langs[0] if langs else "unknown",
                }

                if fmt_key == "json":
                    import json

                    payload = dict(meta, transcript=tr)
                    if include_stats:
                        for _ in range(3):
                            tmp = json.dumps(payload, indent=2, ensure_ascii=False)
                            if not tmp.endswith("\n"):
                                tmp += "\n"
                            w, l, c = stats(tmp)
                            wanted = {"words": w, "lines": l, "chars": c}
                            if payload.get("stats") == wanted:
                                break
                            payload["stats"] = wanted
                    data = json.dumps(payload, ensure_ascii=False, indent=2)
                    if not data.endswith("\n"):
                        data += "\n"
                else:
                    data = FMT[fmt_key].format_transcript(coerce_attr(tr))

                if fmt_key == "json" or not include_stats:
                    path.write_text(data, encoding="utf-8")
                else:
                    full = _single_file_header(fmt_key, data, meta)  # type: ignore[arg-type]
                    path.write_text(full, encoding="utf-8")
                logging.info("✔ saved %s", path.name)
                return ("ok", vid, title)

            except (TranscriptsDisabled, NoTranscriptFound):
                logging.warning("No subtitles for video %s", vid)
                return ("none", vid, title)
            except Exception as exc:
                if attempt == tries:
                    logging.error("%s after %d tries – giving up", exc, attempt)
                    return ("fail", vid, title)
                await asyncio.sleep(0.5 * attempt)


# ---------------------------------------------------------------------------
# scrapetube iteration wrappers
# ---------------------------------------------------------------------------


def video_iter(kind: str, ident: str, limit: int | None, pause: int):
    """Yield *(video_id, title)* tuples based on *kind* and *ident*."""
    if kind == "video":
        yield ident, "(single video)"
        return

    if kind == "playlist":
        vid_dicts = scrapetube.get_playlist(ident, limit=limit or 0)
    else:  # channel
        vid_dicts = scrapetube.get_channel(ident, limit=limit or 0)

    for d in vid_dicts:
        vid = d["videoId"]
        title_runs = d.get("title", {}).get("runs", [])
        title = title_runs[0]["text"] if title_runs else vid
        yield vid, title
        if pause:
            import time

            time.sleep(pause) 