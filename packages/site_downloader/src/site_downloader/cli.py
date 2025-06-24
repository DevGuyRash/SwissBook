"""
CLI entry-point.  Run ``sdl --help``.
"""

from __future__ import annotations

import json
import pathlib
import sys
import shutil
import asyncio

# --------------------------------------------------------------------------- #
#  Async helper used by the internal ``_batch`` worker – imported lazily so   #
#  it is available both to the library *and* to tests that monkey-patch it.   #
# --------------------------------------------------------------------------- #
from site_downloader.batch_async import grab_async  # noqa: E402  (late import)
from typing import Any, Optional, List

import typer
from typer.models import OptionInfo, ArgumentInfo
from typer import colors, secho, Exit, Argument as Arg, Option as Opt

from site_downloader import __version__
from site_downloader.utils import extract_url, sanitize_url_for_filename
from site_downloader.constants import (
    VALID_FORMATS,
    DEFAULT_OUTDIR,
    DEFAULT_VIEWPORT,
    DEFAULT_SCALE,
    LIST_FILE_SUFFIXES,
)

app = typer.Typer(add_completion=False, help="Site Downloader CLI", no_args_is_help=True)

# --------------------------------------------------------------------------- #
# Helper - unwrap Typer's sentinel objects when functions are invoked
# **directly** from Python (e.g. unit-tests) instead of through the CLI
# parser.  After this, business-logic never has to special-case them again.
# --------------------------------------------------------------------------- #
def _unwrap(value: Any) -> Any:                       # pragma: no cover
    if isinstance(value, (OptionInfo, ArgumentInfo)):
        return value.default
    return value


