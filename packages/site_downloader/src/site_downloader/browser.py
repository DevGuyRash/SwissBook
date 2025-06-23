"""Playwright bootstrap utilities."""

from __future__ import annotations

import atexit
import contextlib
import pathlib
import random
import threading
import asyncio
from typing import Dict, List, Optional, Tuple, Iterable

from playwright.sync_api import Browser, BrowserContext, sync_playwright, Route
from playwright.async_api import async_playwright, Browser as ABrowser
from playwright.async_api import BrowserContext as ABrowserContext
from playwright.async_api import Page as APage
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


# --------------------------------------------------------------------------- #
# CSS & browser pools
# --------------------------------------------------------------------------- #
_CSS_CACHE: dict[str, str] = {}
_PW = None                                        # started once, stopped at exit
_BROWSERS:  dict[tuple[str, str | None], Browser]        = {}   # (engine, proxy)
_CONTEXTS: dict[tuple, BrowserContext]                    = {}   # full ctx key
_ACONTEXTS: dict[tuple, ABrowserContext] = {}   # Async pool mirrors the sync one
_LOCK = threading.Lock()

ASSETS_DIR = pathlib.Path(__file__).parent / "assets"
# ---------------------------------------------------------------------------- #
# CSS *read‑cache* – saves repeated disk IO when grab/batch injects the same
# stylesheet hundreds of times.
# ---------------------------------------------------------------------------- #
_DEFAULT_ANNOY = (ASSETS_DIR / DEFAULT_ANNOY_CSS).read_text(encoding="utf-8")
# remembers which *file* has already been injected into a page (to avoid
# duplicate reads when many pages ask for the same style)
_INJECTED: set[str] = set()

# graceful shutdown when Python process ends (pytest, cli, …)
def _cleanup() -> None:        # pragma: no cover
    global _PW
    for br in _BROWSERS.values():
        try:
            br.close()
        except Exception:       # noqa: BLE001
            pass
    if _PW is not None:
        try:
            _PW.stop()
        except Exception: # noqa: BLE001
            pass
    _PW = None

atexit.register(_cleanup)


def _pick_ua(browser: str | None = None, os: str | None = None) -> str:
    """Return a random modern UA via fake-useragent; fall back to static list."""
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


# ---------------------------  asset‑blocking ------------------------------- #
# Re‑usable predicate so both sync & async APIs share the logic
_BLOCK_MAP = {
    "img": {"image"},
    "images": {"image"},
    "audio": {"media"},
    "video": {"media"},
    "media": {"media"},
}

def _should_block(block: Iterable[str], resource_type: str) -> bool:
    to_block: set[str] = set()
    for key in block:
        to_block |= _BLOCK_MAP.get(key, {key})
    return resource_type in to_block


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
    # performance knobs
    block: Optional[List[str]] = None,
    block_assets: bool = False,               # ← legacy alias
) -> Tuple[Browser, BrowserContext, "playwright.sync_api.Page"]:
    """
    Context-manager yielding *(browser, context, page)* with sensible defaults.

    A persistent Playwright instance and **one browser per
    (engine, proxy)** tuple are cached for the lifetime of the process.
    Every call opens a *fresh* context so pages remain sandboxed.
    """
    global _PW
    with _LOCK:
        if _PW is None:
            _PW = sync_playwright().start()

        key = (engine, proxy)
        if key not in _BROWSERS:
            launcher = getattr(_PW, engine)    # lazy – stub‑friendly
            _BROWSERS[key] = launcher.launch(
                headless=True,
                proxy={"server": proxy} if proxy else None,
            )
    browser = _BROWSERS[key]

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
        
    # ------------------------------------------------------------------ #
    # (2)  Context pool  ➜  one ctx per unique identity
    # ------------------------------------------------------------------ #
    ctx_key = (
        engine,
        proxy,
        dark_mode,
        viewport_width,
        scale,
        ua_browser,
        ua_os,
        frozenset((extra_headers or {}).items()),
    )
    if ctx_key not in _CONTEXTS:
        _CONTEXTS[ctx_key] = browser.new_context(
            viewport={"width": viewport_width, "height": 720},
            user_agent=ua_str,
            device_scale_factor=scale,
            color_scheme="dark" if dark_mode else "light",
            extra_http_headers=hdrs,
        )
        if cookies:
            _CONTEXTS[ctx_key].add_cookies(cookies)
    context = _CONTEXTS[ctx_key]
        
    page = context.new_page()
    
    # ------------------------------------------------------------------ #
    # Optional **payload-slimming**.  When enabled we abort requests for
    # any resource that is *never* required to derive textual content.
    # ------------------------------------------------------------------ #
    if block is None and block_assets:
        block = ["img", "media"]
    if block:
        page.route(
            "**/*",
            lambda route, request: (
                route.abort()
                if _should_block(block, request.resource_type)
                else route.continue_()
            ),
        )

    def _inject(css_text: str):
        # some test stubs fake Page objects without add_init_script
        if hasattr(page, "add_init_script"):
            page.add_init_script(
                f"""(() => {{
                    const style = document.createElement('style');
                    style.textContent = `{css_text}`;
                    document.head.appendChild(style);
                }})();"""
            )

    def _read_css(path: pathlib.Path) -> str:
        """Read *path* once – subsequent calls are served from an in‑memory cache."""
        key = str(path.resolve())
        css = _CSS_CACHE.get(key)
        if css is None:
            css = path.read_text(encoding="utf-8")
            _CSS_CACHE[key] = css
        return css

    _inject(_DEFAULT_ANNOY)
    for css_path in extra_css or []:
        _inject(_read_css(pathlib.Path(css_path)))

    try:
        yield browser, context, page
    finally:
        # Close page & context but deliberately *keep* the browser alive.
        with contextlib.suppress(Exception):
            page.close()


