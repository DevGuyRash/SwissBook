"""yt_bulk_cc.utils

Utility helpers extracted from the original monolithic script.  Keeping
these generic (no Playwright or YouTube dependencies) makes them easy to
unit-test and reuse.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse, urlunparse
from youtube_transcript_api.proxies import GenericProxyConfig, WebshareProxyConfig

__all__ = [
    "BAD_REGEX",
    "slug",
    "stats",
    "shorten_path",
    "detect",
    "coerce_attr",
    "make_proxy",
]

# ---------------------------------------------------------------------------
# Filesystem-safe helpers
# ---------------------------------------------------------------------------

BAD_REGEX = re.compile(r'[\\/:*?"<>|\r\n]+')


def shorten_path(p: Path) -> Path:  # pragma: no cover – OS-specific
    """Windows MAX_PATH (260-char) workaround.

    If *p* exceeds ~260 characters on Windows, attempt to shorten it while
    preserving the important bits (video-id, file extension, etc.).  On other
    OSes this is a no-op.
    """
    if os.name != "nt":
        return p

    MAX = 250  # some headroom
    if len(str(p)) <= MAX:
        return p

    dir_part = p.parent
    base = p.name

    m = re.match(r"(\d+ )?\[([A-Za-z0-9_-]{11})] (.+)\.(\w+)", base)
    if m:
        prefix, vid, title, ext = m.groups()
        prefix = prefix or ""
        new_title = title[:40] + ("…" if len(title) > 40 else "")
        candidate = dir_part / f"{prefix}[{vid}] {new_title}.{ext}"
        if len(str(candidate)) <= 260:
            return candidate

    short = hashlib.md5(base.encode()).hexdigest()[:8] + p.suffix
    return dir_part / short


# ---------------------------------------------------------------------------
# Text statistics & slugging
# ---------------------------------------------------------------------------

def slug(text: str, max_len: int = 120) -> str:
    """Return a filesystem-safe, reasonably short slice of *text*."""
    text = BAD_REGEX.sub("_", text).strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) > max_len:
        text = text[:max_len].rsplit(" ", 1)[0] + "…"
    return text or "untitled"


def stats(txt: str) -> tuple[int, int, int]:
    """Return *(words, lines, chars)* exactly like the *nix `wc` tool."""
    chars = len(txt)
    words = len(re.findall(r"\S+", txt))
    lines = txt.count("\n")  # match `wc -l` semantics
    return words, lines, chars


# ---------------------------------------------------------------------------
# Cue adapter (dict → SimpleNamespace)
# ---------------------------------------------------------------------------


from youtube_transcript_api import FetchedTranscriptSnippet


def coerce_attr(seq):
    """Return cue objects compatible with ``Formatter`` classes."""

    return [
        FetchedTranscriptSnippet(**d) if isinstance(d, dict) else d
        for d in seq
    ]

# ---------------------------------------------------------------------------
# YouTube URL detector
# ---------------------------------------------------------------------------

_VID_RE = re.compile(r"(?:youtu\.be/|v=)([A-Za-z0-9_-]{11})")
_LIST_RE = re.compile(r"[?&]list=([A-Za-z0-9_-]+)")
_CHAN_RE = re.compile(r"(?:/channel/|/user/|/@)([A-Za-z0-9_-]+)")


def detect(url: str) -> tuple[str, str]:
    """Classify *url* as video/playlist/channel and return *(kind, id/url)*."""
    if (m := _VID_RE.search(url)):
        return "video", m.group(1)
    if (m := _LIST_RE.search(url)):
        return "playlist", m.group(1)
    if _CHAN_RE.search(url) or url.rstrip("/").endswith("/videos"):
        return "channel", url
    raise argparse.ArgumentTypeError("Link doesn't look like video/playlist/channel")


def make_proxy(url: str) -> GenericProxyConfig | WebshareProxyConfig:
    """Return a ``GenericProxyConfig`` or ``WebshareProxyConfig`` for *url*."""
    if url.lower().startswith(("ws://", "webshare://")):
        creds = url.split("://", 1)[1]
        user, pwd = creds.split(":", 1)
        return WebshareProxyConfig(user, pwd)
    parsed = urlparse(url)
    if parsed.scheme in ("http", "https"):
        http_url = urlunparse(parsed._replace(scheme="http"))
        https_url = urlunparse(parsed._replace(scheme="https"))
    else:
        http_url = https_url = url
    return GenericProxyConfig(http_url=http_url, https_url=https_url)