# --------------------------------------------------------------------------- #
# "grab" - single front-door (full parity with legacy Bash/JS tools)
# --------------------------------------------------------------------------- #
@app.command()
def grab(
    url: str = Arg(..., help="URL *or* local file"),
    fmt: str = Opt("html", "--format", "-f", help="/".join(sorted(VALID_FORMATS))),
    out: pathlib.Path = Opt(None, "--out", "-o", help="Output path"),
    # browser / network
    engine: str = Opt("chromium", "--engine", "-e", help="chromium | firefox | webkit"),
    proxy: Optional[str] = Opt(None, "--proxy", help="HTTP proxy, e.g. http://host:3128"),
    proxies: Optional[str] = Opt(None, "--proxies", help="Comma-separated proxy list"),
    proxy_file: Optional[pathlib.Path] = Opt(
        None, "--proxy-file", help="File containing proxies (1/line)"
    ),
    headers: Optional[str] = Opt(None, "--headers", help="Extra HTTP headers as JSON string"),
    dark_mode: bool = Opt(False, "--dark-mode", help="prefers-color-scheme: dark"),
    # --- NEW - UA filters -------------------------------------------------- #
    ua_browser: Optional[str] = Opt(
        None, "--ua-browser", help="Prefer UA from this browser family"
    ),
    ua_os: Optional[str] = Opt(None, "--ua-os", help="windows/linux/macos/android/ios"),
    # --- NEW - cookies / login -------------------------------------------- #
    cookies_json: Optional[str] = Opt(None, "--cookies-json", help="Cookies JSON str"),
    cookies_file: Optional[pathlib.Path] = Opt(None, "--cookies-file", help="cookies.json"),
    login: Optional[str] = Opt(None, "--login", help="Interactively log in at URL"),
    # --- NEW - extra CSS --------------------------------------------------- #
    extra_css: Optional[str] = Opt(
        None,
        "--extra-css",
        help="Comma-separated list of additional CSS files injected on load",
    ),
    block: Optional[str] = Opt(
        None,
        "--block",
        "-b",
        help="Comma-separated resource types to abort: img,video,audio,media",
    ),
    viewport_width: int = Opt(
        DEFAULT_VIEWPORT, "--viewport-width", help="Viewport width px"
    ),
    quality: float = Opt(DEFAULT_SCALE, "--quality", "-q", help="device-scale-factor"),
    # Optional: treat *this* command as batch when url looks like file-of-URLs
    jobs: int = Opt(
        4,
        "--jobs",
        "-j",
        hidden=True,
        help="Concurrency when url points to a list-file.",
    ),
    # extraction tweaks
    selector: Optional[str] = Opt(None, "--selector", help="CSS selector for main article"),
    no_scroll: bool = Opt(False, "--no-scroll", help="Disable lazy-load auto-scroll"),
    max_scrolls: int = Opt(10, "--max-scrolls", help="Auto-scroll iterations"),
    # perf
    fast_http: bool = Opt(
        False,
        "--fast-http/--no-fast-http",
        help="Fetch HTML via vanilla HTTP instead of Playwright when possible",
    ),
) -> None:
    """
    Unified command - determines workflow solely by **--format**.

    • html / md / txt / docx / epub → article extraction & conversion  
    • pdf / png                     → full-page capture (screen + print for PDF)  
    Works for remote URLs *and* local HTML/Markdown files.
    """
    # ---- Normalise parameters when we're NOT running through Typer -------- #
    fmt = _unwrap(fmt)

    # Typer passes an ``OptionInfo`` sentinel when the caller doesn't specify
    # ``--out``.  Convert it to *None* first, then build a real ``Path`` only
    # when we actually have a string / Path-like value.
    _out_raw = _unwrap(out)          # None when OptionInfo or explicit None
    out = pathlib.Path(_out_raw) if _out_raw is not None else None

    engine         = _unwrap(engine)
    proxy          = _unwrap(proxy)
    proxies        = _unwrap(proxies)
    _proxy_file    = _unwrap(proxy_file)
    proxy_file     = pathlib.Path(_proxy_file) if _proxy_file is not None else None
    headers        = _unwrap(headers)
    dark_mode      = bool(_unwrap(dark_mode))
    viewport_width = int(_unwrap(viewport_width))
    quality        = float(_unwrap(quality))
    selector       = _unwrap(selector)
    no_scroll      = bool(_unwrap(no_scroll))
    max_scrolls    = int(_unwrap(max_scrolls))
    ua_browser     = _unwrap(ua_browser)
    ua_os          = _unwrap(ua_os)
    cookies_json   = _unwrap(cookies_json)
    _cookies_file  = _unwrap(cookies_file)
    cookies_file   = pathlib.Path(_cookies_file) if _cookies_file is not None else None
    login          = _unwrap(login)
    _raw_block     = _unwrap(block)
    block          = [t.strip().lower() for t in _raw_block.split(",")] if _raw_block else None

    # ── handle OptionInfo sentinel correctly ──────────────────────────────
    _raw_css       = _unwrap(extra_css)          # None | str
    extra_css      = (
        [p.strip() for p in _raw_css.split(",") if p.strip()]
        if _raw_css
        else None
    )
    
    # ---------- proxy pool initialisation -------------------------------- #
    from site_downloader.proxy import pool as proxy_pool

    _proxy_cycle = proxy_pool(proxy, proxies, proxy_file)

    # ---------- cookie handling ------------------------------------------ #
    from site_downloader import session as _sess

    jar: list[dict] | None = None
    if login:
        jar = _sess.interactive_login(login, pathlib.Path("cookies.json"))
    elif cookies_json:
        jar = json.loads(cookies_json)
    elif cookies_file:
        jar = _sess.load_cookie_file(cookies_file)

    # Ensure headers reach the fetcher even when grab() is called directly
    headers_json = headers if isinstance(headers, str) else None

    fmt = fmt.lower()
    if fmt not in VALID_FORMATS:
        secho(f"❌  Unknown format: {fmt}", fg=colors.RED, err=True)
        raise Exit(1)

    default_ext = ".pdf" if fmt == "pdf" else f".{fmt}"
    if out is None:
        slug = sanitize_url_for_filename(extract_url(url))
        out = pathlib.Path(DEFAULT_OUTDIR) / f"{slug}{default_ext}"
    out.parent.mkdir(parents=True, exist_ok=True)

    local_src = pathlib.Path(url)
    is_local = local_src.exists()

    # --------------------------------------------------------------------- #
    #  ⬇  auto-detect "file of URLs"  ➜  dispatch to batch() immediately
    # --------------------------------------------------------------------- #
    if is_local and local_src.suffix.lower() in LIST_FILE_SUFFIXES:
        from site_downloader.cli import batch as _batch_cmd

        # call directly to avoid a sub-process
        _batch_cmd(local_src, fmt=fmt, jobs=jobs)
        return


    # ----- rendered formats --------------------------------------------------
    if fmt in {"pdf", "png"} and not is_local:
        from site_downloader.renderer import render_page
        render_page(
            url,
            out,
            engine=engine,
            scale=quality,
            dark_mode=dark_mode,
            proxy=next(_proxy_cycle),
            viewport_width=viewport_width,
            headers_json=headers,
            cookies=jar,
            ua_browser=ua_browser,
            ua_os=ua_os,
            extra_css=extra_css,
            block=block,
        )
        typer.echo(f"✅  Saved {out}")
        return

    # ----- textual formats ---------------------------------------------------
    from site_downloader.convert import convert_html
    if is_local:
        html_raw = local_src.read_text(encoding="utf-8")
    else:
        from site_downloader.fetcher import fetch_clean_html
        html_raw = fetch_clean_html(
            url,
            selector=selector,
            engine=engine,
            auto_scroll=not no_scroll,
            max_scrolls=max_scrolls,
            proxy=next(_proxy_cycle),
            headers_json=headers_json,  # Use the processed headers_json
            dark_mode=dark_mode,
            cookies=jar,
            ua_browser=ua_browser,
            ua_os=ua_os,
            extra_css=extra_css,
            viewport_width=viewport_width,
            block=block,
            fast_http=fast_http,
        )

    converted = convert_html(html_raw, fmt)  # may be bytes
    if isinstance(converted, bytes):
        out.write_bytes(converted)
    else:
        out.write_text(converted, encoding="utf-8")
    typer.echo(f"✅  Saved {out}")


