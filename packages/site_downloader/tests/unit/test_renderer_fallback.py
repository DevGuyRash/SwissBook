"""Renderer fallback: non-Chromium engine → PNG screenshot only."""

import pathlib

from site_downloader import renderer


def _stub_new_page(*_, **__):
    class _Page:
        def goto(self, *a, **kw): ...

        def screenshot(self, *, path, full_page):
            pathlib.Path(path).write_text("mock")

    class _Ctx:
        def __enter__(self):
            return (None, None, _Page())

        def __exit__(self, *exc): ...

    return _Ctx()


def test_png_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(renderer, "new_page", _stub_new_page)
    out = tmp_path / "page.png"
    renderer.render_page("https://example.com", out, engine="firefox")
    assert out.exists() and out.stat().st_size > 0

def test_webkit_png_fallback(monkeypatch, tmp_path):
    # reuse the local stub – avoids import‑path issues when the tests
    # directory is not inside the installed package.
    monkeypatch.setattr(renderer, "new_page", _stub_new_page)

    out = tmp_path / "page.png"
    renderer.render_page("https://example.com", out, engine="webkit")
    assert out.exists() and out.stat().st_size > 0
