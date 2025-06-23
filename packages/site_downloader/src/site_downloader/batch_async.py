"""
Async sibling of `cli.grab` – internal use by cli.batch.
Only 'remote' code‑paths are async‑capable; local‑file flows fall back to
the original sync helpers transparently.
"""
from __future__ import annotations
import pathlib, json
from typing import Optional

from site_downloader.constants import DEFAULT_OUTDIR, VALID_FORMATS
from site_downloader.utils import extract_url, sanitize_url_for_filename
from site_downloader import fetcher, renderer, convert
from site_downloader.browser import anew_page
from site_downloader.proxy import pool as proxy_pool


async def grab_async(
    url: str,
    *,
    fmt: str = "html",
    out: Optional[pathlib.Path] = None,
    proxy: str | None = None,
    proxies: str | None = None,
    proxy_file: pathlib.Path | None = None,
    headers: str | None = None,
    dark_mode: bool = False,
    viewport_width: int = 1280,
    quality: float = 2.0,
    selector: str | None = None,
    no_scroll: bool = False,
    max_scrolls: int = 10,
    ua_browser: str | None = None,
    ua_os: str | None = None,
    cookies_json: str | None = None,
    cookies_file: pathlib.Path | None = None,
    extra_css: list[str] | None = None,
    block: list[str] | None = None,
) -> None:

    fmt = fmt.lower()
    if fmt not in VALID_FORMATS:
        raise ValueError(f"Unknown format: {fmt}")

    if out is None:
        slug = sanitize_url_for_filename(extract_url(url))
        ext = ".pdf" if fmt == "pdf" else f".{fmt}"
        out = pathlib.Path(DEFAULT_OUTDIR) / f"{slug}{ext}"
    out.parent.mkdir(parents=True, exist_ok=True)

    # --- network identity ------------------------------------------------- #
    _proxy_cycle = proxy_pool(proxy, proxies, proxy_file)
    jar = json.loads(cookies_json) if cookies_json else None
    if cookies_file and not jar:
        from site_downloader.session import load_cookie_file
        jar = load_cookie_file(cookies_file)

    headers_json = headers if isinstance(headers, str) else None

    # ------- rendered ------------------------------------------------------ #
    if fmt in {"pdf", "png"}:
        await renderer.render_page_async(        # updated async entry‑point
            url,
            out,
            proxy=next(_proxy_cycle),
            headers_json=headers_json,
            dark_mode=dark_mode,
            viewport_width=viewport_width,
            scale=quality,
            ua_browser=ua_browser,
            ua_os=ua_os,
            cookies=jar,
            extra_css=extra_css,
            block=block,
        )
        return

    # ------- textual ------------------------------------------------------- #
    async with anew_page(
        proxy=next(_proxy_cycle),
        dark_mode=dark_mode,
        viewport_width=viewport_width,
        extra_headers=json.loads(headers_json) if headers_json else None,
        ua_browser=ua_browser,
        ua_os=ua_os,
        cookies=jar,
        extra_css=extra_css,
        block=block,
    ) as (_, _, page):
        await page.goto(url, wait_until="networkidle", timeout=90_000)
        if not no_scroll:
            await fetcher._auto_scroll_async(page, max_scrolls=max_scrolls)
        html_raw = await page.content()

    converted = convert.convert_html(html_raw, fmt)
    if isinstance(converted, bytes):
        out.write_bytes(converted)
    else:
        out.write_text(converted, encoding="utf-8") 