# --------------------------------------------------------------------------- #
# Legacy commands - keep for back-compat but hide from `--help`
# --------------------------------------------------------------------------- #
@app.callback()
def _version(
    version: Optional[bool] = Opt(
        None,
        "--version",
        callback=lambda value: (typer.echo(__version__) or sys.exit(0) if value else None),
        is_eager=True,
        help="Print version and exit.",
    ),
) -> None:
    """Legacy --version handler."""


@app.command(hidden=True)
def fetch(
    url: str = Arg(..., help="URL to fetch"),
    out: pathlib.Path = Opt(None, "--out", "-o", help="Output file (.html/.md/.txt)"),
    fmt: str = Opt("html", "--format", "-f", help="html | md | txt"),
    selector: Optional[str] = Opt(None, "--selector", help="CSS selector for main article"),
) -> None:
    """Legacy alias for `grab` with text formats."""
    grab(url=url, out=out, fmt=fmt, selector=selector, no_scroll=True)


@app.command(hidden=True)
def render(
    url: str = Arg(..., help="URL to capture"),
    out: pathlib.Path = Opt(None, "--out", "-o", help="Output .pdf/.png"),
    engine: str = Opt("chromium", "--engine", "-e", help="chromium | firefox | webkit"),
    quality: float = Opt(2.0, "--quality", "-q", help="Device scale factor"),
) -> None:
    """Legacy alias for `grab` with PDF/PNG formats."""
    fmt = "pdf"
    if out and out.suffix and out.suffix[1:].lower() == "png":
        fmt = "png"
    grab(url=url, out=out, fmt=fmt, engine=engine, quality=quality)


