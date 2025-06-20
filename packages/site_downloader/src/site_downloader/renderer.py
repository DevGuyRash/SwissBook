from __future__ import annotations

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
        ) as (_, _, page):
            page.goto(url, wait_until="networkidle", timeout=90_000)

        # Decide the output purely from the *file extension* so users can ask
        # for PNG even when they keep the default `chromium` engine.
        ext = out.suffix.lower()

        # -- PNG ----------------------------------------------------------------
        if ext == ".png":
            page.screenshot(path=str(out), full_page=True)
            return

        # -- PDF (dual‑render, Chromium‑only) -----------------------------------
        if ext == ".pdf" and engine == "chromium":
            screen_path = out.with_suffix(".screen.pdf")
            print_path = out.with_suffix(".print.pdf")

            page.emulate_media(media="screen")
            page.pdf(
                path=str(screen_path),
                format="A4",
                print_background=True,
                scale=scale,
            )

            page.emulate_media(media="print")
            page.pdf(
                path=str(print_path),
                format="A4",
                print_background=True,
            )
            return

        # -- Fallback (non‑Chromium engines don't support page.pdf) -------------
        fallback = out if ext == ".png" else out.with_suffix(".png")
        page.screenshot(path=str(fallback), full_page=True)
    except Exception as exc:  # pragma: no cover
        raise RenderFailure(f"Could not render {url}: {exc}") from exc
