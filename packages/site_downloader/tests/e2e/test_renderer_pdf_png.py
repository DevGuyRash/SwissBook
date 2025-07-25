import importlib.util
import pathlib

import pytest

pytestmark = pytest.mark.e2e

# Skip automatically when Playwright (and its browser binaries) is unavailable
if importlib.util.find_spec("playwright") is None:
    pytest.skip("Playwright not installed - skipping e2e renderer test", allow_module_level=True)

from site_downloader.renderer import render_page
from site_downloader.errors import RenderFailure


@pytest.mark.parametrize(
    "engine,fmt",
    [
        ("chromium", "pdf"),          # dual render path
        ("chromium", "png"),          # baseline
        ("firefox",  "png"),          # fallback engine
        ("webkit",   "png"),          # Safari/WebKit
    ],
)
def test_render_formats(tmp_path: pathlib.Path, engine: str, fmt: str):
    """End-to-end check that real browsers can capture both formats."""
    out = tmp_path / f"example.{fmt}"
    try:
        render_page("https://example.com", out, engine=engine)
    except RenderFailure as exc:
        msg = str(exc).lower()
        missing = (
            "missing dependencies",
            "libicu",
            "libxml2",
            "libwebp",
            "error while loading shared libraries",
            "executable doesn't exist",
        )
        if any(k in msg for k in missing):
            hint = (
                "WebKit not available – install native deps with:\n"
                "   python -m playwright install --with-deps"
            )
            pytest.skip(hint)
        raise

    if fmt == "pdf":
        assert out.with_suffix(".screen.pdf").exists()
        assert out.with_suffix(".print.pdf").exists()
    else:
        assert out.exists() and out.stat().st_size > 0
