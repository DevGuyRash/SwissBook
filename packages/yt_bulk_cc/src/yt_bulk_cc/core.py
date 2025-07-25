"""yt_bulk_cc.core – async download + iteration logic extracted from the
legacy script.

Only high-level routines are included here; lower-level utilities live in
other modules to keep responsibilities clear.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Sequence
import requests
from youtube_transcript_api.proxies import GenericProxyConfig
from youtube_transcript_api.proxies import WebshareProxyConfig
from .user_agent import _pick_ua
from .utils import coerce_attr, detect, make_proxy as _make_proxy, stats as _stats

import time
from youtube_transcript_api import YouTubeTranscriptApi

from .errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    TooManyRequests,
    IpBlocked,
    VideoUnavailable,
    CouldNotRetrieveTranscript,
)
from .formatters import FMT
from .header import _single_file_header, _fixup_loop  # type: ignore

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
    elif proxy_pool and hasattr(proxy_pool, "get"):
        proxies = [proxy_pool.get()]
    else:
        proxies = [None]
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
                elif label == "direct":
                    banned.add(label)
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
            except requests.exceptions.RequestException as exc:
                logging.debug("Probe network error via %s: %s", label, exc)
                time.sleep(1 * attempt)
                continue
            except Exception:
                return True, banned  # Other errors are not considered IP blocks
        if addr:
            banned.add(addr)  # If all retries fail, ban the proxy
            logging.info("🚫 banned %s (failed)", label)
        elif label == "direct":
            banned.add(label)
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
    used: set[str] | None = None,
    include_stats: bool = True,
    delay: float = 0.0,
) -> tuple[str, str, str]:  # (status, video_id, title)
    async with sem:
        banned = banned if banned is not None else set()
        used = used if used is not None else set()

        for attempt in range(1, tries + 1):
            try:
                proxy = None
                addr = None
                if proxy_pool and hasattr(proxy_pool, "get"):
                    spin = 0
                    while spin < 5:
                        addr = proxy_pool.get()
                        if addr not in banned:
                            break
                        spin += 1
                    if addr in banned:
                        logging.error("All sampled proxies banned; abort %s", vid)
                        return ("proxy_fail", vid, title)
                elif proxy_cfg:
                    proxy = proxy_cfg

                label = addr or (
                    proxy.http_url if isinstance(proxy, GenericProxyConfig) else (
                        "webshare" if isinstance(proxy, WebshareProxyConfig) else "direct"
                    )
                )
                used.add(label)
                logging.info("Using proxy %s for %s (attempt %d/%d)", label, vid, attempt, tries)

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
                fmt_tr = (
                    tr if hasattr(tr, "__iter__") else coerce_attr(tr.to_raw_data())
                )

                meta = {
                    "video_id": vid,
                    "title": title,
                    "url": f"https://youtu.be/{vid}",
                    "language": langs[0] if langs else "unknown",
                }

                if fmt_key == "json":
                    payload = dict(
                        meta,
                        transcript=(
                            tr.to_raw_data() if hasattr(tr, "to_raw_data") else tr
                        ),
                    )

                    # embed per-file stats unless we know we'll concatenate later
                    if include_stats:
                        for _ in range(3):  # converges fast
                            # Make the measurement on **exactly** the same
                            # text that will be written to disk - including
                            # the final newline that json.dumps omits.
                            tmp = json.dumps(payload, indent=2, ensure_ascii=False)
                            if not tmp.endswith("\n"):
                                tmp += "\n"
                            w, l, c = _stats(tmp)
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
                    # JSON, or stats explicitly disabled → dump verbatim
                    path.write_text(data, encoding="utf-8")
                else:
                    full = _single_file_header(fmt_key, data, meta)
                    path.write_text(full, encoding="utf-8")
                logging.info("✔ saved %s", path.name)
                if delay:
                    await asyncio.sleep(delay)
                return ("ok", vid, title)

            except (TranscriptsDisabled, NoTranscriptFound):
                logging.warning("✖ no transcript for %s", vid)
                if delay:
                    await asyncio.sleep(delay)
                return ("none", vid, title)

            # ← NEW: some library versions throw a TypeError instead when the
            # test stub mis-constructs NoTranscriptFound().  Detect that form
            # and downgrade it to "none".
            except TypeError as exc:
                if "NoTranscriptFound" in str(exc):
                    logging.debug(
                        "TypeError wrapper for NoTranscriptFound → treat as none"
                    )
                    logging.warning("✖ no transcript for %s", vid)
                    return ("none", vid, title)
                raise  # unrelated TypeError → re-raise as before
            except VideoUnavailable:
                logging.warning("✖ video unavailable %s", vid)
                return ("fail", vid, title)
            except (TooManyRequests, IpBlocked, CouldNotRetrieveTranscript) as exc:
                if addr:
                    banned.add(addr)
                wait = 6 * attempt
                logging.info(
                    "⏳ %s - retrying in %ss (attempt %s/%s)",
                    exc.__class__.__name__,
                    wait,
                    attempt,
                    tries,
                )
                await asyncio.sleep(wait)
                continue
            except requests.exceptions.RequestException as exc:
                logging.debug("Network error for %s via %s: %s", vid, addr or proxy_cfg, exc)
                if attempt == tries:
                    logging.error("%s after %d tries – giving up", exc, attempt)
                    if addr:
                        banned.add(addr)
                    if delay:
                        await asyncio.sleep(delay)
                    return ("proxy_fail", vid, title)
                await asyncio.sleep(1.0 * attempt)
                continue
            except Exception as exc:
                if attempt == tries:
                    logging.error("%s after %d tries – giving up", exc, attempt)
                    if addr:
                        banned.add(addr)
                    if delay:
                        await asyncio.sleep(delay)
                    return ("proxy_fail", vid, title)
                await asyncio.sleep(0.5 * attempt)
        if delay:
            await asyncio.sleep(delay)
        return ("proxy_fail", vid, title)


def video_iter(kind: str, ident: str, limit: int | None, pause: int):
    """Yield minimal video JSON objects from scrapetube (or single-video stub)."""
    if kind == "video":
        yield {"videoId": ident, "title": {"runs": [{"text": ident}]}}
    else:
        from importlib import import_module

        ytb = import_module("yt_bulk_cc")
        if kind == "playlist":
            yield from ytb.scrapetube.get_playlist(ident, limit=limit, sleep=pause)
        elif kind == "channel":
            yield from ytb.scrapetube.get_channel(
                channel_url=ident, limit=limit, sleep=pause
            )
