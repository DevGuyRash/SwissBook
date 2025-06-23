"""
Validate --block img|media prevents route.continue_() being called.
"""

from site_downloader.browser import new_page, anew_page
import pathlib, asyncio
import pytest

class _Req:
    def __init__(self, rtype): self.resource_type = rtype

def test_sync_block(monkeypatch):
    called = {"abort": 0, "cont": 0}

    class _Route:  # noqa: D401
        def abort(self): called["abort"] += 1
        def continue_(self): called["cont"] += 1

    def _fake_route(pattern, handler):
        # simulate two requests
        handler(_Route(), _Req("image"))
        handler(_Route(), _Req("document"))

    monkeypatch.setattr("playwright.sync_api.Page.route", lambda self, p, h: _fake_route(p, h))

    with new_page(block=["img"]) as (_, _, _):
        pass

    assert called["abort"] == 1 and called["cont"] == 1

@pytest.mark.asyncio
async def test_async_block(monkeypatch):
    called = {"abort": 0, "cont": 0}

    class _Route:  # noqa: D401
        async def abort(self): called["abort"] += 1
        async def continue_(self): called["cont"] += 1

    async def _fake_route(self, pattern, handler):
        await handler(_Route(), _Req("media"))
        await handler(_Route(), _Req("image"))

    monkeypatch.setattr("playwright.async_api.Page.route", _fake_route)
    monkeypatch.setattr("site_downloader.browser.async_playwright", None)
    
    async def fake_anew(*a, **kw):
        # Create a mock page object that has the patched `route` method
        class AsyncPage:
            async def route(self, pattern, handler):
                await _fake_route(self, pattern, handler)
        
        class AsyncContext:
            async def new_page(self):
                return AsyncPage()
            async def add_init_script(self, _): ...
            async def add_cookies(self, _): ...
            async def close(self): ...
        
        class AsyncBrowser:
            async def new_context(self, **_):
                return AsyncContext()
            async def close(self): ...

        class _Ctx:
            async def __aenter__(self):
                return AsyncBrowser(), AsyncContext(), AsyncPage()
            async def __aexit__(self, *e): ...
        return _Ctx()

    monkeypatch.setattr("site_downloader.browser.anew_page", fake_anew)
    
    async with anew_page(block=["media"]) as _:
        pass

    assert called["abort"] == 1 and called["cont"] == 1 