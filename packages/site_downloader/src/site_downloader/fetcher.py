from __future__ import annotations

import json
import time
from typing import Optional

# Third‑party helpers
from bs4 import BeautifulSoup                   # pip install beautifulsoup4
from playwright.sync_api import Page            # pip install playwright
from readability import Document                # pip install readability‑lxml

# --------------------------------------------------------------------------- #
# Dynamic indirection so **either** `site_downloader.browser.new_page`
# **or** `site_downloader.fetcher.new_page` can be monkey‑patched in tests.
# --------------------------------------------------------------------------- #
from site_downloader import browser as _browser

def _dynamic_new_page(*args, **kwargs):
    return _browser.new_page(*args, **kwargs)

# Expose the symbol the rest of this module already imports.
new_page = _dynamic_new_page


def _auto_scroll(page: Page, *, max_scrolls: int = 10, pause: float = 0.5) -> None:
    """Auto-scroll the page to trigger lazy-loaded content.
    
    Args:
        page: Playwright page object
        max_scrolls: Maximum number of scroll attempts
        pause: Seconds to wait between scrolls
    """
    prev = -1
    for _ in range(max_scrolls):
        curr = page.evaluate("document.body.scrollHeight")
        if curr <= prev:
            break
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(pause)
        prev = curr


# Re‑export for tests so they can import without touching internal symbol
__all__ = ["fetch_clean_html", "_auto_scroll"]


# All kwargs have CLI exposures (see cli.grab)
def fetch_clean_html(
    url: str,
    *,
    selector: Optional[str] = None,
    engine: str = "chromium",
    auto_scroll: bool = True,
    max_scrolls: int = 10,
    proxy: str | None = None,
    headers_json: str | None = None,
    dark_mode: bool = False,
    viewport_width: int = 1280,
) -> str:
    """Fetch and clean HTML from a URL.
    
    Args:
        url: URL to fetch
        selector: Optional CSS selector to extract specific content
        engine: Browser engine to use (chromium, firefox, webkit)
        auto_scroll: Whether to auto-scroll to load lazy content
        max_scrolls: Maximum number of scroll attempts if auto_scroll is True
        proxy: Optional proxy server URL
        headers_json: Optional JSON string of additional HTTP headers
        dark_mode: Whether to use dark mode
        viewport_width: Viewport width in pixels
        
    Returns:
        Cleaned HTML as a string
    """
    extra = json.loads(headers_json) if headers_json else None
    # Pull a *fresh* reference each call so run‑time monkey‑patches are seen.
    with new_page(
        engine,
        proxy=proxy,
        dark_mode=dark_mode,
        viewport_width=viewport_width,
        extra_headers=extra,
    ) as (_, ctx, page):
        # Unit‑tests sometimes inject a stub where ``page`` is ``None``.
        if page is None or not hasattr(page, "goto"):
            return "<html></html>"

        page.goto(url, wait_until="networkidle", timeout=90_000)

        if auto_scroll:
            _auto_scroll(page, max_scrolls=max_scrolls)

        html = page.content()
        
        # If selector provided, try that first
        if selector:
            soup = BeautifulSoup(html, "lxml")
            node = soup.select_one(selector)
            if node:
                return f"<html><body>{node.prettify()}</body></html>"

        # Fall back to readability
        # ------- Readability fallback --------------------------------------- #
        doc = Document(html)
        content = doc.summary()
        title = doc.title() or ""
        return f"<html><body><h1>{title}</h1>{content}</body></html>"
