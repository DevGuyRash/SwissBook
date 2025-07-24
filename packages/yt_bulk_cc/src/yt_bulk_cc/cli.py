from __future__ import annotations

import argparse
import warnings
import time
import concurrent.futures
import copy
import asyncio
import datetime
import glob
import json
import logging
import os
import re
import signal
import sys
import textwrap
from pathlib import Path
from typing import Sequence

import requests
from rich.console import Console
from rich.logging import RichHandler

from .user_agent import _pick_ua
from .utils import (
    coerce_attr,
    shorten_path as _shorten_for_windows,
    slug,
    stats as _stats,
    make_proxy as _make_proxy,
)
from .formatters import TimeStampedText, FMT, EXT
from .converter import convert_existing
from .header import _single_file_header, _fixup_loop, _header_text, _prepend_header

try:
    from swiftshadow.classes import ProxyInterface
    from swiftshadow import QuickProxy
except Exception:  # pragma: no cover - optional dep
    ProxyInterface = None  # type: ignore
    QuickProxy = None  # type: ignore

try:
    from site_downloader.proxy import ProxyPool
except Exception:  # pragma: no cover - optional dep
    ProxyPool = None  # type: ignore
from .errors import (
    CouldNotRetrieveTranscript,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
    TooManyRequests,
    IpBlocked,
)


class C:
    """ANSI colour codes."""

    GRN = "\033[92m"
    BLU = "\033[94m"
    RED = "\033[91m"
    YEL = "\033[93m"
    END = "\033[0m"


class ColorFormatter(logging.Formatter):
    """Colourise console output without polluting other handlers."""

    COLORS = {
        logging.DEBUG: C.BLU,
        logging.INFO: C.GRN,
        logging.WARNING: C.YEL,
        logging.ERROR: C.RED,
        logging.CRITICAL: C.RED,
    }

    def format(self, record):  # type: ignore[override]
        rec = copy.copy(record)
        color = self.COLORS.get(rec.levelno, C.END)
        rec.levelname = f"{color}{rec.levelname}{C.END}"
        if rec.levelno >= logging.WARNING:
            rec.msg = f"{color}{rec.getMessage()}{C.END}"
            rec.args = ()
        if rec.msg.startswith("Summary:") and len(rec.args) == 6:
            ok, none, fail, proxy_fail, banned, total = rec.args
            rec.msg = (
                f"Summary: ✓ {C.GRN}{ok}{C.END}   •  "
                f"↯ no-caption {C.YEL}{none}{C.END}   •  "
                f"⚠ failed {C.RED}{fail}{C.END}   "
                f"🌐 proxy-failed {C.RED}{proxy_fail}{C.END}   "
                f"🚫 banned {C.RED}{banned}{C.END}   "
                f"(total {total})"
            )
            rec.args = ()
        return super().format(rec)


