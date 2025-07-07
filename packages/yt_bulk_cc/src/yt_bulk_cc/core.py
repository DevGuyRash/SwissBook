"""yt_bulk_cc.core – async download + iteration logic extracted from the
legacy script.

Only high-level routines are included here; lower-level utilities live in
other modules to keep responsibilities clear.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Sequence
import requests
from youtube_transcript_api.proxies import GenericProxyConfig
from youtube_transcript_api.proxies import WebshareProxyConfig
from .user_agent import _pick_ua
from .utils import stats, detect, make_proxy as _make_proxy

import scrapetube
import time
from youtube_transcript_api import YouTubeTranscriptApi

from .errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    TooManyRequests,
    IpBlocked,
)
from .formatters import FMT
from . import _single_file_header, _fixup_loop  # type: ignore

__all__ = [
    "grab",
    "video_iter",
    "probe_video",
]


def probe_video(
    vid: str,
    *,
    cookies: list | None = None,
    proxy_pool: list[str] | None = None,
    proxy_cfg: GenericProxyConfig | WebshareProxyConfig | None = None,
    banned: set[str] | None = None,
    tries: int = 3,  # Added tries parameter
) -> tuple[bool, set[str]]:
    """Return ``(ok, banned_proxies)`` after probing ``vid``."""
    banned = banned if banned is not None else set()
    if proxy_cfg:
        proxies = [proxy_cfg]
    else:
        proxies = proxy_pool or [None]
    for url in proxies:
        if isinstance(url, (GenericProxyConfig, WebshareProxyConfig)):
            proxy = url
            addr = None
        else:
            addr = url
            proxy = _make_proxy(url) if url else None

        if addr:
            label = addr
        elif isinstance(proxy, GenericProxyConfig):
            label = proxy.http_url
        elif isinstance(proxy, WebshareProxyConfig):
            label = "webshare"
        else:
            label = "direct"

        session = requests.Session()
        session.headers.update({"User-Agent": _pick_ua()})
        if cookies:
            for c in cookies:
                session.cookies.set(c.get("name"), c.get("value"))
        api = YouTubeTranscriptApi(proxy_config=proxy, http_client=session)

        for attempt in range(1, tries + 1):  # Retry loop
            logging.info("Probe attempt %d/%d via %s", attempt, tries, label)
            try:
                api.fetch(vid, languages=["en"])
                return True, banned
            except (TooManyRequests, IpBlocked) as exc:
                if addr:
                    banned.add(addr)
                    logging.info("🚫 banned %s (%s)", label, exc.__class__.__name__)
                wait = 6 * attempt  # Exponential backoff
                logging.debug(
                    "⏳ Probe for %s - retrying in %ss (attempt %s/%s)",
                    vid,
                    wait,
                    attempt,
                    tries,
                )
                time.sleep(wait)  # Use time.sleep for synchronous probe
                continue
            except Exception:
                return True, banned  # Other errors are not considered IP blocks
        if addr:
            banned.add(addr)  # If all retries fail, ban the proxy
            logging.info("🚫 banned %s (failed)", label)
    return False, banned


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
    proxy_cfg: GenericProxyConfig | WebshareProxyConfig | None = None,
    banned: set[str] | None = None,
    include_stats: bool = True,
    delay: float = 0.0,
):
    """Download a single transcript asynchronously and write it to *path*."""
    async with sem:
        proxy_cycle = None
        if proxy_pool:
            from itertools import cycle

            proxy_cycle = cycle(proxy_pool)
        banned = banned if banned is not None else set()

        for attempt in range(1, tries + 1):
            try:
                proxy = None
                addr = None
                if proxy_cycle:
                    for _ in range(len(proxy_pool)):
                        cand = next(proxy_cycle)
                        if cand not in banned:
                            addr = cand
                            break
                    else:
                        logging.error("All proxies appear blocked; abort %s", vid)
                        return ("fail", vid, title)
                    proxy = _make_proxy(addr)
                elif proxy_cfg:
                    proxy = proxy_cfg

                if addr:
                    label = addr
                elif isinstance(proxy, GenericProxyConfig):
                    label = proxy.http_url
                elif isinstance(proxy, WebshareProxyConfig):
                    label = "webshare"
                else:
                    label = "direct"

                logging.info(
                    "Download attempt %d/%d via %s", attempt, tries, label
                )

                session = requests.Session()
                session.headers.update({"User-Agent": _pick_ua()})
                if cookies:
                    for c in cookies:
                        session.cookies.set(c.get("name"), c.get("value"))

                api = YouTubeTranscriptApi(proxy_config=proxy, http_client=session)

                tr = await asyncio.to_thread(
                    api.fetch,
                    vid,
                    languages=list(langs) if langs else ["en"],
                )
                fmt_tr = tr if hasattr(tr, "__iter__") else coerce_attr(tr.to_raw_data())

                meta = {
                    "video_id": vid,
                    "title": title,
                    "url": f"https://youtu.be/{vid}",
                    "language": langs[0] if langs else "unknown",
                }

                if fmt_key == "json":
                    import json

                    payload = dict(
                        meta,
                        transcript=tr.to_raw_data() if hasattr(tr, "to_raw_data") else tr,
                    )
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
                    data = FMT[fmt_key].format_transcript(fmt_tr)

                if fmt_key == "json" or not include_stats:
                    path.write_text(data, encoding="utf-8")
                else:
                    full = _single_file_header(fmt_key, data, meta)  # type: ignore[arg-type]
                    path.write_text(full, encoding="utf-8")
                logging.info("✔ saved %s", path.name)
                if delay:
                    await asyncio.sleep(delay)
                return ("ok", vid, title)

            except (TranscriptsDisabled, NoTranscriptFound):
                logging.warning("No subtitles for video %s", vid)
                if delay:
                    await asyncio.sleep(delay)
                return ("none", vid, title)
            except (TooManyRequests, IpBlocked, CouldNotRetrieveTranscript) as exc:
                if addr:
                    banned.add(addr)
                    logging.info("🚫 banned %s (%s)", label, exc.__class__.__name__)
                wait = 6 * attempt
                logging.debug(
                    "⏳ %s - retrying in %ss (attempt %s/%s)",
                    exc.__class__.__name__,
                    wait,
                    attempt,
                    tries,
                )
                await asyncio.sleep(wait)
                continue
            except Exception as exc:
                if attempt == tries:
                    logging.error("%s after %d tries – giving up", exc, attempt)
                    if addr:
                        banned.add(addr)
                        logging.info("🚫 banned %s (failed)", label)
                    if delay:
                        await asyncio.sleep(delay)
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
        vid_dicts = scrapetube.get_playlist(ident, limit=limit or 0, sleep=pause)
    else:  # channel
        vid_dicts = scrapetube.get_channel(channel_url=ident, limit=limit or 0, sleep=pause)

    for d in vid_dicts:
        vid = d["videoId"]
        title_runs = d.get("title", {}).get("runs", [])
        title = title_runs[0]["text"] if title_runs else vid
        yield vid, title
        if pause:
            import time

            time.sleep(pause) 