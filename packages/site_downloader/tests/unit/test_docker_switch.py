"""
Fast unit test that exercises the Docker branch of browser.new_page
without touching a real Docker daemon or Playwright browsers.
"""

import types

import site_downloader.browser as br


def _fake_docker_ctx():
    """Pretend docker_chromium returned a CDP websocket URL."""

    class _Ctx:
        def __enter__(self):
            return {"wsEndpoint": "ws://fake"}

        def __exit__(self, *exc):
            pass

    return _Ctx()


def test_docker_branch(monkeypatch):
    # Force env var so new_page goes into Docker mode
    monkeypatch.setenv("SDL_PLAYWRIGHT_DOCKER", "1")

    # Stub docker_runtime.docker_chromium
    monkeypatch.setattr(
        "site_downloader.docker_runtime.docker_chromium", _fake_docker_ctx
    )

    # Fake Playwright connect_over_cdp ➜ returns dummy Browser/Context/Page
    class _Pg:
        def add_init_script(self, *a, **kw):
            pass

    class _Ctx:
        def new_page(self):
            return _Pg()

        def add_cookies(self, *_):
            pass

        def close(self):
            pass

    class _Br:
        def new_context(self, **kw):
            return _Ctx()

        def close(self):
            pass

    class _PW:
        def __init__(self):
            self.chromium = self  # both launcher *and* CDP client

        def connect_over_cdp(self, ws):  # called by real code
            assert ws == "ws://fake"
            return _Br()

        # fallback path exercised when .connect_over_cdp is monkey‑removed
        def launch(self, *, headless: bool = True):
            return _Br()

    monkeypatch.setattr(
        br, "sync_playwright", lambda: types.SimpleNamespace(start=lambda: _PW())
    )

    with br.new_page(use_docker=True) as (_b, _c, page):
        # Smoke assertion: page exists and env var triggered branch
        assert page is not None

    # Clean‑up env to avoid side‑effects on other tests
    monkeypatch.delenv("SDL_PLAYWRIGHT_DOCKER", raising=False) 