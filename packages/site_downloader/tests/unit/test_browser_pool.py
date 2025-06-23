"""
Successive calls with the same (engine, proxy) share the *same* Browser object.
"""
import site_downloader.browser as br

def _fake_pw():
    class _Page:
        def add_init_script(self, *a, **kw): ...
    class _Ctx:
        def new_page(self): return _Page()
        def close(self): ...
    class _Browser:
        def __init__(self): self.id = id(self)
        def new_context(self, **kw): return _Ctx()
        def close(self): ...
    class _PW:
        def __init__(self): self.chromium = self
        def launch(self, **kw): return _Browser()
    class _SyncMgr:
        def start(self): return _PW()
    return _SyncMgr()

def test_shared_browser(monkeypatch):
    monkeypatch.setattr(br, "sync_playwright", _fake_pw)
    with br.new_page(engine="chromium") as (b1, *_):
        pass
    with br.new_page(engine="chromium") as (b2, *_):
        pass
    assert b1 is b2          # relies on the new _BROWSERS cache 