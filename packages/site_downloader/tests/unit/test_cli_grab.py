"""
CLI‐level tests.  For happy‑path text formats we still spawn the
`sdl` console‑script via ``subprocess`` (matches real user flows),
but for PDF / PNG we execute the CLI **in‑process** so that test
monkey‑patches (which stub Playwright) take effect.
"""

import json
import pathlib
import subprocess
import sys

import pytest
from typer.testing import CliRunner

from site_downloader.cli import app as _cli

BIN = pathlib.Path(sys.executable).parent / "sdl"
_runner = CliRunner()


def _run_subprocess(*args, **kw):
    """Spawn the real console‑script (used by text‑format tests)."""

    return subprocess.run(
        [BIN, *args], check=True, capture_output=True, text=True, **kw
    )


@pytest.mark.parametrize("fmt", ["html", "md", "txt"])
def test_basic_text_formats(tmp_path: pathlib.Path, fmt: str):
    out = tmp_path / f"ex.{fmt}"
    _run_subprocess("grab", "https://example.com", "-f", fmt, "-o", str(out))
    assert out.exists() and out.stat().st_size > 50


def test_pdf_dual(tmp_path: pathlib.Path, monkeypatch):
    # Monkey-patch renderer.render_page so we don't need Playwright binaries
    def _fake_render(url, out, **kw):
        out = pathlib.Path(out)
        # Always mimic dual render for PDF; single PNG otherwise
        if out.suffix == ".pdf":
            out.with_suffix(".screen.pdf").write_text("mock")
            out.with_suffix(".print.pdf").write_text("mock")
        else:
            out.with_suffix(".png").write_text("mock")

    monkeypatch.setattr("site_downloader.renderer.render_page", _fake_render)
    out = tmp_path / "ex.pdf"
    # run **in‐process** so the render_page monkey‐patch is honoured
    result = _runner.invoke(
        _cli, ["grab", "https://example.com", "-f", "pdf", "-o", str(out)]
    )
    assert result.exit_code == 0, result.stderr

    # fake renderer should have created dual PDFs
    assert out.with_suffix(".screen.pdf").exists()
    assert out.with_suffix(".print.pdf").exists()


def test_extra_headers_passthrough(monkeypatch):
    called = {}

    def _fake_new_page(*_, **kw):
        called.update(kw)
        class Dummy:
            def __enter__(self): return (None, None, None)
            def __exit__(self, *args): pass
        return Dummy()

    # Patch both the low‑level helper *and* the dynamic alias that ``fetcher``
    # re‑exports so the stub is honoured no matter which symbol the code
    # resolves at run‑time.
    monkeypatch.setattr("site_downloader.browser.new_page", _fake_new_page)
    monkeypatch.setattr("site_downloader.fetcher.new_page", _fake_new_page)

    hdrs = json.dumps({"X-Test": "1"})
    # Call the CLI function **directly** so the monkey‑patch is visible in‑proc
    # (a subprocess would import the modules afresh and miss the patch).
    from site_downloader.cli import grab

    grab("https://example.com", fmt="html", headers=hdrs)
    assert called["extra_headers"]["X-Test"] == "1"