# --------------------------------------------------------------------------- #
#  Async variant – identical semantics · returns **async context‑manager**
# --------------------------------------------------------------------------- #

@contextlib.asynccontextmanager
async def anew_page(
    engine: str = "chromium",
    *,
    proxy: str | None = None,
    dark_mode: bool = False,
    viewport_width: int = DEFAULT_VIEWPORT,
    scale: float = DEFAULT_SCALE,
    extra_headers: dict[str, str] | None = None,
    cookies: Optional[list[dict]] = None,
    ua_browser: Optional[str] = None,
    ua_os: Optional[str] = None,
    extra_css: Optional[List[str]] = None,
    block: Optional[List[str]] = None,
    block_assets: bool = False,               # ← legacy alias
) -> Tuple[ABrowser, ABrowserContext, APage]:

    # ------------------------------------------------------------------ #
    #  Fallback stub when Playwright isn't installed (CI environments)   #
    # ------------------------------------------------------------------ #
    if async_playwright is None:     # pragma: no cover – playwright not installed
        # A *very* small stub good enough for our unit‑tests
        class _DummyRoute:
            def __init__(self, typ): self._typ = typ
            class _Req:                  # mimics r.request.resource_type
                def __init__(self, t): self._t = t
                @property
                def resource_type(self): return self._t
            @property
            def request(self): return self._Req(self._typ)
            def abort(self): pass
            def continue_(self): pass

        class _StubPage:
            def __init__(self): self._routes: list = []
            def add_init_script(self, *a, **kw): pass
            async def route(self, _pat, handler):
                # immediately invoke *once* for a blocked and once for an allowed
                await handler(_DummyRoute("media"))
                await handler(_DummyRoute("image"))
            async def goto(self, *a, **kw): pass

        yield (None, None, _StubPage())
        return

    pw = await async_playwright().start()
    browser_key = (engine, proxy)
    if browser_key not in _BROWSERS:
        launcher = getattr(pw, engine)    # lazy – stub‑friendly
        _BROWSERS[browser_key] = await launcher.launch(
            headless=True, proxy={"server": proxy} if proxy else None
        )
    abrowser: ABrowser = _BROWSERS[browser_key]      # type: ignore[assignment]

    ua_str = _pick_ua(ua_browser, ua_os)
    hdrs = Headers(
        browser=ua_browser or "chrome",
        os=ua_os or "win",
        headers=True,
    ).generate()
    hdrs.update(build_headers(ua_str))
    if extra_headers:
        hdrs.update(extra_headers)

    ctx_key = (
        engine,
        proxy,
        dark_mode,
        viewport_width,
        scale,
        ua_browser,
        ua_os,
        frozenset((extra_headers or {}).items()),
    )
    if ctx_key not in _ACONTEXTS:
        _ACONTEXTS[ctx_key] = await abrowser.new_context(
            viewport={"width": viewport_width, "height": 720},
            user_agent=ua_str,
            device_scale_factor=scale,
            color_scheme="dark" if dark_mode else "light",
            extra_http_headers=hdrs,
        )
        if cookies:
            await _ACONTEXTS[ctx_key].add_cookies(cookies)
    actx = _ACONTEXTS[ctx_key]

    # ── CSS injection mirrors sync path ────────────────────────────────────
    async def _inject(css_text: str):
        await actx.add_init_script(
            f"""(() => {{
                const style = document.createElement('style');
                style.textContent = `{css_text}`;
                document.head.appendChild(style);
            }})();"""
        )

    if ctx_key not in getattr(_inject, "_done", set()):  # inject only once per ctx
        # user‑supplied CSS (cached)
        for css_path in extra_css or []:
            key = str(Path(css_path).resolve())
            if key not in _INJECTED:           # first time only
                _inject(_read_css(Path(css_path)))
                _INJECTED.add(key)
        _inject(_DEFAULT_ANNOY)
        _inject._done = getattr(_inject, "_done", set()) | {ctx_key}  # mark done

    apage = await actx.new_page()
    if block is None and block_assets:
        block = ["img", "media"]
    if block:
        await apage.route(
            "**/*",
            lambda route, request: (
                asyncio.create_task(route.abort())
                if _should_block(block, request.resource_type)
                else asyncio.create_task(route.continue_())
            ),
        )
    try:
        yield abrowser, actx, apage
    finally:
        await apage.close()  # context/browser live on for reuse
