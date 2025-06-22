"""Playwright bootstrap utilities."""

from __future__ import annotations

import contextlib
import pathlib
import random
from typing import Dict, List, Optional, Tuple

from playwright.sync_api import Browser, BrowserContext, sync_playwright
from fake_useragent import UserAgent                     # 🆕  UA rotation
from fake_headers import Headers                         # builds realistic header sets

from site_downloader.constants import (
    USER_AGENTS_POOL,
    DEFAULT_VIEWPORT,
    DEFAULT_SCALE,
    DEFAULT_ANNOY_CSS,
)
from site_downloader.logger import log
from site_downloader.utils import sec_ch_headers


ASSETS_DIR = pathlib.Path(__file__).parent / "assets"
# default stylesheet is always injected
_DEFAULT_ANNOY = (ASSETS_DIR / DEFAULT_ANNOY_CSS).read_text(encoding="utf-8")


def _pick_ua(browser: str | None = None, os: str | None = None) -> str:
    """Return a random modern UA via fake‑useragent; fall back to static list."""
    try:
        ua_src = UserAgent(browsers=[browser] if browser else None,
                         os=[os] if os else None)
        return ua_src.random
    except Exception as exc:  # network/cache failure
        log.warning("fake-useragent failed (%s) - using fallback UA", exc)
        return random.choice(USER_AGENTS_POOL)


def build_headers(ua: str) -> Dict[str, str]:
    """Return merged default + Sec-CH headers for *ua*."""
    base = {
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "DNT": "1",
        "Sec-GPC": "1",
    }
    base.update(sec_ch_headers(ua))
    return base


# NB: every kwarg has a 1-to-1 exposure at the CLI
@contextlib.contextmanager
def new_page(
    engine: str = "chromium",
    *,
    proxy: str | None = None,
    dark_mode: bool = False,
    viewport_width: int = DEFAULT_VIEWPORT,
    scale: float = DEFAULT_SCALE,
    # new knobs
    extra_headers: dict[str, str] | None = None,
    cookies: Optional[list[dict]] = None,
    ua_browser: Optional[str] = None,
    ua_os: Optional[str] = None,
    extra_css: Optional[List[str]] = None,
) -> Tuple[Browser, BrowserContext, "playwright.sync_api.Page"]:
    """Context-manager yielding *(browser, context, page)* with sensible defaults."""
    pw = sync_playwright().start()
    launcher = {"chromium": pw.chromium, "firefox": pw.firefox, "webkit": pw.webkit}[
        engine
    ]
    browser: Browser = launcher.launch(
        headless=True, proxy={"server": proxy} if proxy else None
    )

    ua_str = _pick_ua(ua_browser, ua_os)
    # Merge fake-headers (accept-lang etc.) for plausibility
    hdrs = Headers(
        browser=ua_browser or "chrome",
        os=ua_os or "win",
        headers=True,
    ).generate()
    hdrs.update(build_headers(ua_str))
    if extra_headers:
        hdrs.update(extra_headers)
        
    context: BrowserContext = browser.new_context(
        viewport={"width": viewport_width, "height": 720},
        user_agent=ua_str,
        device_scale_factor=scale,
        color_scheme="dark" if dark_mode else "light",
        extra_http_headers=hdrs,
    )
    
    if cookies:
        context.add_cookies(cookies)  # Playwright native API
        
    page = context.new_page()
    
    def _inject(css_text: str):
        page.add_init_script(
            f"""(() => {{
                const style = document.createElement('style');
                style.textContent = `{css_text}`;
                document.head.appendChild(style);
            }})();"""
        )

    _inject(_DEFAULT_ANNOY)
    for css_path in extra_css or []:
        _inject(pathlib.Path(css_path).read_text(encoding="utf-8"))

    try:
        yield browser, context, page
    finally:
        log.debug("Closing Playwright browser")
        browser.close()
        pw.stop()
