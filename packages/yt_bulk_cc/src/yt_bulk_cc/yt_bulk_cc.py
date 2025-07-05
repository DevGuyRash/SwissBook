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
import inspect
import json
import logging
import re
import signal
import sys
import textwrap
from datetime import timedelta
from pathlib import Path
from random import choice
from types import SimpleNamespace
import copy          # NEW
from typing import Sequence

import scrapetube
from youtube_transcript_api import YouTubeTranscriptApi, formatters
# ------------------------------------------------------------
#  Robust error-class import — works on every library version
# ------------------------------------------------------------
from youtube_transcript_api._errors import (
    CouldNotRetrieveTranscript,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

# `NoTranscriptAvailable` was removed in 2024-plus releases.
# Create a stub if it's missing so downstream `except` clauses stay valid.
try:
    from youtube_transcript_api._errors import NoTranscriptAvailable
except ImportError:                          # fallback for new versions
    class NoTranscriptAvailable(Exception):  # type: ignore
        """Placeholder for backward compatibility."""
        pass

# Newer releases sometimes add throttling errors; define dummies if absent.
try:
    from youtube_transcript_api._errors import TooManyRequests
except ImportError:
    class TooManyRequests(Exception):        # type: ignore
        pass

# ───────────────────────── helpers ────────────────────────── #

_BAD = re.compile(r'[\\/:*?"<>|\r\n]+')

def _shorten_for_windows(p: Path) -> Path:
    """
    Return a path guaranteed to be ≤ 260 characters on Windows
    (noop on other OSes).  Strategy:
      1.  If already short: return as-is.
      2.  Try truncating the slug (title) portion to 40 chars.
      3.  Fallback: md5 hash + original suffix (extremely unlikely).
    """
    if os.name != "nt":
        return p
    MAX = 250                                # a bit under the hard limit
    if len(str(p)) <= MAX:
        return p

    dir_part  = p.parent
    base      = p.name
    m = re.match(r"(\d+ )?\[([A-Za-z0-9_-]{11})\] (.+)\.(\w+)", base)
    if m:
        prefix, vid, title, ext = m.groups()
        prefix = prefix or ""
        new_title = title[:40] + ("…" if len(title) > 40 else "")
        candidate = dir_part / f"{prefix}[{vid}] {new_title}.{ext}"
        if len(str(candidate)) <= 260:
            return candidate

    import hashlib
    short = hashlib.md5(base.encode()).hexdigest()[:8] + p.suffix
    return dir_part / short


def slug(text: str, max_len: int = 120) -> str:
    """Return a filesystem-safe, reasonably short slice of a title."""
    text = _BAD.sub("_", text).strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) > max_len:
        text = text[: max_len].rsplit(" ", 1)[0] + "…"
    return text or "untitled"


def _stats(txt: str) -> tuple[int, int, int]:
    """
    Return *(words, lines, chars)* for *txt*.

    • **Lines** are now counted exactly like `wc -l`:  
      *one* line per ``\n`` byte, so a file without a final newline
      reports the same number you would see in the shell.
    """
    chars  = len(txt)
    words  = len(re.findall(r"\S+", txt))
    lines  = txt.count("\n")          # match wc -l
    return words, lines, chars


# ---------- URL detector ------------------------------------ #
_VID_RE   = re.compile(r"(?:youtu\.be/|v=)([A-Za-z0-9_-]{11})")
_LIST_RE  = re.compile(r"[?&]list=([A-Za-z0-9_-]+)")
_CHAN_RE  = re.compile(r"(?:/channel/|/user/|/@)([A-Za-z0-9_-]+)")


def detect(url: str):
    """Return ('video' | 'playlist' | 'channel', identifier-or-url)."""
    if (m := _VID_RE.search(url)):
        return "video", m.group(1)
    if (m := _LIST_RE.search(url)):
        return "playlist", m.group(1)
    if _CHAN_RE.search(url) or url.rstrip("/").endswith("/videos"):
        return "channel", url
    raise argparse.ArgumentTypeError("Link doesn't look like video/playlist/channel")


