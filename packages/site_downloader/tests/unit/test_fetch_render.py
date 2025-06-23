import pathlib
import importlib.util
import pytest

# Skip automatically when Playwright is unavailable (e.g. in CI without
# browsers) so the rest of the suite still passes.
if importlib.util.find_spec("playwright") is None:
    pytest.skip("Playwright not installed - skipping integration test", allow_module_level=True)

from site_downloader.fetcher import fetch_clean_html

def _stub_new_page(*_, **__):
    """Return a context-manager yielding a dummy Playwright page."""

    class _Page:
        def goto(self, *a, **kw):
            pass

        # ── Methods used by renderer paths ────────────────────────────────────
        def emulate_media(self, *a, **kw):
            pass

        def pdf(self, *, path, **kw):
            pathlib.Path(path).write_text("mock")

        def screenshot(self, *a, **kw):
            pass

        # ── Methods used by fetcher paths ─────────────────────────────────────
        def evaluate(self, script: str):
            # Return a constant height so _auto_scroll exits after one loop.
            if "scrollHeight" in script and "scrollTo" not in script:
                return 1000
            return None

        def content(self):
            # Minimal HTML that satisfies the assertion in the test.
            return (
                "<html><body><h1>Example Domain</h1>"
                "<p>Lorem ipsum dolor sit amet</p></body>"
            )

    class _Ctx:
        def __enter__(self):  # noqa: D401
            return (None, None, _Page())

        def __exit__(self, *exc): ...

    return _Ctx()


from site_downloader import renderer  # import *after* the stub helper
import site_downloader.browser as _browser
import site_downloader.fetcher as _fetcher


def _patch(monkeypatch):
    """
    Patch **every** public entry-point that could lead to Playwright:

    * site_downloader.renderer.new_page   - used by render_page()
    * site_downloader.browser.new_page    - root implementation
    * site_downloader.fetcher.new_page    - dynamic alias used by fetcher
    """
    monkeypatch.setattr(renderer, "new_page", _stub_new_page)
    monkeypatch.setattr(_browser, "new_page", _stub_new_page)
    monkeypatch.setattr(_fetcher, "new_page", _stub_new_page)

def test_example_fetch(tmp_path: pathlib.Path, monkeypatch):
    _patch(monkeypatch)
    html = fetch_clean_html("https://example.com")
    assert "<h1>Example Domain" in html

    out = tmp_path / "example.pdf"
    renderer.render_page("https://example.com", out, engine="chromium")
    assert out.with_suffix(".screen.pdf").exists()
