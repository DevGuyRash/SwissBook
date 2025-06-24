from __future__ import annotations

import json
import time
import asyncio
from typing import Optional
import urllib.request

# Third-party helpers
from bs4 import BeautifulSoup                   # pip install beautifulsoup4
from playwright.sync_api import Page            # pip install playwright
from readability import Document                # pip install readability-lxml

# --------------------------------------------------------------------------- #
# Dynamic indirection so **either** `site_downloader.browser.new_page`
# **or** `site_downloader.fetcher.new_page` can be monkey-patched in tests.
# --------------------------------------------------------------------------- #
from site_downloader import browser as _browser

def _dynamic_new_page(*args, **kwargs):
    return _browser.new_page(*args, **kwargs)

# Expose the symbol the rest of this module already imports.
new_page = _dynamic_new_page


def _auto_scroll(page: Page, *, max_scrolls: int = 10, pause: float = 0.5) -> None:
    """
    Auto-scroll the page to trigger lazy-loaded content.
    
    This function scrolls to the bottom of the page in increments, waiting between
    each scroll to allow dynamic content to load. It stops when either:
    - The page stops growing in height, or
    - The maximum number of scroll attempts is reached.
    
    Args:
        page: Playwright page object to scroll
        max_scrolls: Maximum number of scroll attempts before giving up
        pause: Seconds to wait between scrolls to allow content to load
    """
    prev = -1
    for _ in range(max_scrolls):
        curr = page.evaluate("document.body.scrollHeight")
        if curr <= prev:
            break
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(pause)
        prev = curr


# Async peer (identical algorithm)
async def _auto_scroll_async(page: "playwright.async_api.Page", *,
                             max_scrolls: int = 10, pause: float = 0.5) -> None:
    prev = -1
    for _ in range(max_scrolls):
        curr = await page.evaluate("document.body.scrollHeight")
        if curr <= prev:
            break
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(pause)
        prev = curr


# Re-export for tests so they can import without touching internal symbol
__all__ = ["fetch_clean_html", "_auto_scroll", "_auto_scroll_async"]


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
    # New parameters
    cookies: Optional[list[dict]] = None,
    ua_browser: Optional[str] = None,
    ua_os: Optional[str] = None,
    extra_css: Optional[list[str]] = None,
    block_assets: bool = False,
    fast_http: bool = False,
    block: Optional[list[str]] = None,
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
    # ------------------------------------------------------------------ #
    # Disable the lightweight path whenever we *must* attach headers/cookies or
    # apply blocking - otherwise tests expecting Playwright hooks won't see
    # their monkey-patches being hit.
    if headers_json or cookies or block:
        fast_http = False

    # Fast path - use pure HTTP when caller *explicitly* requests it.
    # We still respect custom headers but obviously lose JS execution,
    # auto-scroll and CSS injection.
    # ------------------------------------------------------------------ #
    if fast_http:
        req = urllib.request.Request(
            url,
            headers=json.loads(headers_json) if headers_json else {},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="ignore")

    extra = json.loads(headers_json) if headers_json else None
    # Pull a *fresh* reference each call so run-time monkey-patches are seen.
    with new_page(
        engine,
        dark_mode=dark_mode,
        proxy=proxy,
        viewport_width=viewport_width,
        extra_headers=extra,
        block=block,
        ua_browser=ua_browser,
        ua_os=ua_os,
        extra_css=extra_css,
        block_assets=block_assets,
    ) as (_, ctx, page):
        # Unit-tests sometimes inject a stub where ``page`` is ``None``.
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
