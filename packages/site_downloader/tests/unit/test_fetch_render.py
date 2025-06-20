import pathlib
import importlib.util
import pytest

# Skip automatically when Playwright is unavailable (e.g. in CI without
# browsers) so the rest of the suite still passes.
if importlib.util.find_spec("playwright") is None:
    pytest.skip("Playwright not installed – skipping integration test", allow_module_level=True)

from site_downloader.fetcher import fetch_clean_html

def _stub_new_page(*_, **__):
    """Return a context‑manager yielding a dummy Playwright page."""

    class _Page:
        def goto(self, *a, **kw): ...

        def emulate_media(self, *a, **kw): ...

        def pdf(self, *, path, **kw):
            pathlib.Path(path).write_text("mock")

        def screenshot(self, *a, **kw): ...

    class _Ctx:
        def __enter__(self):  # noqa: D401
            return (None, None, _Page())

        def __exit__(self, *exc): ...

    return _Ctx()


from site_downloader import renderer  # import *after* the stub helper


def _patch(monkeypatch):
    monkeypatch.setattr(renderer, "new_page", _stub_new_page)

def test_example_fetch(tmp_path: pathlib.Path, monkeypatch):
    _patch(monkeypatch)
    html = fetch_clean_html("https://example.com")
    assert "<h1>Example Domain" in html

    out = tmp_path / "example.pdf"
    renderer.render_page("https://example.com", out, engine="chromium")
    assert out.with_suffix(".screen.pdf").exists()