@app.command(hidden=True, name="batch")
def batch(
    file: pathlib.Path = Arg(..., help="Text file of URLs"),
    fmt: str = Opt("pdf", "--format", "-f", help="Output format"),
    jobs: int = Opt(4, "--jobs", "-j", help="Concurrency"),
    # Forward proxy options
    engine: str = Opt("chromium", "--engine", "-e", help="chromium | firefox | webkit"),
    proxy: Optional[str] = Opt(None, "--proxy", help="HTTP proxy, e.g. http://host:3128"),
    proxies: Optional[str] = Opt(None, "--proxies", help="Comma-separated proxy list"),
    proxy_file: Optional[pathlib.Path] = Opt(
        None, "--proxy-file", help="File containing proxies (1/line)"
    ),
    headers: Optional[str] = Opt(None, "--headers", help="Extra HTTP headers as JSON string"),
    dark_mode: bool = Opt(False, "--dark-mode", help="prefers-color-scheme: dark"),
    viewport_width: int = Opt(
        DEFAULT_VIEWPORT, "--viewport-width", help="Viewport width px"
    ),
    quality: float = Opt(DEFAULT_SCALE, "--quality", "-q", help="device-scale-factor"),
    # Forward other options
    ua_browser: Optional[str] = Opt(None, "--ua-browser", help="Prefer UA from this browser family"),
    ua_os: Optional[str] = Opt(None, "--ua-os", help="windows/linux/macos/android/ios"),
    cookies_json: Optional[str] = Opt(None, "--cookies-json", help="Cookies JSON str"),
    cookies_file: Optional[pathlib.Path] = Opt(None, "--cookies-file", help="cookies.json"),
    extra_css: Optional[str] = Opt(
        None,
        "--extra-css",
        help="Comma-separated list of additional CSS files injected on load",
    ),
    block: Optional[str] = Opt(
        None,
        "--block",
        "-b",
        help="Comma‑separated resource types to abort: img,video,audio,media",
    ),
) -> None:
    """Process many URLs in **parallel** using the **grab** logic."""
    # Allow the function to be called directly (unit-tests) *or* via the CLI.
    file = pathlib.Path(file)
    if not file.exists():
        secho(f"❌  Input list not found: {file}", fg=colors.RED, err=True)
        raise typer.Exit(code=1)

    urls = [line.strip() for line in file.read_text().splitlines() if line.strip()]
    outdir = pathlib.Path("out")
    outdir.mkdir(exist_ok=True)

    # ------------------------------------------------------------------ #
    #  Run the batch in a *private* loop **without** replacing the       #
    #  currently‑running one (so pytest‑asyncio stays happy).            #
    # ------------------------------------------------------------------ #
    def _runner() -> None:
        async def _inner() -> None:
            sem = asyncio.Semaphore(jobs)

            async def sem_worker(url_: str) -> None:
                async with sem:
                    # Keep the tests that patch ``asyncio.to_thread`` happy
                    def _call() -> None:
                        # unwrap Typer sentinels
                        def _plain(v):
                            return v.default if isinstance(v, OptionInfo) else v

                        from site_downloader.proxy import pool as proxy_pool
                        _proxy_cycle = proxy_pool(_plain(proxy), _plain(proxies), _plain(proxy_file))

                        from site_downloader import session as _sess
                        jar: list[dict] | None = None
                        if _plain(cookies_json):
                            jar = json.loads(_plain(cookies_json))
                        elif _plain(cookies_file):
                            jar = _sess.load_cookie_file(_plain(cookies_file))

                        _raw_block = _plain(block)
                        _block_list = [t.strip().lower() for t in _raw_block.split(",")] if _raw_block else None

                        _raw_css       = _plain(extra_css)
                        _extra_css_list = (
                            [p.strip() for p in _raw_css.split(",") if p.strip()]
                            if _raw_css
                            else None
                        )

                        _headers_json = _plain(headers)

                        # run the asynchronous grab helper in this thread
                        asyncio.run(
                            grab_async(
                                url_,
                                fmt=_plain(fmt),
                                engine=_plain(engine),
                                proxy=next(_proxy_cycle),
                                headers=_headers_json,
                                dark_mode=_plain(dark_mode),
                                viewport_width=_plain(viewport_width),
                                quality=_plain(quality),
                                ua_browser=_plain(ua_browser),
                                ua_os=_plain(ua_os),
                                cookies_json=_plain(cookies_json),
                                cookies_file=_plain(cookies_file),
                                extra_css=_extra_css_list,
                                block=_block_list,
                            )
                        )

                    await asyncio.to_thread(_call)

            await asyncio.gather(*(sem_worker(u) for u in urls))

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_inner())
        finally:
            loop.close()

    _runner()
    typer.echo("🎉  Batch complete.")


# --------------------------------------------------------------------------- #
# Compatibility: some callers (and one unit-test) expect `batch.callback`.
# --------------------------------------------------------------------------- # keep the legacy alias so static analysers don't complain in tests
batch.callback = batch  # type: ignore[attr-defined]
