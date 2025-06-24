import pathlib
from site_downloader import browser

def test_extra_css_injected_once(tmp_path, monkeypatch):
    css = tmp_path / "mystyle.css"
    css.write_text("body{opacity:.3}")
    calls = {"count": 0}

    class _Page:
        def add_init_script(self, *_a, **_kw):
            calls["count"] += 1
    class _Ctx:
        def new_page(self): return _Page()
        def close(self): ...
    class _PW:
        def __init__(self): self.chromium = self
        def launch(self, **_): return _Ctx()
    class _Mgr:
        def start(self): return _PW()

    monkeypatch.setattr(browser, "sync_playwright", _Mgr)

    for _ in range(3):
        with browser.new_page(extra_css=[str(css)]):
            pass

    # initial annoyances CSS + our custom sheet  →  2 injections max
    assert calls["count"] == 2