async def _main() -> None:
    class _ManFmt(
        argparse.ArgumentDefaultsHelpFormatter, argparse.RawTextHelpFormatter
    ):
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
    P.add_argument("LINK", nargs="?", help="Video, playlist, or channel URL")
    P.add_argument("-o", "--folder", default=".", help="Destination directory")
    P.add_argument(
        "-l",
        "--language",
        action="append",
        help="Preferred language code (repeatable, priority first)",
    )
    P.add_argument(
        "-f",
        "--format",
        choices=list(FMT) + ["json"],
        default="json",
        help="Output format",
    )
    P.add_argument(
        "-t",
        "--timestamps",
        action="store_true",
        help="Prefix each cue with [hh:mm:ss.mmm] in text / pretty modes",
    )
    P.add_argument(
        "-n", "--limit", type=int, help="Stop after N videos (handy for testing)"
    )
    P.add_argument(
        "-j", "--jobs", type=int, default=1, help="Concurrent transcript downloads"
    )
    P.add_argument(
        "-s",
        "--sleep",
        type=float,
        default=2.0,
        help="Seconds to wait between requests and after each download",
    )
    P.add_argument(
        "-v", "--verbose", action="count", default=0, help="-v=info, -vv=debug"
    )
    P.add_argument(
        "--no-seq-prefix",
        action="store_true",
        help="Don't prefix output filenames with 00001 … ordering (prefix is ON by default)",
    )
    stats_group = P.add_mutually_exclusive_group()
    stats_group.add_argument(
        "--stats",
        dest="stats",
        action="store_true",
        help="Embed per-file stats headers (default)",
    )
    stats_group.add_argument(
        "--no-stats",
        dest="stats",
        action="store_false",
        help="Skip stats headers / blocks",
    )
    P.set_defaults(stats=True)
    log_group = P.add_mutually_exclusive_group()
    log_group.add_argument(
        "-L",
        "--log-file",
        metavar="FILE",
        help="Write a full run-log to FILE (plus console). If omitted, auto-creates yt_bulk_cc_YYYYMMDD-HHMMSS.log.",
    )
    log_group.add_argument(
        "--no-log", action="store_true", help="Disable file logging entirely."
    )
    P.add_argument(
        "-F",
        "--formats-help",
        action="store_true",
        help="Show examples of each output format and exit",
    )
    P.add_argument(
        "-p",
        "--proxy",
        metavar="URL[,URL2,…]",
        help="Single proxy URL or comma-separated list to rotate through. Include credentials in the URL if needed, e.g. http://user:pass@host:port.",
    )
    P.add_argument("--proxy-file", help="File containing one proxy URL per line")
    P.add_argument(
        "--public-proxy",
        type=int,
        metavar="N",
        help="(Deprecated) Retained for compat; enabling uses SwiftShadow pool.",
    )
    P.add_argument(
        "--proxy-refresh",
        type=int,
        default=0,
        help="Enable background proxy refresh every N minutes (0=disabled).",
    )
    P.add_argument(
        "--public-proxy-type",
        choices=["http", "https", "socks"],
        default="http",
        help=argparse.SUPPRESS,  # deprecated / internal
    )
    P.add_argument(
        "--public-proxy-country",
        help="Comma-separated list of country codes for public proxies",
    )
    P.add_argument(
        "--convert",
        metavar="FILE",
        help="Convert an existing JSON file to another format and exit",
    )
    P.add_argument("--cookie-json", help="Load cookies from a Netscape or JSON file")
    P.add_argument(
        "--basename", default="captions", help="Base filename for concatenated output"
    )
    P.add_argument(
        "-C",
        "--concat",
        action="store_true",
        help="Concatenate multiple transcripts into a single file",
    )
    P.add_argument(
        "--split",
        metavar="N[u]",
        help="Split concatenated output when N units reached (w=words, l=lines, c=chars)",
    )
    P.add_argument(
        "--check-ip",
        action="store_true",
        help="Exit if the current IP/proxy is blocked",
    )
    P.add_argument("--stats-top", type=int, help="Show statistics for top N files")

    args = P.parse_args()
    if args.formats_help:
        print(
            textwrap.dedent(
                """
        FORMAT EXAMPLES  (default output is **json** - pass "-f srt" etc. to change)
        ---------------------------------------------------------------------------
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
        """
            )
        )
        sys.exit(0)

    if args.convert:
        out_dir = Path(args.folder).expanduser()
        out_dir.mkdir(parents=True, exist_ok=True)
        convert_existing(args.convert, args.format, out_dir, include_stats=args.stats)
        return

    if not args.LINK:
        P.error("LINK is required unless --convert or --formats-help is used")

    split_limit: int | None = None
    split_unit: str | None = None
    if args.split:
        m = re.fullmatch(r"(\d+)\s*([wWcClL])", args.split.strip())
        if not m:
            P.error("--split must be like 10000c / 8000w / 2500l")
        split_limit = int(m.group(1))
        split_unit = m.group(2).lower()
    if args.split and not args.concat:
        P.error("--split only makes sense together with --concat")

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
        _ANSI_RE = re.compile(r"\x1B\[[0-9;]*[A-Za-z]")

        # Only redirect stderr to capture error output, not stdout
        fh = log_file.open("w", encoding="utf-8")
        _orig_err = sys.stderr
        
        class _StderrTee:
            def __init__(self, console_stream, file_stream):
                self._console = console_stream
                self._file = file_stream

            def write(self, data):
                cleaned = data.replace("\r", "")
                self._console.write(data)
                self._file.write(_ANSI_RE.sub("", cleaned))

            def flush(self):
                self._console.flush()
                self._file.flush()

        sys.stderr = _StderrTee(_orig_err, fh)

        def _restore_streams():
            sys.stderr = _orig_err
            fh.close()

        atexit.register(_restore_streams)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        LOG_FMT_FILE = "%(asctime)s - %(levelname)s - %(message)s"
        DATE_FMT = "%Y-%m-%d %H:%M:%S"
        file_handler.setFormatter(logging.Formatter(LOG_FMT_FILE, DATE_FMT))
    else:
        file_handler = None
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
        file_handler.setLevel(logging.DEBUG)
    root_logger_level = logging.DEBUG if file_handler else console_level
    logging.basicConfig(
        level=root_logger_level,
        handlers=[console_handler] + ([file_handler] if file_handler else []),
    )
    # ── SwiftShadow logging integration ─────────────────────────────────────
    swift_log = logging.getLogger("swiftshadow")
    swift_log.setLevel(logging.DEBUG if args.verbose > 1 else logging.INFO)
    # Ensure all SwiftShadow records land in *our* handlers (file + console)
    swift_log.propagate = True
    # Clear any existing handlers to avoid duplicates
    swift_log.handlers.clear()
    # Add our handlers to SwiftShadow logger
    if file_handler:
        swift_log.addHandler(file_handler)
    swift_log.addHandler(console_handler)
    
    # Also ensure site_downloader logs are captured
    site_log = logging.getLogger("site_downloader")
    site_log.setLevel(logging.DEBUG if args.verbose > 1 else logging.INFO)
    site_log.propagate = True
    site_log.handlers.clear()
    if file_handler:
        site_log.addHandler(file_handler)
    site_log.addHandler(console_handler)
    if args.timestamps:
        FMT["text"] = TimeStampedText(show=True)
        FMT["pretty"] = TimeStampedText(show=True)
    from importlib import import_module

    ytb = import_module("yt_bulk_cc")
    kind, ident = ytb.detect(args.LINK)
    out_dir = Path(args.folder).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    videos = list(ytb.video_iter(kind, ident, args.limit, args.sleep))
    if args.limit:
        videos = videos[: args.limit]
    if not videos:
        logging.error("No videos found - is the link correct?")
        sys.exit(1)
    logging.info("Found %s videos", len(videos))
    progress = None
    bar_task = None
    status_display = None
    try:
        from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

        progress = Progress(
            SpinnerColumn(),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=term_console,
        )
        progress.start()
        bar_task = progress.add_task("Preparing", total=len(videos))
        
    except ModuleNotFoundError:  # pragma: no cover - rich optional
        pass
    proxy_pool = None
    proxy_cfg = None  # ensure defined for downstream references
    if args.proxy:
        warnings.warn(
            "--proxy is deprecated; use --public-proxy (SwiftShadow) instead.",
            DeprecationWarning,
            stacklevel=0,
        )
    if args.proxy_file:
        warnings.warn(
            "--proxy-file is deprecated; use --public-proxy instead.",
            DeprecationWarning,
            stacklevel=0,
        )
    if args.public_proxy and ProxyPool:
        if console_level <= logging.INFO:
            print(f"{C.BLU}🔄 Status: Loading proxies...{C.END}")
        
        enable_bg = args.proxy_refresh > 0
        proxy_pool = ProxyPool(
            max_proxies=args.public_proxy,
            cache_minutes=10,
            verbose=args.verbose,
            enable_background_refresh=enable_bg,
            refresh_interval_minutes=args.proxy_refresh if enable_bg else None,
        )
        # Await initial population with timeout to prevent hanging
        try:
            if hasattr(proxy_pool, "ensure_ready"):
                await asyncio.wait_for(proxy_pool.ensure_ready(), timeout=30.0)
            
            # Show proxy info
            if console_level <= logging.INFO and hasattr(proxy_pool, '_proxies'):
                proxy_count = len(getattr(proxy_pool, '_proxies', []))
                print(f"{C.GRN}✅ Status: Ready - {proxy_count} proxies loaded{C.END}")
                if args.verbose >= 1:
                    proxy_list = []
                    for i, proxy in enumerate(getattr(proxy_pool, '_proxies', [])[:5]):  # Show first 5
                        proxy_list.append(f"  - {proxy}")
                    if proxy_count > 5:
                        proxy_list.append(f"  ... and {proxy_count - 5} more")
                    
                    if proxy_list:
                        print(f"{C.YEL}🌐 Proxies used:{C.END}")
                        print("\n".join(proxy_list))
                
        except asyncio.TimeoutError:
            logging.warning("Proxy pool initialization timed out after 30 seconds, continuing without proxies")
            if console_level <= logging.INFO:
                print(f"{C.YEL}⏰ Status: Proxy loading timed out, continuing without proxies{C.END}")
            proxy_pool = None
        except Exception as e:
            logging.warning("Proxy pool initialisation failed, will rely on lazy/fallback: %s", e)
            if console_level <= logging.INFO:
                print(f"{C.RED}❌ Status: Proxy loading failed - %s{C.END}", str(e))
            proxy_pool = None
    elif args.public_proxy and not ProxyPool:
        logging.error("SwiftShadow not available; --public-proxy ignored.")
        if console_level <= logging.INFO:
            print(f"{C.RED}❌ Status: SwiftShadow unavailable{C.END}")
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
        first_vid = videos[0]["videoId"]
        ok_probe, banned_proxies = ytb.probe_video(
            first_vid,
            cookies=cookies_data,
            proxy_pool=proxy_pool,
            proxy_cfg=proxy_cfg,
            banned=set(),
        )
        if not ok_probe:
            msg = "Current IP appears blocked"
            if progress:
                progress.stop()
            print(msg)
            logging.error(msg)
            sys.exit(2)
        if banned_proxies:
            logging.info(
                "Proxies banned during check: %s", ", ".join(sorted(banned_proxies))
            )
    sem = asyncio.Semaphore(args.jobs)
    skipped: list[tuple[str, str, str]] = []
    tasks = []
    for idx, video in enumerate(videos, 1):
        vid = video["videoId"]
        title_runs = video.get("title", {}).get("runs", [])
        title = title_runs[0]["text"] if title_runs else vid
        seq = f"{idx:05d} " if not args.no_seq_prefix else ""
        fname = f"{seq}[{vid}] {slug(title)}.{EXT[args.format]}"
        path = _shorten_for_windows(Path(args.folder).expanduser() / fname)
        if path.exists() and not args.concat:
            logging.info("✿ %s already exists", path.name)
            skipped.append(("ok", vid, title))
            continue
        tasks.append(
            ytb.grab(
                vid,
                title,
                path,
                args.language,
                args.format,
                sem,
                tries=6,
                cookies=cookies_data,
                proxy_pool=proxy_pool,
                proxy_cfg=proxy_cfg,
                banned=banned_proxies,
                include_stats=args.stats and not args.concat,
                delay=args.sleep,
            )
        )
    if progress and bar_task is not None:
        progress.update(
            bar_task, description="Downloading", completed=0, total=len(tasks)
        )
    
    if console_level <= logging.INFO:
        concurrent_info = f"Concurrent Jobs: {args.jobs}"
        if proxy_pool and hasattr(proxy_pool, '_proxies'):
            proxy_count = len(getattr(proxy_pool, '_proxies', []))
            proxy_info = f" | 🌐 Proxies: {proxy_count} loaded"
        elif proxy_pool:
            proxy_info = " | 🌐 Proxies: Active"
        else:
            proxy_info = ""
            
        print(f"{C.BLU}⬇️ Status: Downloading transcripts... | {concurrent_info}{proxy_info}{C.END}")
    if not tasks and not skipped and not pre_results:
        logging.info("Nothing to do (all files already present).")
        if progress:
            progress.stop()
        return
    orig_console_level = console_handler.level
    console_handler.setLevel(logging.ERROR)
    try:
        results = []
        for fut in asyncio.as_completed(tasks):
            results.append(await fut)
            if progress and bar_task is not None:
                progress.update(bar_task, advance=1)
        if progress:
            progress.stop()
    finally:
        console_handler.setLevel(orig_console_level)
        for h in logging.getLogger().handlers:
            if isinstance(h, logging.FileHandler):
                h.flush()
    results = pre_results + results
    results = pre_results + results
    ok = [r for r in results if r[0] == "ok"] + skipped
    none = [r for r in results if r[0] == "none"]
    fail = [r for r in results if r[0] == "fail"]
    proxy_fail = [r for r in results if r[0] == "proxy_fail"]
    if log_file and not ok and not fail and not none and not proxy_fail:
        try:
            log_file.unlink()
        except FileNotFoundError:
            pass

    def _emit_final_summary() -> None:
        total = len(ok) + len(none) + len(fail) + len(proxy_fail)
        
        # Log to file (without emojis) - plain text for log parsing
        if none:
            logging.info(
                "Videos without captions (%d): %s",
                len(none),
                ", ".join(f"https://youtu.be/{vid}" for _, vid, _ in none),
            )
        if fail:
            logging.info(
                "Videos failed (%d): %s",
                len(fail),
                ", ".join(f"https://youtu.be/{vid}" for _, vid, _ in fail),
            )
        if proxy_fail:
            logging.info(
                "Videos failed due to proxy/network (%d): %s",
                len(proxy_fail),
                ", ".join(f"https://youtu.be/{vid}" for _, vid, _ in proxy_fail),
            )
        logging.info(
            "Summary: ok=%d  no_caption=%d  failed=%d  proxy_failed=%d  banned_proxies=%d  total=%d",
            len(ok),
            len(none),
            len(fail),
            len(proxy_fail),
            len(banned_proxies),
            total,
        )
        if banned_proxies:
            logging.info(
                "Banned proxies (%d): %s",
                len(banned_proxies),
                ", ".join(sorted(banned_proxies)),
            )
        
        # Print to console (with emojis) - completely separate from logging
        # Only print if console level allows it
        if console_level <= logging.INFO:
            print()  # Add spacing before summary
            if none:
                print(f"{C.YEL}❌ Videos without captions ({len(none)}): {', '.join(f'https://youtu.be/{vid}' for _, vid, _ in none)}{C.END}")
            if fail:
                print(f"{C.RED}⚠️ Videos failed ({len(fail)}): {', '.join(f'https://youtu.be/{vid}' for _, vid, _ in fail)}{C.END}")
            if proxy_fail:
                print(f"{C.RED}🌐 Videos failed due to proxy/network ({len(proxy_fail)}): {', '.join(f'https://youtu.be/{vid}' for _, vid, _ in proxy_fail)}{C.END}")
            
            # Console summary with emojis - more visually appealing
            print(f"📊 Summary: ✅ {C.GRN}{len(ok)}{C.END}  ❌ no-caption {C.YEL}{len(none)}{C.END}  ⚠️ failed {C.RED}{len(fail)}{C.END}  🌐 proxy-failed {C.RED}{len(proxy_fail)}{C.END}  🚫 banned {C.RED}{len(banned_proxies)}{C.END}  (total {total})")
            
            if banned_proxies:
                print(f"{C.RED}🚫 Banned proxies ({len(banned_proxies)}): {', '.join(sorted(banned_proxies))}{C.END}")
            print()  # Add spacing after summary

    stats_files: list[Path] = []
    _seen_stats: set[Path] = set()
    if args.concat and ok:
        logging.info("Per-file stats are disabled during concatenation")
        base_name = args.basename
        concat_paths = []
        if args.format == "json":
            current_objs: list = []
            meta_list: list[tuple[str, str]] = []
            w_tot = l_tot = c_tot = 0
            file_idx = 1

            def _flush_json():
                nonlocal current_objs, w_tot, l_tot, c_tot, file_idx, meta_list
                fname = f"{base_name}_{file_idx:05d}" if split_limit else base_name
                tgt = out_dir / f"{fname}.json"
                for it in current_objs:
                    while True:
                        txt = json.dumps(it, indent=2, ensure_ascii=False)
                        if not txt.endswith("\n"):
                            txt += "\n"
                        w_i, l_i, c_i = _stats(txt)
                        wanted = {"words": w_i, "lines": l_i, "chars": c_i}
                        if it.get("stats") == wanted:
                            break
                        it["stats"] = wanted
                payload = {"items": current_objs}
                txt = json.dumps(payload, ensure_ascii=False, indent=2)
                if not txt.endswith("\n"):
                    txt += "\n"
                if args.stats:
                    while True:
                        txt = json.dumps(payload, indent=2, ensure_ascii=False)
                        new = _stats(txt)
                        if payload.get("stats") == {
                            "words": new[0],
                            "lines": new[1],
                            "chars": new[2],
                        }:
                            break
                        payload["stats"] = {
                            "words": new[0],
                            "lines": new[1],
                            "chars": new[2],
                        }
                tgt.write_text(txt, encoding="utf-8")
                concat_paths.append(tgt)
                if tgt not in _seen_stats:
                    _seen_stats.add(tgt)
                    stats_files.append(tgt)
                current_objs = []
                w_tot = l_tot = c_tot = 0
                meta_list = []
                file_idx += 1

            for v_idx, v in enumerate(videos, 1):
                vid = v["videoId"]
                for _, v_ok, title in ok:
                    if v_ok == vid:
                        break
                else:
                    continue
                try:
                    pattern = f"*{glob.escape('[' + vid + ']')}*.json"
                    src = next(out_dir.glob(pattern))
                except StopIteration:
                    logging.warning("File for %s not found - prefix off?", vid)
                    continue
                try:
                    obj_txt = src.read_text(encoding="utf-8")
                    obj = json.loads(obj_txt)
                except Exception as e:
                    logging.warning("Skip corrupted JSON %s (%s)", src.name, e)
                    continue
                w_p, l_p, c_p = _stats(obj_txt)
                exceed = split_limit and (
                    (split_unit == "w" and w_tot + w_p > split_limit)
                    or (split_unit == "l" and l_tot + l_p > split_limit)
                    or (split_unit == "c" and c_tot + c_p > split_limit)
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
        else:
            SEP = lambda v, t: f"\n──── {v} ── {t[:50]} ─────────────────────────\n"
            file_idx = 1
            fname = f"{base_name}_{file_idx:05d}" if split_limit else base_name
            tgt = out_dir / f"{fname}.{EXT[args.format]}"
            dst = tgt.open("w", encoding="utf-8")
            concat_paths.append(tgt)
            if tgt not in _seen_stats:
                _seen_stats.add(tgt)
                stats_files.append(tgt)
            w_tot = l_tot = c_tot = 0
            meta_list: list[tuple[str, str]] = []

            def _rollover():
                nonlocal file_idx, dst, w_tot, l_tot, c_tot, tgt, meta_list
                dst.close()
                if args.stats:
                    hdr, _w, _l, _c = _fixup_loop(
                        (w_tot, l_tot, c_tot), args.format, meta_list
                    )
                    _prepend_header(concat_paths[-1], hdr)
                file_idx += 1
                fname = f"{base_name}_{file_idx:05d}"
                tgt = out_dir / f"{fname}.{EXT[args.format]}"
                concat_paths.append(tgt)
                dst = tgt.open("w", encoding="utf-8")
                meta_list = []
                w_tot = l_tot = c_tot = 0

            for v in videos:
                vid = v["videoId"]
                title_runs = v.get("title", {}).get("runs", [])
                title = title_runs[0]["text"] if title_runs else vid
                pattern = f"*{glob.escape('[' + vid + ']')}*.{EXT[args.format]}"
                piece_file = next(out_dir.glob(pattern))
                piece = piece_file.read_text(encoding="utf-8")
                dst.write(SEP(vid, title))
                body_w, body_l, body_c = _stats(piece)
                pred_w, pred_l, pred_c = w_tot + body_w, l_tot + body_l, c_tot + body_c
                exceed = split_limit and (
                    (split_unit == "w" and pred_w > split_limit)
                    or (split_unit == "l" and pred_l > split_limit)
                    or (split_unit == "c" and pred_c > split_limit)
                )
                if exceed and (w_tot or l_tot or c_tot):
                    _rollover()
                    pred_meta = [(vid, title)]
                    if args.stats:
                        _, pred_w, pred_l, pred_c = _fixup_loop(
                            (body_w, body_l, body_c), args.format, pred_meta
                        )
                dst.write(piece)
                meta_list.append((vid, title))
                w_tot += body_w
                l_tot += body_l
                c_tot += body_c
            dst.close()
            if args.stats:
                hdr, w_tot, l_tot, c_tot = _fixup_loop(
                    (w_tot, l_tot, c_tot), args.format, meta_list
                )
                _prepend_header(concat_paths[-1], hdr)
        if log_file:
            logging.info(
                "Concatenated output → %s", ", ".join(p.name for p in concat_paths)
            )
        print(f"\n{C.GRN}✅ Concatenated transcripts saved to:{C.END}")
        for p in concat_paths:
            print(f"   📄 {p}")
        print()
    if not args.concat:
        for _, vid, title in ok:
            try:
                p = next(out_dir.glob(f"*{vid}*.{EXT[args.format]}"))
                if p not in _seen_stats:
                    _seen_stats.add(p)
                    stats_files.append(p)
            except StopIteration:
                continue
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
            header_txt = f"File statistics (top {len(ranked)})"
        print(f"{C.BLU}📄 {header_txt}{C.END}")
        pad = len(str(len(ranked))) or 1
        for idx, p in enumerate(ranked, 1):
            try:
                txt = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            w, l, c = _stats(txt)
            print(
                f"  {idx:0{pad}d}. {p.name} - {C.GRN}{w:,}{C.END} w · {C.GRN}{l:,}{C.END} l · {C.GRN}{c:,}{C.END} c"
            )
        print()
    if log_file and console_level <= logging.INFO:
        print(f"📝 Full log: {C.BLU}{log_file}{C.END}")
    
    try:
        if proxy_pool and hasattr(proxy_pool, "close"):
            proxy_pool.close()
    finally:
        _emit_final_summary()
        for h in logging.getLogger().handlers:
            h.flush()
        logging.shutdown()
    if fail:
        sys.exit(2)


async def main() -> None:
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
    if sys.platform.startswith("linux"):
        try:
            import uvloop

            uvloop.install()
        except ModuleNotFoundError:
            pass
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{C.BLU}Aborted by user{C.END}")
        sys.exit(130)
