#!/usr/bin/env python3
# yt_bulk_cc.py  —  2025-06-17 build
# -----------------------------------------------------------------------------
# MIT-licensed utility to bulk-download YouTube caption / transcript tracks.
#
# Author: 2025 DevGuyRash
# Enhancements: split-file logic, per-file stats, streaming concat,
#               5-digit numbering, cross-platform line counting,
#               transcript converter utility (JSON → any supported format)
# -----------------------------------------------------------------------------
"""
Download captions/transcripts for a single video, an entire playlist, or all
videos on a channel—no YouTube Data API key needed.

Quick examples
--------------
# 1 video → default SRT
  yt_bulk_cc.py https://youtu.be/dQw4w9WgXcQ

# Playlist → JSON file per video, each wrapped in metadata
  yt_bulk_cc.py -f json "https://youtube.com/playlist?list=PLxyz123"

# Channel → plain text with per-line timestamps, French preferred
  yt_bulk_cc.py -l fr -f text -t https://www.youtube.com/@CrashCourse/videos
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import datetime
import os            # NEW - Windows pathname tweak
import json
import glob
import logging
import re
import signal
import sys
import textwrap
from datetime import timedelta
from pathlib import Path
from random import choice
import copy          # NEW
from typing import Sequence, Callable
import inspect

import scrapetube
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import GenericProxyConfig, WebshareProxyConfig
import requests
from rich.console import Console
from rich.logging import RichHandler
from .user_agent import _pick_ua
from .utils import (
    coerce_attr,
    shorten_path as _shorten_for_windows,
    slug,
    stats as _stats,
    detect,
    make_proxy as _make_proxy,
)
from .formatters import TimeStampedText, FMT, EXT
from .converter import convert_existing
try:
    from swiftshadow.classes import ProxyInterface
    # Propagate SwiftShadow logs to our root logger so they get written
    # to the CLI log file. Clear any pre-existing handlers that might
    # otherwise short‑circuit logging.basicConfig(force=True).
    _slog = logging.getLogger("swiftshadow")
    _slog.handlers.clear()
    _slog.propagate = True
    _slog.setLevel(logging.DEBUG)
except Exception:  # pragma: no cover - optional dep
    ProxyInterface = None  # type: ignore
# ------------------------------------------------------------
#  Robust error-class import — works on every library version
# ------------------------------------------------------------
from .errors import (
    CouldNotRetrieveTranscript,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
    TooManyRequests,
    IpBlocked,
)



# ───────────────────────── helpers ────────────────────────── #

# ───────────────────────── header helpers ──────────────────────────────

# Fixed-width placeholders (12 chars each → fits 999 999 999 999)
_PH   = "{:>12}"
_PH_W = _PH.format(0)  # '           0'
_PH_L = _PH.format(0)
_PH_C = _PH.format(0)


def _fixup_loop(
    body: tuple[int, int, int],
    fmt: str,
    metas: list[tuple[str, str]] | None
) -> tuple[str, int, int, int]:
    """
    Return (header_text, W, L, C) where the W/L/C numbers *inside* the header
    equal the totals *including* the header itself.

    The iteration is bounded (max 10 rounds) so it can never hang.
    """
    body_w, body_l, body_c = body           # invariant (body only)
    w, l, c = body                          # first guess

    # Freeze timestamp once for deterministic convergence
    ts_frozen = datetime.datetime.now().isoformat()

    for _ in range(10):
        hdr = _header_text(fmt, w, l, c, metas, _ts_override=ts_frozen)
        hw, hl, hc = _stats(hdr)            # header alone
        w2, l2, c2 = body_w + hw, body_l + hl, body_c + hc
        if (w, l, c) == (w2, l2, c2):
            return hdr, w, l, c
        w, l, c = w2, l2, c2

    logging.warning("Header stats failed to converge in 10 rounds; using last attempt")
    return hdr, w, l, c


def _single_file_header(fmt: str, body_txt: str, meta: dict[str, str]) -> str:
    """
    Header for an individual (non-JSON) transcript file.

    The stats line must count:
        header  +  video-id / url / title lines  +  blank line  +  body
    """
    pre = "NOTE " if fmt in ("srt", "webvtt") else "# "
    aux_lines = [
        f"{pre}video-id: {meta['video_id']}",
        f"{pre}url:      {meta['url']}",
        f"{pre}title:    {meta['title']}",
    ]
    aux_txt = "\n".join(aux_lines) + "\n\n"      # ends with blank line

    bw, bl, bc = _stats(body_txt)                # body only
    aw, al, ac = _stats(aux_txt)                 # aux only

    hdr, _, _, _ = _fixup_loop((bw + aw, bl + al, bc + ac), fmt, None)
    return hdr + aux_txt + body_txt


# ───────────────────────── NEW: header builder ────────────────────────────
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
    lines.append("")  # blank line after header
    return "\n".join(lines) + "\n"


def _prepend_header(path: Path, hdr: str):
    txt = path.read_text(encoding="utf-8", errors="ignore")
    path.write_text(hdr + txt, encoding="utf-8")





# ───────────────────────── workers ────────────────────────── #
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
    verify_ssl: bool = True,
) -> tuple[str, str, str]:   # (status, video_id, title)
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

                session = requests.Session()
                session.headers.update({"User-Agent": _pick_ua()})
                session.verify = verify_ssl
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
                    "title":    title,
                    "url":      f"https://youtu.be/{vid}",
                    "language": langs[0] if langs else "unknown",
                }

                if fmt_key == "json":
                    payload = dict(
                        meta,
                        transcript=tr.to_raw_data() if hasattr(tr, "to_raw_data") else tr,
                    )

                    # embed per-file stats unless we know we'll concatenate later
                    if include_stats:
                        for _ in range(3):                          # converges fast
                            # Make the measurement on **exactly** the same
                            # text that will be written to disk - including
                            # the final newline that json.dumps omits.
                            tmp = json.dumps(payload, indent=2,
                                            ensure_ascii=False)
                            if not tmp.endswith("\n"):
                                tmp += "\n"
                            w, l, c = _stats(tmp)
                            wanted     = {"words": w, "lines": l, "chars": c}
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
                    logging.debug("TypeError wrapper for NoTranscriptFound → treat as none")
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
            except Exception as exc:
                if attempt == tries:
                    logging.error("%s after %d tries – giving up", exc, attempt)
                    if addr:
                        banned.add(addr)
                    if delay:
                        await asyncio.sleep(delay)
                    return ("fail", vid, title)
                await asyncio.sleep(0.5 * attempt)
        if delay:
            await asyncio.sleep(delay)
        return ("fail", vid, title)


def video_iter(kind: str, ident: str, limit: int | None, pause: int):
    """Yield minimal video JSON objects from scrapetube (or single-video stub)."""
    if   kind == "video":
        yield {"videoId": ident, "title": {"runs": [{"text": ident}]}}
    elif kind == "playlist":
        yield from scrapetube.get_playlist(ident, limit=limit, sleep=pause)
    elif kind == "channel":
        yield from scrapetube.get_channel(channel_url=ident, limit=limit, sleep=pause)


# ────────────────────────── CLI entry ─────────────────────────────── #
class C:
    """ANSI colour codes."""
    GRN = "\033[92m"; BLU = "\033[94m"; RED = "\033[91m"; YEL = "\033[93m"; END = "\033[0m"


class ColorFormatter(logging.Formatter):
    """
    Colourise console output **without** polluting other handlers.
    We operate on a shallow copy of the LogRecord so the original
    remains untouched for the file handler (and any others).
    """

    COLORS = {
        logging.DEBUG:    C.BLU,
        logging.INFO:     C.GRN,
        logging.WARNING:  C.YEL,
        logging.ERROR:    C.RED,
        logging.CRITICAL: C.RED,
    }

    def format(self, record):  # type: ignore[override]
        rec = copy.copy(record)                       # protect siblings

        color = self.COLORS.get(rec.levelno, C.END)
        rec.levelname = f"{color}{rec.levelname}{C.END}"

        if rec.levelno >= logging.WARNING:
            rec.msg = f"{color}{rec.getMessage()}{C.END}"
            rec.args = ()

        if rec.msg.startswith("Summary:") and len(rec.args) == 5:
            ok, none, fail, banned, total = rec.args
            rec.msg = (
                f"Summary: ✓ {C.GRN}{ok}{C.END}   •  "
                f"↯ no-caption {C.YEL}{none}{C.END}   •  "
                f"⚠ failed {C.RED}{fail}{C.END}   "
                f"🚫 banned {C.RED}{banned}{C.END}   "
                f"(total {total})"
            )
            rec.args = ()

        return super().format(rec)


async def _main() -> None:
    # custom help formatter
    class _ManFmt(argparse.ArgumentDefaultsHelpFormatter,
                  argparse.RawTextHelpFormatter):
        def __init__(self, prog):
            super().__init__(prog, max_help_position=32)
        def _format_action_invocation(self, action):
            if not action.option_strings:
                return super()._format_action_invocation(action)
            parts = [", ".join(action.option_strings)]
            if action.nargs != 0:
                metavar = self._format_args(
                    action, self._get_default_metavar_for_optional(action)
                )
                parts.append(metavar)
            return " ".join(parts)

    P = argparse.ArgumentParser(
        prog="yt_bulk_cc.py",
        description="Bulk-download YouTube captions / transcripts (no API key).",
        epilog="[Use --formats-help to see format examples]",
        formatter_class=_ManFmt,
    )

    # positional
    P.add_argument("LINK", nargs="?", help="Video, playlist, or channel URL")

    # core options
    P.add_argument("-o", "--folder", default=".", help="Destination directory")
    P.add_argument("-l", "--language", action="append",
                   help="Preferred language code (repeatable, priority first)")
    P.add_argument("-f", "--format", choices=list(FMT) + ["json"], default="json",
                   help="Output format")
    P.add_argument("-t", "--timestamps", action="store_true",
                   help="Prefix each cue with [hh:mm:ss.mmm] in text / pretty modes")
    P.add_argument("-n", "--limit", type=int,
                   help="Stop after N videos (handy for testing)")
    P.add_argument("-j", "--jobs", type=int, default=1,
                   help="Concurrent transcript downloads")
    P.add_argument("-s", "--sleep", type=float, default=2.0,
                   help="Seconds to wait between requests and after each download")
    P.add_argument("-v", "--verbose", action="count", default=0,
                   help="-v=info, -vv=debug")
    P.add_argument("--no-seq-prefix", action="store_true",
                   help="Don't prefix output filenames with 00001 … ordering "
                        "(prefix is ON by default)")

    # ──────────────── NEW: stats on/off ──────────────────
    stats_group = P.add_mutually_exclusive_group()
    stats_group.add_argument("--stats",     dest="stats", action="store_true",
                             help="Embed per-file stats headers (default)")
    stats_group.add_argument("--no-stats",  dest="stats", action="store_false",
                             help="Skip stats headers / blocks")
    P.set_defaults(stats=True)

    # logging
    log_group = P.add_mutually_exclusive_group()
    log_group.add_argument("-L", "--log-file", metavar="FILE",
        help="Write a full run-log to FILE (plus console). "
             "If omitted, auto-creates yt_bulk_cc_YYYYMMDD-HHMMSS.log.")
    log_group.add_argument("--no-log", action="store_true",
        help="Disable file logging entirely.")

    # misc helpers
    P.add_argument("-F", "--formats-help", action="store_true",
                   help="Show examples of each output format and exit")
    P.add_argument(
        "-p",
        "--proxy",
        metavar="URL[,URL2,…]",
        help=(
            "Single proxy URL or comma-separated list to rotate through. "
            "Include credentials in the URL if needed, e.g. http://user:pass@host:port. "
            "Use ws://user:pass for Webshare residential proxies"
        ),
    )
    P.add_argument(
        "--proxy-file",
        metavar="FILE",
        help=(
            "Load proxies from FILE (one URL per line). "
            "Each line may include credentials. Combines with -p when rotating between multiple"
        ),
    )
    P.add_argument(
        "--public-proxy",
        nargs="?",
        const=5,
        type=int,
        metavar="N",
        help="Fetch N free proxies via Swiftshadow (default 5)",
    )
    P.add_argument(
        "--public-proxy-country",
        metavar="CC[,CC]",
        help="Comma-separated country codes for public proxies",
    )
    P.add_argument(
        "--public-proxy-type",
        choices=["http", "https", "socks"],
        help="Protocol for public proxies (auto if omitted)",
    )
    P.add_argument("-c", "--cookie-json", "--cookie-file", dest="cookie_json",
                   metavar="FILE",
                   help="Cookies JSON exported by browser (see docs)")
    P.add_argument("--check-ip", action="store_true",
                   help="Fetch first video once to detect IP blocks early")
    P.add_argument("--overwrite", action="store_true",
                   help="Re-download even if output file already exists")
    P.add_argument(
        "--insecure",
        dest="verify_ssl",
        action="store_false",
        help="Disable SSL certificate verification for HTTP requests",
    )
    P.set_defaults(verify_ssl=True)

    # concatenation & splitting
    P.add_argument("-C", "--concat", action="store_true",
                   help="Write all successful transcripts into one file")
    P.add_argument("--basename", default="combined", metavar="NAME",
                   help="Base filename for concatenated output (default 'combined')")
    P.add_argument("--split", metavar="N[w|c|l]",
                   help="With --concat: start a new file once N words/chars/lines "
                        "would be exceeded, e.g. --split 12000c. Off by default.")

    # ───────── stats list size ──────────────────────────────────────────────
    P.add_argument("--stats-top", type=int, default=10, metavar="N",
                   help="Show at most N entries (largest first) in the final "
                        "'File statistics' block -- use 0 for all files.")

    # converter flag
    P.add_argument("--convert", metavar="File or Directory",
                   help="Convert existing JSON transcripts to -f format then exit")

    args = P.parse_args()

    if args.public_proxy is not None:
        if args.public_proxy_type is None:
            if ProxyInterface is None:
                args.public_proxy_type = "socks"
                logging.info("Swiftshadow not installed; using SOCKS proxies")
            else:
                args.public_proxy_type = choice(["http", "https"])
                logging.info(
                    "Auto-selected %s public proxies",
                    args.public_proxy_type.upper(),
                )
        elif args.public_proxy_type in ("http", "https") and ProxyInterface is None:
            logging.warning(
                "Swiftshadow not installed; falling back to SOCKS proxies"
            )
            args.public_proxy_type = "socks"

    # ---------- optional format samples -------------------------------
    if args.formats_help:
        print(textwrap.dedent(f"""
        FORMAT EXAMPLES  (default output is **json** - pass "-f srt" etc. to change)
        --------------------------------------------------------------------------
        --- json
        {
          "stats": { "words": 1,234, "lines": 456, "chars": 8,765 },
          "video_id": "abc123",
          "title": "Demo",
          "url": "https://youtu.be/abc123",
          "language": "en",
          "transcript": [ … ]
        }

        --- srt
        NOTE stats: 1,234 words ·  456 lines ·  8,765 chars
        NOTE generated: 2025-06-17T12:34:56

        1
        00:00:00,000 --> 00:00:02,000
        Hello world!

        --- webvtt
        WEBVTT
        
        NOTE stats: 1,234 words ·  456 lines ·  8,765 chars
        NOTE generated: 2025-06-17T12:34:56

        00:00:00.000 --> 00:00:02.000
        Hello world!

        --- text      (plain; add -t for timestamps)
        # stats: 1,234 words · 456 lines · 8,765 chars
        # generated: 2025-06-17T12:34:56

        Hello world!

        --- pretty    (always timestamped; same as "text -t")
        # stats: 1,234 words · 456 lines · 8,765 chars

        # generated: 2025-06-17T12:34:56

        [00:00:00.000] Hello world!
        """))
        sys.exit(0)

    # ---------- convert-only short-circuit ----------------------------
    if args.convert:
        out_dir = Path(args.folder).expanduser(); out_dir.mkdir(parents=True, exist_ok=True)
        convert_existing(args.convert, args.format, out_dir,
                         include_stats=args.stats)
        return

    if not args.LINK:
        P.error("LINK is required unless --convert or --formats-help is used")

    # ---------- split flag parsing ------------------------------------
    split_limit: int | None = None
    split_unit: str | None  = None
    if args.split:
        m = re.fullmatch(r"(\d+)\s*([wWcClL])", args.split.strip())
        if not m:
            P.error("--split must be like 10000c / 8000w / 2500l")
        split_limit = int(m.group(1))
        split_unit  = m.group(2).lower()

    # ---------- enforce split-requires-concat ---------------------------
    if args.split and not args.concat:
        P.error("--split only makes sense together with --concat")

    async def _update_swiftshadow(mgr: ProxyInterface) -> None:
        """Safely refresh proxies regardless of library version."""
        # prefer the explicit async_update() API when present
        if hasattr(mgr, "async_update"):
            await mgr.async_update()
            return

        update_fn = getattr(mgr, "update", None)
        if not update_fn:
            return

        if inspect.iscoroutinefunction(update_fn):
            # async def update(); just await it directly
            await update_fn()
        else:
            # synchronous update() internally runs asyncio.run(); isolate in thread
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, update_fn)

    # ---------- logging setup -----------------------------------------
    log_file: Path | None = None
    _restore_streams: Callable[[], None] | None = None
    if not args.no_log:
        if args.log_file:
            log_file = Path(args.log_file).expanduser()
        else:
            ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            log_file = Path(args.folder).expanduser() / f"yt_bulk_cc_{ts}.log"

    if log_file:
        import atexit
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # ─────────────── console/file tee with ANSI-strip ───────────────
        _ANSI_RE = re.compile(r"\x1B\[[0-9;]*[A-Za-z]")

        class _Tee:
            """
            Duplicate every write/flush to both the real console stream
            *and* the log file, but scrub ANSI escape sequences from the
            file copy so the log remains plain-text.
            """

            def __init__(self, console_stream, file_stream):
                self._console = console_stream
                self._file    = file_stream

            def write(self, data):
                self._console.write(data)               # honour current capture
                self._file.write(_ANSI_RE.sub("", data))  # strip colours
                self._file.flush()                      # keep log in sync

            def flush(self):
                self._console.flush()
                self._file.flush()

        fh = log_file.open("w", encoding="utf-8")

        # Keep originals so we can put them back at shutdown.
        _orig_out, _orig_err = sys.stdout, sys.stderr   # may be a capture proxy

        sys.stdout = _Tee(_orig_out, fh)
        sys.stderr = _Tee(_orig_err, fh)

        def _restore_streams() -> None:
            """
            Undo the tee so the interpreter's final flush doesn't hit
            a closed file, then close the log.
            """
            sys.stdout, sys.stderr = _orig_out, _orig_err
            fh.close()

        # expose for manual cleanup at shutdown
        _restore_streams_fn = _restore_streams

        atexit.register(_restore_streams)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")

        # Timestamped format for the plain-text log.
        LOG_FMT_FILE = "%(asctime)s - %(levelname)s - %(message)s"
        DATE_FMT     = "%Y-%m-%d %H:%M:%S"
        file_handler.setFormatter(logging.Formatter(LOG_FMT_FILE, DATE_FMT))
        _restore_streams = _restore_streams_fn
    else:
        file_handler = None

    # ────────────── console vs. file log verbosity ──────────────
    console_level = [logging.WARNING, logging.INFO, logging.DEBUG][min(args.verbose, 2)]

    term_console = Console(file=sys.__stdout__, force_terminal=True)
    console_handler = RichHandler(
        console=term_console,
        show_time=False,
        show_level=True,
        show_path=False,
        markup=False,
    )
    console_handler.setLevel(console_level)

    if file_handler:
        # The file should *always* get every detail.
        file_handler.setLevel(logging.DEBUG)

    # Root logger level:
    #   • DEBUG if we *have* a file handler (so it can receive everything)
    #   • else match the console level to avoid wasting overhead
    root_logger_level = logging.DEBUG if file_handler else console_level

    logging.basicConfig(
        level=root_logger_level,
        handlers=[console_handler] + ([file_handler] if file_handler else []),
        force=True,
    )
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    # ---------- runtime tweaks ----------------------------------------
    if args.timestamps:
        FMT["text"]   = TimeStampedText(show=True)
        FMT["pretty"] = TimeStampedText(show=True)

    kind, ident = detect(args.LINK)
    out_dir = Path(args.folder).expanduser(); out_dir.mkdir(parents=True, exist_ok=True)

    videos = list(video_iter(kind, ident, args.limit, args.sleep))
    if args.limit:
        videos = videos[: args.limit]
    if not videos:
        logging.error("No videos found - is the link correct?")
        sys.exit(1)
    logging.info("Found %s videos", len(videos))

    proxy_pool: list[str] | None = None
    proxies: list[str] = []
    cli_proxies: list[str] = []
    file_proxies: list[str] = []
    if args.proxy:
        cli_proxies = [p.strip() for p in args.proxy.split(",") if p.strip()]
        proxies.extend(cli_proxies)
    if args.proxy_file:
        try:
            with open(args.proxy_file, "r", encoding="utf-8") as fh:
                file_proxies = [p.strip() for p in fh if p.strip()]
                proxies.extend(file_proxies)
        except Exception as e:
            logging.error("Cannot read proxy file %s (%s)", args.proxy_file, e)
            sys.exit(1)
    if args.public_proxy is not None:
        countries: list[str] = []
        if args.public_proxy_country:
            countries = [c.strip().upper() for c in args.public_proxy_country.split(',') if c.strip()]
        public: list[str] = []
        if args.public_proxy_type == "socks":
            try:
                resp = requests.get(
                    "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt",
                    timeout=10,
                )
                resp.raise_for_status()
                lines = [line.strip() for line in resp.text.splitlines() if line.strip()]
                public = [f"socks5://{line}" for line in lines[: args.public_proxy]]
                proxies.extend(public)
                logging.info("Loaded %d public SOCKS proxies", len(public))
            except Exception as e:
                logging.error("Failed to fetch SOCKS proxies: %s", e)
        else:
            if ProxyInterface is None:
                logging.error("Swiftshadow not installed")
            else:
                try:
                    mgr = ProxyInterface(
                        countries=countries,
                        protocol=args.public_proxy_type,
                        maxProxies=args.public_proxy,
                        autoUpdate=False,
                    )
                    await _update_swiftshadow(mgr)
                    public = [p.as_string() for p in mgr.proxies]
                    proxies.extend(public)
                    logging.info(
                        "Loaded %d public %s proxies via Swiftshadow",
                        len(public),
                        args.public_proxy_type.upper(),
                    )
                except Exception as e:
                    logging.error("Swiftshadow failed: %s", e)
    public_count = len(public) if args.public_proxy is not None else 0
    if cli_proxies or file_proxies or public_count:
        logging.info(
            "Loaded %d proxies (CLI %d, file %d, public %d)",
            len(cli_proxies) + len(file_proxies) + public_count,
            len(cli_proxies),
            len(file_proxies),
            public_count,
        )

    proxy_cfg = None
    if proxies:
        if len(proxies) == 1:
            entry = proxies[0]
            if entry.lower().startswith(("ws://", "webshare://")):
                creds = entry.split("://", 1)[1]
                try:
                    user, pwd = creds.split(":", 1)
                except ValueError:
                    logging.error("Webshare proxy requires ws://user:pass")
                    sys.exit(1)
                proxy_cfg = WebshareProxyConfig(user, pwd)
            else:
                proxy_cfg = _make_proxy(entry)
        else:
            proxy_pool = proxies
    if proxy_pool and proxy_cfg:
        logging.debug("Single proxy supplied; ignoring proxy list")

    cookies_data: list | None = None
    if args.cookie_json:
        try:
            with open(args.cookie_json, "rb") as fh:
                cookies_data = json.load(fh)
        except Exception as e:
            logging.error("Cannot read cookies file %s (%s)", args.cookie_json, e)
            sys.exit(1)

    pre_results: list[tuple[str, str, str]] = []
    banned_proxies: set[str] = set()

    if args.check_ip:
        from .core import probe_video
        first_vid = videos[0]["videoId"]
        ok_probe, banned_proxies = probe_video(
            first_vid,
            cookies=cookies_data,
            proxy_pool=proxy_pool,
            proxy_cfg=proxy_cfg,
            banned=banned_proxies,
        )
        if not ok_probe:
            logging.error("IP appears blocked; aborting")
            for v in videos:
                title = slug(v["title"]["runs"][0]["text"])
                pre_results.append(("fail", v["videoId"], title))

    sem     = asyncio.Semaphore(args.jobs)
    tasks   = []
    skipped = []

    digits = len(str(len(videos)))       # width for zero-padding

    if not pre_results:
        for idx, v in enumerate(videos, 1):
            vid   = v["videoId"]
            title = slug(v["title"]["runs"][0]["text"])
            prefix = "" if args.no_seq_prefix else f"{idx:0{digits}d} "
            fpath  = out_dir / f"{prefix}[{vid}] {title}.{EXT[args.format]}"
            fpath  = _shorten_for_windows(fpath)        # NEW
            if fpath.exists() and not args.overwrite:
                skipped.append(("old", vid, title))
                continue
            tasks.append(
                grab(
                    vid,
                    title,
                    fpath,
                    args.language or [],
                    args.format,
                    sem,
                    proxy_pool=proxy_pool,
                    proxy_cfg=proxy_cfg,
                    cookies=cookies_data,
                    include_stats=args.stats and not args.concat,
                    delay=args.sleep,
                    banned=banned_proxies,
                    verify_ssl=args.verify_ssl,
                )
            )

    if not tasks and not skipped and not pre_results:
        logging.info("Nothing to do (all files already present).")
        return

    # ---------- run downloads (with optional Rich progress) ------------
    try:
        from rich.progress import (
            Progress,
            SpinnerColumn,
            BarColumn,
            TextColumn,
        )
        async def rich_gather(coros):
            # Use the same Console as the logging handler so progress updates
            # never reach the tee-ed log file.
            with Progress(
                SpinnerColumn(),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                console=term_console,
            ) as bar:
                tid = bar.add_task("Downloading", total=len(coros))
                res = []
                for fut in asyncio.as_completed(coros):
                    res.append(await fut)
                    bar.update(tid, advance=1)
                return res
        # Keep the log file at DEBUG but silence the *console* only,
        # so the Rich bar is not garbled by warnings.
        orig_console_level = console_handler.level    # ← defined earlier
        console_handler.setLevel(logging.ERROR)
        try:
            results = await rich_gather(tasks)
        finally:
            console_handler.setLevel(orig_console_level)
            # make sure everything buffered in the file handler is flushed
            for h in logging.getLogger().handlers:
                if isinstance(h, logging.FileHandler):
                    h.flush()
    except ModuleNotFoundError:
        results = await asyncio.gather(*tasks)

    results = pre_results + results

    ok   = [r for r in results if r[0] == "ok"] + skipped
    none = [r for r in results if r[0] == "none"]
    fail = [r for r in results if r[0] == "fail"]
    
    # If nothing was actually downloaded, drop the auto-generated run-log so
    # test_no_caption_flow sees an empty output directory.
    if log_file and not ok and not fail:
        try: log_file.unlink()
        except FileNotFoundError: pass


    # -----------------------------------------------------------------
    # Defer the human-readable post-run summary until *everything*
    # (concatenation, stats, etc.) has already written to the log file.
    # This guarantees it is the *last* block in the log.
    # -----------------------------------------------------------------
    def _emit_final_summary() -> None:
        """
        Write the per-category lists first, then the one-liner roll-up so the
        **last** record in both the console *and* the file log is always the
        coloured 'Summary: …' line.
        """
        if none:
            print(f"\n{C.YEL}Videos without captions:{C.END}")
            for _, vid, title in none:
                print(f"{C.YEL}  • https://youtu.be/{vid} — {title[:70]}{C.END}")

        if fail:
            print(f"\n{C.RED}Videos that ultimately failed:{C.END}")
            for _, vid, title in fail:
                print(f"{C.RED}  • https://youtu.be/{vid} — {title[:70]}{C.END}")

        # make sure everything printed so far is on disk before appending
        sys.stdout.flush()
        # Emit the roll-up *after* the lists (console only).
        # plain echo guarantees the final line is literally "Summary: …"
        print(
            f"Summary: ✓ {C.GRN}{len(ok)}{C.END}   •  "
            f"↯ no-caption {C.YEL}{len(none)}{C.END}   •  "
            f"⚠ failed {C.RED}{len(fail)}{C.END}   "
            f"🚫 proxies banned {C.RED}{len(banned_proxies)}{C.END}   "
            f"(total {len(ok)+len(none)+len(fail)})"
        )
        if banned_proxies:
            formatted = "\n".join(f"  • {p}" for p in sorted(banned_proxies))
            logging.info("Banned proxies:\n%s", formatted)
            print("Banned proxies:")
            for p in sorted(banned_proxies):
                print(f"  • {p}")
        sys.stdout.flush()

    # --------------- concatenation / splitting ------------------------
    stats_files: list[Path] = []
    _seen_stats: set[Path] = set()

    if args.concat and ok:
        logging.info("Per-file stats are disabled during concatenation")
        base_name    = args.basename
        concat_paths = []

        # —— JSON concat (with split) ————————————————————————
        if args.format == "json":
            current_objs: list = []
            meta_list   : list[tuple[str,str]] = []
            w_tot = l_tot = c_tot = 0
            file_idx = 1

            def _flush_json():
                nonlocal current_objs, w_tot, l_tot, c_tot, file_idx, meta_list
                fname = (f"{base_name}_{file_idx:05d}" if split_limit else base_name)
                tgt   = out_dir / f"{fname}.json"
                # ------------------------------------------------------------------
                # Make every item's stats *self-consistent* with the pretty-printed
                # version that finally lands in the file (indent=2, trailing \n).
                # ------------------------------------------------------------------
                for it in current_objs:
                    while True:
                        txt = json.dumps(it, indent=2, ensure_ascii=False)
                        if not txt.endswith("\n"):
                            txt += "\n"
                        w_i, l_i, c_i = _stats(txt)
                        wanted = {"words": w_i, "lines": l_i, "chars": c_i}
                        if it.get("stats") == wanted:
                            break          # already correct
                        it["stats"] = wanted

                payload = {"items": current_objs}

                # ── final-serialise once, measure, then (optionally) embed stats ──
                txt = json.dumps(payload, ensure_ascii=False, indent=2)
                if not txt.endswith("\n"):
                    txt += "\n"
                if args.stats:
                    while True:                       # converges in ≤2 iterations
                        txt  = json.dumps(payload, indent=2, ensure_ascii=False)
                        new  = _stats(txt)
                        if payload.get("stats") == {"words": new[0], "lines": new[1], "chars": new[2]}:
                            break                     # self-consistent
                        payload["stats"] = {"words": new[0], "lines": new[1], "chars": new[2]}

                tgt.write_text(txt, encoding="utf-8")
                concat_paths.append(tgt)
                if tgt not in _seen_stats:
                    _seen_stats.add(tgt)
                    stats_files.append(tgt)
                current_objs = []; w_tot = l_tot = c_tot = 0
                meta_list = []
                file_idx += 1

            for v_idx, v in enumerate(videos, 1):
                vid = v["videoId"]

                # skip videos that were "none" or "fail"
                for _, v_ok, title in ok:
                    if v_ok == vid:
                        break
                else:
                    continue

                # ── locate the file regardless of an optional 00001-style prefix
                try:
                    pattern = f"*{glob.escape('[' + vid + ']')}*.json"
                    src = next(out_dir.glob(pattern))
                except StopIteration:
                    logging.warning("File for %s not found - prefix off?", vid)
                    continue

                try:
                    obj_txt = src.read_text(encoding="utf-8")
                    obj     = json.loads(obj_txt)
                except Exception as e:
                    logging.warning("Skip corrupted JSON %s (%s)", src.name, e)
                    continue

                w_p, l_p, c_p = _stats(obj_txt)
                exceed = (
                    split_limit
                    and (
                        (split_unit == "w" and w_tot + w_p > split_limit)
                        or (split_unit == "l" and l_tot + l_p > split_limit)
                        or (split_unit == "c" and c_tot + c_p > split_limit)
                    )
                )
                if exceed and current_objs:
                    _flush_json()

                current_objs.append(obj)
                meta_list.append((vid, title))
                w_tot += w_p
                l_tot += l_p
                c_tot += c_p

            if current_objs:
                _flush_json()

        # —— Text / SRT / VTT concat (streaming) ————————————————
        else:
            SEP = lambda v,t: f"\n──── {v} ── {t[:50]} ─────────────────────────\n"
            file_idx = 1
            fname    = (f"{base_name}_{file_idx:05d}" if split_limit else base_name)
            tgt      = out_dir / f"{fname}.{EXT[args.format]}"
            dst      = tgt.open("w", encoding="utf-8")
            concat_paths.append(tgt)
            if tgt not in _seen_stats:
                _seen_stats.add(tgt)
                stats_files.append(tgt)
            w_tot = l_tot = c_tot = 0
            meta_list: list[tuple[str,str]] = []

            def _rollover():
                nonlocal file_idx, dst, w_tot, l_tot, c_tot, tgt, meta_list
                dst.close()
                if args.stats:
                    hdr,_w,_l,_c = _fixup_loop((w_tot,l_tot,c_tot),
                                               args.format, meta_list)
                    _prepend_header(concat_paths[-1], hdr)
                file_idx += 1
                fname = f"{base_name}_{file_idx:05d}"
                tgt   = out_dir / f"{fname}.{EXT[args.format]}"
                dst   = tgt.open("w", encoding="utf-8")
                concat_paths.append(tgt)
                if tgt not in _seen_stats:
                    _seen_stats.add(tgt)
                    stats_files.append(tgt)
                w_tot = l_tot = c_tot = 0; meta_list=[]

            for v in videos:
                vid = v["videoId"]
                for _, v_ok, title in ok:
                    if v_ok == vid:
                        break
                else:
                    continue
                try:
                    pattern = f"*{glob.escape('[' + vid + ']')}*.{EXT[args.format]}"
                    src = next(out_dir.glob(pattern))
                except StopIteration:
                    logging.warning("File for %s not found - prefix off?", vid)
                    continue
                try:
                    txt = src.read_text(encoding="utf-8")
                except Exception as e:
                    logging.warning("Skip unreadable file %s (%s)", src.name, e)
                    continue
                piece = SEP(vid, title) + txt + "\n"
                w_p, l_p, c_p = _stats(piece)
                pred_meta = meta_list + [(vid, title)]
                body_w = w_tot + w_p
                body_l = l_tot + l_p
                body_c = c_tot + c_p
                if args.stats:
                    _, pred_w, pred_l, pred_c = _fixup_loop(
                        (body_w, body_l, body_c), args.format, pred_meta
                    )
                else:
                    pred_w, pred_l, pred_c = body_w, body_l, body_c

                exceed = (
                    split_limit
                    and (
                        (split_unit == "w" and pred_w > split_limit)
                        or (split_unit == "l" and pred_l > split_limit)
                        or (split_unit == "c" and pred_c > split_limit)
                    )
                )
                if exceed and (w_tot or l_tot or c_tot):
                    _rollover()
                    pred_meta = [(vid, title)]
                    body_w = w_p
                    body_l = l_p
                    body_c = c_p
                    if args.stats:
                        _, pred_w, pred_l, pred_c = _fixup_loop(
                            (body_w, body_l, body_c), args.format, pred_meta
                        )
                    else:
                        pred_w, pred_l, pred_c = body_w, body_l, body_c
                dst.write(piece)
                meta_list.append((vid, title))
                w_tot += w_p; l_tot += l_p; c_tot += c_p
            dst.close()
            # ── compute self-consistent header & patch placeholder ───
            if args.stats:
                hdr, w_tot, l_tot, c_tot = _fixup_loop((w_tot,l_tot,c_tot),
                                                       args.format, meta_list)
                _prepend_header(concat_paths[-1], hdr)

        if log_file:
            logging.info("Concatenated output → %s",
                         ", ".join(p.name for p in concat_paths))
        print(f"\n{C.GRN}✅  Concatenated transcripts saved to:{C.END}")
        for p in concat_paths: print(f"   {p}")
        print()

    # if not concatenated, compute stats for each individual ok/old file
    if not args.concat:
        for _, vid, title in ok:
            try:
                p = next(out_dir.glob(f"*{vid}*.{EXT[args.format]}"))
                if p not in _seen_stats:
                    _seen_stats.add(p)
                    stats_files.append(p)
            except StopIteration:
                continue

    # —— statistics summary ————————————————————————————————
    if stats_files:
        ranked = sorted(
            stats_files,
            key=lambda p: _stats(p.read_text(encoding="utf-8", errors="ignore"))[2],
            reverse=True,
        )
        if args.stats_top:
            ranked = ranked[: args.stats_top]

        header_txt = "File statistics:"
        if len(ranked) == 1:
            header_txt = "File statistics (top 1):"
        elif args.stats_top and args.stats_top < len(stats_files):
            header_txt = f"File statistics (top {len(ranked)}):"

        print(f"{C.BLU}{header_txt}{C.END}")
        pad = len(str(len(ranked))) or 1          # dynamic width
        for idx, p in enumerate(ranked, 1):
            try:
                txt = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            w,l,c = _stats(txt)
            print(f"  {idx:0{pad}d}. {p.name} - {C.GRN}{w:,}{C.END} w · "
                  f"{C.GRN}{l:,}{C.END} l · {C.GRN}{c:,}{C.END} c")
        print()

    if args.concat and log_file:
        print(f"📝  Full log: {C.BLU}{log_file}{C.END}\n")

    _emit_final_summary()

    # make absolutely sure the summary really is the last record
    for h in logging.getLogger().handlers:
        h.flush()
    logging.shutdown()
    if _restore_streams:
        try:
            _restore_streams()  # ensure no further output reaches the log
        except Exception:
            pass

    # if anything genuinely failed, propagate non-zero exit for CI
    if fail:
        sys.exit(2)


async def main() -> None:
    """Entry point used by both CLI and tests."""
    def _sigint(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, _sigint)

    try:
        await _main()
    except KeyboardInterrupt:
        logging.warning("Interrupted by user")
        print(f"\n{C.BLU}Aborted by user{C.END}")
        sys.exit(130)


def cli_entry():
    """Synchronous entry point for the console script."""
    if sys.platform.startswith("linux"):
        try:
            import uvloop
            uvloop.install()
        except ModuleNotFoundError:
            pass  # Fallback to standard asyncio

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # The `main` function has its own handler, but this is a fallback
        # for interrupts that occur before the event loop is running.
        print(f"\n{C.BLU}Aborted by user{C.END}")
        sys.exit(130)


# ────────────────────────── bootstrap ────────────────────────────────
if __name__ == "__main__":
    cli_entry()
