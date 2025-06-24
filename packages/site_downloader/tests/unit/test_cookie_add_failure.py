"""
If adding cookies inside browser.new_page() blows up, renderer.render_page()
should convert that into RenderFailure.
"""

import pathlib
import pytest

from site_downloader import renderer
from site_downloader.errors import RenderFailure


def _failing_new_page(*_, **kw):
    # Mimic the inner logic: raise only when cookies were supplied
    if kw.get("cookies"):
        raise Exception("add_cookies failed")

    class _Ctx:
        def __enter__(self):
            class DummyPage:
                def goto(self, *a, **kw): ...
                def screenshot(self, *a, **kw): ...
            return (None, None, DummyPage())

        def __exit__(self, *exc):
            pass

    return _Ctx()


def test_cookie_failure(monkeypatch, tmp_path: pathlib.Path):
    monkeypatch.setattr("site_downloader.renderer.new_page", _failing_new_page)

    with pytest.raises(RenderFailure):
        renderer.render_page(
            "https://example.com",
            tmp_path / "x.png",
            cookies=[{"name": "a"}],  # triggers the failure path
        )
