"""
Ensure renderer writes PDF bytes via streaming (uses our stub page.pdf returning bytes).
"""

import pathlib, types
from site_downloader import renderer
import pytest

def _stub_new_page(*_, **__):
    class _Page:
        def goto(self, *a, **k): ...
        def emulate_media(self, *a, **k): ...
        def screenshot(self, *a, **k): ...
        def pdf(self, **kw):
            assert kw.get("path") is None  # streaming path
            return b"%PDF-1.4 MOCK\n%%EOF"
    class _Ctx:
        def __enter__(self): return (None, None, _Page())
        def __exit__(self, *exc): ...
    return _Ctx()

def test_stream(monkeypatch, tmp_path: pathlib.Path):
    monkeypatch.setattr(renderer, "new_page", _stub_new_page)
    out = tmp_path / "ex.pdf"
    renderer.render_page("https://example.com", out, engine="chromium")
    assert out.with_suffix(".screen.pdf").stat().st_size > 10 