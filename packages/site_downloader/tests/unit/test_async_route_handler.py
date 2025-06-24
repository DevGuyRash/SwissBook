import asyncio
import pytest
from site_downloader.browser import anew_page

@pytest.mark.asyncio
async def test_async_block_wrapper(monkeypatch):
    """Confirm that the new _route_handler awaits when necessary."""
    log = {"abort": 0, "cont": 0}

    class _Route:
        async def abort(self): log["abort"] += 1
        async def continue_(self): log["cont"] += 1

    async def _fake_route(self, _pat, handler):
        await handler(_Route(), type("req", (), {"resource_type": "image"}))
        await handler(_Route(), type("req", (), {"resource_type": "document"}))

    # Stub environment - we only care that *route* calls the handler
    monkeypatch.setattr("playwright.async_api.Page.route", _fake_route)
    monkeypatch.setattr("site_downloader.browser.async_playwright", None)  # trigger fallback stub

    # New semantics: "media" == audio/video, so use "img" to block images
    async with anew_page(block=["img"]) as _:
        pass

    # image  → abort
    # document → continue
    assert log == {"abort": 1, "cont": 1}
