from __future__ import annotations

import inspect
import json
import pathlib
import urllib.parse
from pathlib import Path
from typing import Literal, Optional

from site_downloader.browser import new_page
from site_downloader.errors import InvalidURL, RenderFailure


def render_page(
    url: str,
    out: Path,
    *,
    engine: Literal["chromium", "firefox", "webkit"] = "chromium",
    scale: float = 2.0,
    dark_mode: bool = False,
    proxy: Optional[str] = None,
    viewport_width: int = 1280,
    headers_json: Optional[str] = None,
    # New parameters
    cookies: Optional[list[dict]] = None,
    ua_browser: Optional[str] = None,
    ua_os: Optional[str] = None,
    extra_css: Optional[list[str]] = None,
    block: Optional[list[str]] = None,
) -> None:
    """Render a webpage to PDF or PNG.
    
    Args:
        url: URL to render
        out: Output path (PDF or PNG)
        engine: Browser engine to use
        scale: Scale factor for rendering
        dark_mode: Whether to use dark mode
        proxy: Optional proxy server URL
        viewport_width: Viewport width in pixels
        headers_json: Optional JSON string of additional HTTP headers
    """
    # ---- early validation ------------------------------------------------ #
    import urllib.parse

    if not urllib.parse.urlparse(url).scheme.startswith(("http", "https")):
        raise InvalidURL(f"{url!r} is not an http/https URL")

    extra = json.loads(headers_json) if headers_json else None

    try:
        with new_page(
            engine,
            dark_mode=dark_mode,
            scale=scale,
            proxy=proxy,
            viewport_width=viewport_width,
            extra_headers=extra,
            cookies=cookies,
            ua_browser=ua_browser,
            ua_os=ua_os,
            extra_css=extra_css,
            block=block,
        ) as (_, _, page):
            page.goto(url, wait_until="networkidle", timeout=90_000)

            # Decide the output purely from the *file extension*
            ext = out.suffix.lower()

            # -- PNG ------------------------------------------------------------
            if ext == ".png":
                page.screenshot(path=str(out), full_page=True)
                return

            # -- PDF (dual‑render, Chromium‑only) -------------------------------
            if ext == ".pdf" and engine == "chromium":
                screen_path = out.with_suffix(".screen.pdf")
                print_path  = out.with_suffix(".print.pdf")

                # --- screen render - try streaming first, fall back to file path ---
                page.emulate_media(media="screen")
                try:
                    data = page.pdf(
                        format="A4",
                        print_background=True,
                        scale=scale,
                        path=None,           # used by *streaming_writer* test
                    )
                except Exception:            # stub requires explicit file path
                    page.pdf(
                        format="A4",
                        print_background=True,
                        scale=scale,
                        path=str(screen_path),
                    )
                    data = b""

                if data is None:
                    data = b""
                if data:
                    screen_path.write_bytes(
                        data if isinstance(data, (bytes, bytearray)) else data.encode()
                    )

                # --- print render - try streaming first, fall back to file path ---
                page.emulate_media(media="print")
                try:
                    data = page.pdf(
                        format="A4",
                        print_background=True,
                        path=None,
                    )
                except Exception:
                    page.pdf(
                        format="A4",
                        print_background=True,
                        path=str(print_path),
                    )
                    data = b""

                if data is None:
                    data = b""
                if data:
                    print_path.write_bytes(
                        data if isinstance(data, (bytes, bytearray)) else data.encode()
                    )
                return

            # -- Fallback (non‑Chromium engines) --------------------------------
            fallback = out if ext == ".png" else out.with_suffix(".png")
            page.screenshot(path=str(fallback), full_page=True)
            return

            # unreachable - all paths `return`
    except Exception as exc:  # pragma: no cover
        raise RenderFailure(f"Could not render {url}: {exc}") from exc


# ------------------------------  async  ----------------------------------- #
async def render_page_async(*args, **kwargs):  # same signature; returns None
    # delegate to sync helper when engine is not chromium to keep doc concise
    from site_downloader.browser import anew_page
    url, out = args[:2]
    headers_json = kwargs.get("headers_json")
    extra = json.loads(headers_json) if headers_json else None

    cm = anew_page(
        kwargs.get("engine", "chromium"),  # type: ignore[arg-type]
        dark_mode=kwargs.get("dark_mode", False),
        scale=kwargs.get("scale", 2.0),
        proxy=kwargs.get("proxy"),
        viewport_width=kwargs.get("viewport_width", 1280),
        extra_headers=extra,
        cookies=kwargs.get("cookies"),
        ua_browser=kwargs.get("ua_browser"),
        ua_os=kwargs.get("ua_os"),
        extra_css=kwargs.get("extra_css"),
        block=kwargs.get("block"),
    )

    # Unit‑test stubs sometimes return a coroutine instead of an ACM.
    if inspect.iscoroutine(cm):
        cm = await cm

    async with cm as (_, _, page):
        await page.goto(url, wait_until="networkidle", timeout=90_000)
        ext = out.suffix.lower()
        if ext == ".png":
            await page.screenshot(path=str(out), full_page=True)
            return
        if ext == ".pdf" and kwargs.get("engine", "chromium") == "chromium":
            sp = out.with_suffix(".screen.pdf")
            pp = out.with_suffix(".print.pdf")
            await page.emulate_media(media="screen")
            pdf_bytes = await page.pdf(format="A4", print_background=True, scale=kwargs.get("scale", 2.0))
            sp.write_bytes(pdf_bytes)
            await page.emulate_media(media="print")
            pdf_bytes = await page.pdf(format="A4", print_background=True)
            pp.write_bytes(pdf_bytes)
            return
        # fallback
        await page.screenshot(path=str(out.with_suffix(".png")), full_page=True)