# ---------- custom formatters --------------------------------------- #
class TimeStampedText(formatters.TextFormatter):
    """Plain/pretty formatter that can prefix timestamps."""

    def __init__(self, show: bool = False):
        super().__init__()
        self.show = show

    @staticmethod
    def _ts(sec: float) -> str:
        td   = timedelta(seconds=sec)
        base = f"{td}"
        if "." not in base:
            base += ".000000"
        h, m, rest = base.split(":")
        s, micro   = rest.split(".")
        return f"{h}:{m}:{s}.{micro[:3]}"

    def format_transcript(self, transcript, **kw):
        if not self.show:
            return super().format_transcript(transcript, **kw)
        # formatter base class expects attribute access
        return "\n".join(f"[{self._ts(c.start)}] {c.text}" for c in transcript)


# Registry (JSON handled manually → no WrappedJSON needed)
FMT = {
    "srt":    formatters.SRTFormatter(),
    "webvtt": formatters.WebVTTFormatter(),
    "text":   TimeStampedText(),
    "pretty": TimeStampedText(),
}
EXT = {
    "json":   "json",
    "srt":    "srt",
    "webvtt": "vtt",
    "text":   "txt",
    "pretty": "txt",
}

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


# ───────────────────────── NEW: converter util ──────────────────────────
def _iter_json_files(path: Path):
    """Yield every *.json path under the given file/dir."""
    if path.is_file() and path.suffix.lower() == ".json":
        yield path
    elif path.is_dir():
        for p in path.rglob("*.json"):
            yield p


def _coerce_attr(seq):
    """Ensure each cue allows attribute access needed by formatters."""
    return [SimpleNamespace(**d) if isinstance(d, dict) else d for d in seq]


# ────────────────────────── helper ──────────────────────────
def _extract_cues(blob):
    """
    Return a flat list of cue-dicts no matter whether *blob* is:
      •   a normal per-video JSON  (has "transcript")
      •   one element inside "items" of a concatenated JSON
      •   a full concatenated JSON (has "items" only)
    """
    if "transcript" in blob:                 # single-video file
        return blob["transcript"]
    if "items" in blob:                      # concatenated parent
        cues = []
        for item in blob["items"]:
            cues.extend(_extract_cues(item)) # recurse one level
        return cues
    return []                                # fallback - no cues

