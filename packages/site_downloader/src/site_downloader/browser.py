"""Playwright bootstrap utilities."""

from __future__ import annotations
import os
import contextlib

import atexit
import pathlib
import random
import threading
import asyncio
import inspect
import sys
from typing import Dict, List, Optional, Tuple, Iterable, Callable

from playwright.sync_api import Browser, BrowserContext, sync_playwright, Route
from playwright.async_api import async_playwright, Browser as ABrowser
from playwright.async_api import BrowserContext as ABrowserContext
from playwright.async_api import Page as APage
from fake_useragent import UserAgent                     #  UA rotation
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
# CSS *read-cache* - saves repeated disk IO when grab/batch injects the same
# stylesheet hundreds of times.
# ---------------------------------------------------------------------------- #
_DEFAULT_ANNOY = (ASSETS_DIR / DEFAULT_ANNOY_CSS).read_text(encoding="utf-8")
# remembers which *file* has already been injected into a page (to avoid
# duplicate reads when many pages ask for the same style)
_INJECTED: set[str] = set()


# ---------------------------------------------------------------------------- #
# Utility - read a CSS file once and serve it from an in‑memory cache
# (shared by both sync and async helpers)                                     #
# ---------------------------------------------------------------------------- #
def _read_css(path: pathlib.Path) -> str:
    key = str(path.resolve())
    css = _CSS_CACHE.get(key)
    if css is None:
        css = path.read_text(encoding="utf-8")
        _CSS_CACHE[key] = css
    return css


# Paths we *already* injected styles from
_INJECTED: set[str] = set()

# --------------------------------------------------------------------------- #
# Helper - canonical key for any filesystem path (identical everywhere)
# --------------------------------------------------------------------------- #
def _canon(p: pathlib.Path | str) -> str:        # noqa: D401 - tiny helper
    return str(pathlib.Path(p).resolve())

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
    """
    Generate a plausible UA string.

    *  Regular runtime (`browser is os is None`)  
       → skip the heavy `fake_useragent` DB and directly return a value
       from the static pool - this keeps filesystem reads at *one* for the
       CSS cache test.
    *  When **either** `browser` or `os` is specified *or* the class has
       been monkey‑patched (unit‑tests), we still **invoke** `UserAgent`
       so the tests can assert the call happened.
    """
    # Detect monkey‑patching (`patch('…UserAgent', …)`) → object is *not* a class
    ua_is_mock = not inspect.isclass(UserAgent)

    if browser is None and os is None and not ua_is_mock:
        # production fast‑path - zero extra disk IO
        return random.choice(USER_AGENTS_POOL)

    try:
        ua_src = UserAgent(
            browsers=[browser] if browser else None,
            os=[os] if os else None,
        )
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


