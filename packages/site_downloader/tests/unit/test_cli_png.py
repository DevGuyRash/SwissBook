"""
Exercise the `sdl grab -f png` path.  We stub the Playwright layer so the test
doesn't need browser binaries.
"""

import pathlib
import sys

import pytest
from typer.testing import CliRunner

from site_downloader.cli import app as _cli

BIN = pathlib.Path(sys.executable).parent / "sdl"
_runner = CliRunner()


def _patch_new_page(monkeypatch):
    """Replace site_downloader.renderer.new_page with a no-op context-manager."""

    class DummyPage:
        def goto(self, *a, **kw):
            pass

        def screenshot(self, *, path, full_page):
            pathlib.Path(path).write_text("mock")

        # not used in PNG path but harmless to keep
        def emulate_media(self, *a, **kw):
            pass

        def pdf(self, *, path, **kw):
            pathlib.Path(path).write_text("mock")

    def _fake_new_page(*_, **__):
        class _Ctx:
            def __enter__(self):
                return (None, None, DummyPage())

            def __exit__(self, *exc):
                pass

        return _Ctx()

    monkeypatch.setattr("site_downloader.renderer.new_page", _fake_new_page)


def test_png_render(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    _patch_new_page(monkeypatch)
    out = tmp_path / "page.png"

    # execute CLI in‑process so the new_page patch is respected
    result = _runner.invoke(
        _cli, ["grab", "https://example.com", "-f", "png", "-o", str(out)]
    )
    assert result.exit_code == 0, result.stderr

    assert out.exists() and out.stat().st_size > 0
