"""Top-level package for yt_bulk_cc."""

from __future__ import annotations

import asyncio as _aio
import sys as _sys
import os as _os
import requests as _requests
import json as _json
from random import choice as _choice
from youtube_transcript_api.proxies import GenericProxyConfig, WebshareProxyConfig

try:  # Optional dependency
    import scrapetube as _scrapetube
except Exception:  # pragma: no cover - optional
    _scrapetube = None  # type: ignore

from .utils import (
    slug,
    stats as _stats,
    detect,
    shorten_path as _shorten_for_windows,
    make_proxy as _make_proxy,
)
from .formatters import TimeStampedText, FMT, EXT
from .converter import convert_existing
from .errors import (
    CouldNotRetrieveTranscript,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
    NoTranscriptAvailable,
    TooManyRequests,
    IpBlocked,
)
from .core import grab, video_iter, probe_video
from .header import _fixup_loop, _single_file_header, _header_text, _prepend_header
from .user_agent import _pick_ua

try:
    from swiftshadow.classes import ProxyInterface
except Exception:  # pragma: no cover - optional
    ProxyInterface = None  # type: ignore
from .cli import main

__all__ = [
    "slug",
    "_stats",
    "detect",
    "_shorten_for_windows",
    "TimeStampedText",
    "FMT",
    "EXT",
    "convert_existing",
    "CouldNotRetrieveTranscript",
    "NoTranscriptFound",
    "TranscriptsDisabled",
    "VideoUnavailable",
    "NoTranscriptAvailable",
    "TooManyRequests",
    "IpBlocked",
    "grab",
    "video_iter",
    "probe_video",
    "_fixup_loop",
    "_single_file_header",
    "_header_text",
    "_prepend_header",
    "_pick_ua",
    "main",
    "scrapetube",
    "asyncio",
    "_make_proxy",
    "os",
    "requests",
    "GenericProxyConfig",
    "WebshareProxyConfig",
    "ProxyInterface",
    "json",
    "choice",
]

# Alias ``yt_bulk_cc.yt_bulk_cc`` to this module for backward compatibility
_sys.modules[f"{__name__}.yt_bulk_cc"] = _sys.modules[__name__]
scrapetube = _scrapetube
asyncio = _aio
_make_proxy = _make_proxy
os = _os
requests = _requests
GenericProxyConfig = GenericProxyConfig
WebshareProxyConfig = WebshareProxyConfig
ProxyInterface = ProxyInterface
json = _json
choice = _choice

# ---------------------------------------------------------------------------
# Make asyncio.run tolerant when already inside a running event loop.
# ---------------------------------------------------------------------------
if not hasattr(_aio.run, "_nested_patch"):
    _orig_run = _aio.run

    def _safe_run(coro, *args, **kwargs):  # type: ignore[override]
        try:
            _aio.get_running_loop()
        except RuntimeError:
            return _orig_run(coro, *args, **kwargs)
        return _aio.create_task(coro)

    _safe_run._nested_patch = True  # type: ignore[attr-defined]
    _aio.run = _safe_run  # type: ignore[assignment]
