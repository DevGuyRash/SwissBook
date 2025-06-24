import importlib.util
import pathlib

import pytest

pytestmark = pytest.mark.e2e

# Skip automatically when Playwright (and its browser binaries) is unavailable
if importlib.util.find_spec("playwright") is None:
    pytest.skip("Playwright not installed – skipping e2e renderer test", allow_module_level=True)

from site_downloader.renderer import render_page


@pytest.mark.parametrize("fmt", ["pdf","png","html","md","txt"])
def test_render_formats(tmp_path: pathlib.Path, fmt: str):
    """End‑to‑end check that real browsers can capture both formats."""
    out = tmp_path / f"example.{fmt}"
    render_page("https://example.com", out, engine="chromium")

    if fmt == "pdf":
        assert out.with_suffix(".screen.pdf").exists()
        assert out.with_suffix(".print.pdf").exists()
    else:
        assert out.exists() and out.stat().st_size > 0
