"""Playwright bootstrap utilities."""

from __future__ import annotations

import contextlib
import json
import pathlib
import random
from typing import Dict, Tuple

from playwright.sync_api import Browser, BrowserContext, sync_playwright
from user_agents import parse as ua_parse  # pip install pyyaml ua-parser user-agents

from site_downloader.constants import USER_AGENTS_POOL, DEFAULT_VIEWPORT, DEFAULT_SCALE
from site_downloader.logger import log
from site_downloader.utils import sec_ch_headers


ASSETS_DIR = pathlib.Path(__file__).parent / "assets"
ANNOY_CSS = (ASSETS_DIR / "annoyances.css").read_text(encoding="utf-8")


def _pick_ua() -> str:
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
    extra_headers: dict[str, str] | None = None,
) -> Tuple[Browser, BrowserContext, "playwright.sync_api.Page"]:
    """Context-manager yielding *(browser, context, page)* with sensible defaults."""
    pw = sync_playwright().start()
    launcher = {"chromium": pw.chromium, "firefox": pw.firefox, "webkit": pw.webkit}[
        engine
    ]
    browser: Browser = launcher.launch(
        headless=True, proxy={"server": proxy} if proxy else None
    )

    ua_str = _pick_ua()
    hdrs = build_headers(ua_str)
    if extra_headers:
        hdrs.update(extra_headers)
        
    context: BrowserContext = browser.new_context(
        viewport={"width": viewport_width, "height": 720},
        user_agent=ua_str,
        device_scale_factor=scale,
        color_scheme="dark" if dark_mode else "light",
        extra_http_headers=hdrs,
    )
    page = context.new_page()
    # Inject annoyance-blocking CSS as soon as any doc starts
    page.add_init_script(f"""(() => {{
        const style = document.createElement('style');
        style.textContent = `{ANNOY_CSS}`;
        document.head.appendChild(style);
    }})();""")

    try:
        yield browser, context, page
    finally:
        log.debug("Closing Playwright browser")
        browser.close()
        pw.stop()