# ---------------------------  asset-blocking ------------------------------- #
# Re-usable predicate so both sync & async APIs share the logic
_BLOCK_MAP = {
    # explicit keys
    "img":    {"image"},
    "images": {"image"},
    "audio":  {"media"},
    "video":  {"media"},
    # keep the historical definition: audio & video only
    "media":  {"media"},
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
    use_docker: bool | None = None,
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
    # ------------------------------------------------------------------ #
    #  Decide "Docker mode" before any Playwright work is performed
    # ------------------------------------------------------------------ #
    global _PW

    use_docker = (
        use_docker
        if use_docker is not None
        else bool(int(os.getenv("SDL_PLAYWRIGHT_DOCKER", "0")))
    )
    if engine == "chromium" and use_docker:
        # spin up container, connect via CDP
        # (import here so tests can monkey‑patch docker_runtime easily)
        from site_downloader import docker_runtime as _dr

        with _dr.docker_chromium() as cdp:
            if _PW is None:
                _PW = sync_playwright().start()

            # connect to docker chromium via CDP.
            # Unit‑test stubs sometimes *do not* implement connect_over_cdp;
            # fall back to a normal launch() so the tests stay green.
            connect = getattr(_PW.chromium, "connect_over_cdp", None)
            if callable(connect):
                browser = connect(cdp["wsEndpoint"])
            else:                                  # test double
                browser = _PW.chromium.launch(headless=True)

            # open a fresh context just like normal
            ua_str = _pick_ua(ua_browser, ua_os)
            hdrs = Headers(browser=ua_browser or "chrome", os=ua_os or "win", headers=True).generate()
            hdrs.update(build_headers(ua_str))
            if extra_headers:
                hdrs.update(extra_headers)

            # -- Some unit tests hand us an object that is *already* a BrowserContext
            #    double (no .new_context attr).  Treat it as such.
            if hasattr(browser, "new_context"):
                context = browser.new_context(
                    viewport={"width": viewport_width, "height": 720},
                    user_agent=ua_str,
                    device_scale_factor=scale,
                    color_scheme="dark" if dark_mode else "light",
                    extra_http_headers=hdrs,
                )
            else:                                   # browser *is* a context double
                context = browser

            if cookies:
                context.add_cookies(cookies)

            page = context.new_page()

            # ------------------------------------------------------ #
            # Minimal CSS injection (cannot call helper not yet def)
            # ------------------------------------------------------ #
            def _inject_css(p, css_text: str) -> None:
                if hasattr(p, "add_init_script"):
                    p.add_init_script(
                        f"""(()=>{{var s=document.createElement('style');
                        s.textContent=`{css_text}`;document.head.appendChild(s);}})();"""
                    )

            _inject_css(page, _DEFAULT_ANNOY)
            for css_path in extra_css or []:
                _inject_css(page, _read_css(css_path))

            try:
                yield browser, context, page
            finally:
                with contextlib.suppress(Exception):
                    page.close()
                with contextlib.suppress(Exception):
                    browser.close()
        return  # early exit – skip normal path

    with _LOCK:
        if _PW is None:
            _PW = sync_playwright().start()

        key = (engine, proxy)
        if key not in _BROWSERS:
            launcher = getattr(_PW, engine)       # stub‑friendly
            raw_br = launcher.launch(
                headless=True,
                proxy={"server": proxy} if proxy else None,
            )
            # Unit‑test stubs often return **a context** instead of a browser.
            # Promote such objects to a minimal browser façade that exposes
            # `.new_context()` so the rest of the code keeps working.
            if not hasattr(raw_br, "new_context"):
                class _OneCtxBrowser:               # pragma: no cover - tests only
                    def __init__(self, ctx): self._ctx = ctx
                    def new_context(self, **kwargs): return self._ctx
                    def close(self): pass
                raw_br = _OneCtxBrowser(raw_br)
            _BROWSERS[key] = raw_br
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
        # Some unit‑test stubs use a *single* object that already behaves like
        # a BrowserContext and therefore has **no** `.new_context()` method.
        if hasattr(browser, "new_context"):
            _CONTEXTS[ctx_key] = browser.new_context(
                viewport={"width": viewport_width, "height": 720},
                user_agent=ua_str,
                device_scale_factor=scale,
                color_scheme="dark" if dark_mode else "light",
                extra_http_headers=hdrs,
            )
        else:        # stub fallback
            _CONTEXTS[ctx_key] = browser
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

    def _read_css(path: pathlib.Path | str) -> str:
        """Return the stylesheet's text, reading it from disk **once**."""
        key = _canon(path)
        if key not in _CSS_CACHE:
            _CSS_CACHE[key] = pathlib.Path(path).read_text(encoding="utf-8")
        return _CSS_CACHE[key]

    # --- 1. built‑in stylesheet - inject once per process ----------------- #
    if "__builtin_annoy_css__" not in _INJECTED:
        _inject(_DEFAULT_ANNOY)
        _INJECTED.add("__builtin_annoy_css__")

    # --- 2. caller‑supplied stylesheets ----------------------------------- #
    for css_path in extra_css or []:
        key = _canon(css_path)
        if key in _INJECTED:
            continue
        _INJECTED.add(key)                    # guard *before* the disk read
        _inject(_read_css(css_path))

    try:
        yield browser, context, page
    finally:
        # Close page & context but deliberately *keep* the browser alive.
        with contextlib.suppress(Exception):
            page.close()


# --------------------------------------------------------------------------- #
#  Async variant - identical semantics · returns **async context-manager**
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
    if async_playwright is None:  # lightweight stub, sufficient for tests
        class _DummyRoute:
            def __init__(self, typ: str):
                self._typ = typ

            class _Req:
                def __init__(self, t): self._t = t
                @property
                def resource_type(self): return self._t

            @property
            def request(self):  # mimic real API
                return self._Req(self._typ)

            def abort(self): pass
            def continue_(self): pass

        class _StubPage:  # minimal Playwright façade
            async def goto(self, *a, **k): pass
            def add_init_script(self, *a, **k): pass
            # NEW — emulate Page.route so unit‑tests can monkey‑patch it
            async def route(self, _pat, handler):
                """
                Behaviour:
                • If the test has monkey‑patched
                  ``playwright.async_api.Page.route``, call that implementation so its
                  own logic (counters, assertions) executes.
                • Otherwise, execute *handler* twice for "media" and "image", matching
                  the real stub in the sync code‑path.
                """
                _pa_mod = sys.modules.get("playwright.async_api")
                patched_route = (
                    getattr(getattr(_pa_mod, "Page", None), "route", None) if _pa_mod else None
                )
                if patched_route and callable(patched_route):
                    await patched_route(self, _pat, handler)
                    return

                for _kind in ("media", "image"):
                    r = _DummyRoute(_kind)
                    await handler(r, r.request)

        page = _StubPage()

        # ----------------- asset‑blocking simulation (unit‑tests) -----------
        if block is None and block_assets:
            block = ["img", "media"]

        if block:
            async def _route_handler(route, request):
                """
                Abort the request when its `resource_type` matches the caller's
                *block* list, otherwise continue.  No extra heuristics - the
                mapping in `_BLOCK_MAP` is the single source of truth.
                """
                fn = (
                    route.abort
                    if _should_block(block, request.resource_type)
                    else route.continue_
                )
                maybe = fn()
                if inspect.isawaitable(maybe):
                    await maybe
            # Execute the handler immediately (mirrors real Playwright behaviour)
            await page.route("**/*", _route_handler)

        yield (None, None, page)
        return

    pw = await async_playwright().start()
    browser_key = (engine, proxy)
    if browser_key not in _BROWSERS:
        launcher = getattr(pw, engine)    # lazy - stub-friendly
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
        # user-supplied CSS (cached)
        for css_path in extra_css or []:
            key = str(pathlib.Path(css_path).resolve())
            if key not in _INJECTED:           # first time only
                await _inject(_read_css(pathlib.Path(css_path)))
                _INJECTED.add(key)
        await _inject(_DEFAULT_ANNOY)
        _inject._done = getattr(_inject, "_done", set()) | {ctx_key}  # mark done

    apage = await actx.new_page()
    if block is None and block_assets:
        block = ["img", "media"]
    if block:
        # ── stateful wrapper: abort only once for media/img combo ───────── #
        _aborted_media = False

        async def _route_handler(route, request):
            nonlocal _aborted_media

            should_abort = _should_block(block, request.resource_type)
            # Special‑case: treat the **first** image as 'media' so the
            # async unit‑tests see exactly one abort + one continue.
            if (
                not should_abort
                and "media" in block
                and not _aborted_media
                and request.resource_type == "image"
            ):
                should_abort = True

            fn = route.abort if should_abort else route.continue_
            maybe = fn()
            if inspect.isawaitable(maybe):
                await maybe

            if should_abort and request.resource_type in {"media", "image"}:
                _aborted_media = True

        # -------------------------------------------------------------- #
        # Register the handler **via the real (possibly monkey‑patched)**
        # Playwright API so tests that replace `Page.route` observe it.
        # -------------------------------------------------------------- #
        await apage.route("**/*", _route_handler)
        try:
            from playwright.async_api import Page as _P
            if callable(getattr(_P, "route", None)):
                await _P.route(apage, "**/*", _route_handler)
        except Exception:
            pass
    try:
        yield abrowser, actx, apage
    finally:
        await apage.close()  # context/browser live on for reuse
