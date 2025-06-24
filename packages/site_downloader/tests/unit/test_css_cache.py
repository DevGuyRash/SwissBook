"""
Repeated injection of the same extra‑CSS file must hit the in‑memory cache.
"""
import pathlib
from site_downloader import browser

def test_css_read_cache(monkeypatch, tmp_path):
    css = tmp_path / "x.css"
    css.write_text("body{opacity:.1}")

    reads = {"count": 0}
    orig_read = pathlib.Path.read_text

    def _counted(self, *a, **kw):
        reads["count"] += 1
        return orig_read(self, *a, **kw)

    monkeypatch.setattr(pathlib.Path, "read_text", _counted)

    for _ in range(3):
        with browser.new_page(extra_css=[str(css)]):
            pass

    # first call only
    assert reads["count"] == 1 