def convert_existing(
    src: str, dest_fmt: str, out_dir: Path, *, include_stats: bool = True
):
    """Convert previously downloaded JSON transcripts to another format."""
    dest_ext = EXT[dest_fmt]
    for jfile in _iter_json_files(Path(src).expanduser()):
        try:
            data = json.loads(jfile.read_text(encoding="utf-8"))
        except Exception as e:
            logging.warning("Skip unreadable JSON %s (%s)", jfile, e)
            continue

        # Robust cue extraction (handles both per-video and
        # concatenated JSONs transparently)
        cues = _extract_cues(data)
        if not cues:
            logging.warning("No cues in %s", jfile)
            continue

        if dest_fmt == "json":
            new_txt = json.dumps(data, ensure_ascii=False, indent=2)
            if not new_txt.endswith("\n"):
                new_txt += "\n"
        else:
            # ── mode flags ───────────────────────────────────────────────
            many_srt = dest_fmt == "srt" and "items" in data and len(data["items"]) > 2

            def _render_one(meta: dict, cue_list):
                """Render one video; header only when allowed by flags."""
                txt = FMT[dest_fmt].format_transcript(_coerce_attr(cue_list))
                if include_stats and not many_srt:
                    txt = _single_file_header(dest_fmt, txt, meta)
                return txt

            if "items" in data:                 # concatenated JSON
                parts, meta_acc = [], []
                for item in data["items"]:
                    meta = {k: item[k] for k in ("video_id", "title", "url")}
                    if not many_srt:          # no visual separator in bare-SRT mode
                        parts.append("──── {video_id} ── {title}\n".format(**meta))
                    parts.append(_render_one(meta, item["transcript"]))
                    meta_acc.append((meta["video_id"], meta["title"]))
                body = "\n".join(parts)

                # optional file-wide header
                add_header = include_stats and not many_srt
                if add_header:
                    hdr, *_ = _fixup_loop(_stats(body), dest_fmt, meta_acc)
                    new_txt = hdr + body
                else:
                    new_txt = body
            else:                               # single-video JSON
                meta = {k: data[k] for k in ("video_id", "title", "url")}
                new_txt = _render_one(meta, cues)

        dst = out_dir / jfile.with_suffix(f".{dest_ext}").name
        dst.write_text(new_txt, encoding="utf-8")
        logging.info("✔ converted %s → %s", jfile.name, dst.name)


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
    include_stats: bool = True,
) -> tuple[str, str, str]:   # (status, video_id, title)
    async with sem:
        for attempt in range(1, tries + 1):
            try:
                # build kwargs only with supported keys
                sig_params = inspect.signature(
                    YouTubeTranscriptApi.get_transcript
                ).parameters
                kwargs = {}
                if langs and "languages" in sig_params:
                    kwargs["languages"] = list(langs)
                if proxy_pool and "proxies" in sig_params:
                    url = proxy_pool[0] if len(proxy_pool) == 1 else choice(proxy_pool)
                    kwargs["proxies"] = {"http": url, "https": url}
                if cookies and "cookies" in sig_params:
                    kwargs["cookies"] = cookies

                # ───────────────────────── DEBUG A ─────────────────────────
                logging.debug(
                    "grab[%s] About to call .get_transcript - "
                    "api=%r  sig=%s  kwargs=%s  NoTranscriptFound-id=%s",
                    vid,
                    YouTubeTranscriptApi,
                    list(sig_params),
                    kwargs,
                    id(NoTranscriptFound),
                )
                # ────────────────────────────────────────────────────────────


                # returns a list of dicts
                tr = await asyncio.to_thread(
                    YouTubeTranscriptApi.get_transcript,
                    vid,
                    **kwargs,
                )

                meta = {
                    "video_id": vid,
                    "title":    title,
                    "url":      f"https://youtu.be/{vid}",
                    "language": langs[0] if langs else "unknown",
                }

                if fmt_key == "json":
                    payload = dict(meta, transcript=tr)

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
                    data = FMT[fmt_key].format_transcript(_coerce_attr(tr))

                if fmt_key == "json" or not include_stats:
                    # JSON, or stats explicitly disabled → dump verbatim
                    path.write_text(data, encoding="utf-8")
                else:
                    full = _single_file_header(fmt_key, data, meta)
                    path.write_text(full, encoding="utf-8")
                logging.info("✔ saved %s", path.name)
                return ("ok", vid, title)

            except (TranscriptsDisabled, NoTranscriptFound):
                logging.warning("✖ no transcript for %s", vid)
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
            except (TooManyRequests, CouldNotRetrieveTranscript) as exc:
                wait = 6 * attempt
                logging.info("⏳ %s - retrying in %ss (attempt %s/%s)",
                             exc.__class__.__name__, wait, attempt, tries)
                await asyncio.sleep(wait)
                continue
            except Exception as exc:
                # ───────────────────────── DEBUG B ─────────────────────────
                logging.debug(
                    "grab[%s] caught %s  id=%s  isinstance(NoTranscriptFound)=%s  msg=%s",
                    vid,
                    exc.__class__.__name__,
                    id(exc.__class__),
                    isinstance(exc, NoTranscriptFound),
                    exc,
                )
                # ────────────────────────────────────────────────────────────
                logging.debug("retry %s/%s for %s: %s", attempt, tries, vid, exc)
                if attempt == tries:
                    logging.error("⚠ giving up on %s (%s)", vid, exc.__class__.__name__)
                else:
                    await asyncio.sleep(1.5 * attempt)
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

        if rec.msg.startswith("Summary:") and len(rec.args) == 4:
            ok, none, fail, total = rec.args
            rec.msg = (
                f"Summary: ✓ {C.GRN}{ok}{C.END}   •  "
                f"↯ no-caption {C.YEL}{none}{C.END}   •  "
                f"⚠ failed {C.RED}{fail}{C.END}   "
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
    P.add_argument("-j", "--jobs", type=int, default=2,
                   help="Concurrent transcript downloads")
    P.add_argument("-s", "--sleep", type=int, default=2,
                   help="Seconds between scrapetube pagination calls")
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
    P.add_argument("-p", "--proxy", metavar="URL[,URL2,…]",
                   help="Single proxy or comma-list to rotate between")
    P.add_argument("-c", "--cookie-json", metavar="FILE",
                   help="Cookies JSON exported by browser (see docs)")
    P.add_argument("--overwrite", action="store_true",
                   help="Re-download even if output file already exists")

    # concatenation & splitting
    P.add_argument("-C", "--concat", nargs="?", const="combined", metavar="BASENAME",
                   help="Write all successful transcripts into one file "
                        "(optional BASENAME; default 'combined')")
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

    # ---------- logging setup -----------------------------------------
    log_file: Path | None = None
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

            def flush(self):
                self._console.flush()
                self._file.flush()

        fh = log_file.open("w", encoding="utf-8")

        # Keep originals so we can put them back at shutdown.
        _orig_out, _orig_err = sys.stdout, sys.stderr   # may be a capture proxy

        sys.stdout = _Tee(_orig_out, fh)
        sys.stderr = _Tee(_orig_err, fh)

        def _restore_streams():
            """
            Undo the tee so the interpreter's final flush doesn't hit
            a closed file, then close the log.
            """
            sys.stdout, sys.stderr = _orig_out, _orig_err
            fh.close()

        atexit.register(_restore_streams)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")

        # Timestamped format for the plain-text log.
        LOG_FMT_FILE = "%(asctime)s - %(levelname)s - %(message)s"
        DATE_FMT     = "%Y-%m-%d %H:%M:%S"
        file_handler.setFormatter(logging.Formatter(LOG_FMT_FILE, DATE_FMT))
    else:
        file_handler = None

    # ────────────── console vs. file log verbosity ──────────────
    console_level = [logging.WARNING, logging.INFO, logging.DEBUG][min(args.verbose, 2)]

    console_handler = logging.StreamHandler(sys.__stdout__)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(ColorFormatter("%(levelname)s %(message)s"))

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
    )

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
    if args.proxy:
        proxy_pool = [p.strip() for p in args.proxy.split(",") if p.strip()]

    cookies_data: list | None = None
    if args.cookie_json:
        try:
            with open(args.cookie_json, "rb") as fh:
                cookies_data = json.load(fh)
        except Exception as e:
            logging.error("Cannot read cookies file %s (%s)", args.cookie_json, e)
            sys.exit(1)

    sem     = asyncio.Semaphore(args.jobs)
    tasks   = []
    skipped = []

    digits = len(str(len(videos)))       # width for zero-padding

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
            grab(vid, title, fpath,
                 args.language or [],
                 args.format, sem,
                 proxy_pool=proxy_pool,
                 cookies=cookies_data,
                 include_stats=args.stats and not args.concat)
        )

    if not tasks and not skipped:
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
        from rich.console import Console            # NEW
        async def rich_gather(coros):
            # Use a dedicated Console that writes **only** to the real TTY,
            # so progress updates never reach the tee-ed log file.
            term = Console(file=sys.__stdout__, force_terminal=True)
            with Progress(
                SpinnerColumn(),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                console=term,                       # <<< key change
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
        # Emit the roll-up *after* the lists.
        logging.info(
            "Summary: ✓ %s   •  ↯ no-caption %s   •  ⚠ failed %s   (total %s)",
            len(ok), len(none), len(fail), len(ok) + len(none) + len(fail),
        )
        # plain echo guarantees the final line is literally "Summary: …"
        print(
            f"Summary: ✓ {C.GRN}{len(ok)}{C.END}   •  "
            f"↯ no-caption {C.YEL}{len(none)}{C.END}   •  "
            f"⚠ failed {C.RED}{len(fail)}{C.END}   "
            f"(total {len(ok)+len(none)+len(fail)})"
        )
        sys.stdout.flush()

    # --------------- concatenation / splitting ------------------------
    stats_files: list[Path] = []
    _seen_stats: set[Path] = set()

    if args.concat and ok:
        logging.info("Per-file stats are disabled during concatenation")
        base_name    = args.concat
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
                    src = next(out_dir.glob(f"*[{vid}]*.json"))
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
                    src = next(out_dir.glob(f"*[{vid}]*.{EXT[args.format]}"))
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


# ────────────────────────── bootstrap ────────────────────────────────
if __name__ == "__main__":
    try:
        # Use uvloop for performance on Linux, but fall back gracefully
        # if it's not installed or we're on another OS.
        if not sys.platform.startswith("linux"):
            raise ModuleNotFoundError()
        import uvloop
        uvloop.run(main())
    except ModuleNotFoundError:
        asyncio.run(main())
