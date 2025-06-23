"""
Successive new_page() calls that share *all* identity parameters must
receive the **same** BrowserContext (pooling layer).
"""

import site_downloader.browser as br


def _fake_playwright():
    """Minimal stub that exposes .chromium.launch().new_context()."""
    class _Page: ...
    class _Ctx:
        def __init__(self):
            self.id = id(self)
        def new_page(self): return _Page()
    class _Browser:
        def __init__(self):
            self.id = id(self)
        def new_context(self, **kw):
            self.ctx = getattr(self, "ctx", _Ctx())
            return self.ctx
        def close(self): ...
    class _PW:
        def __init__(self): self.chromium = self
        def launch(self, **kw): return _Browser()
    class _Mgr:
        def start(self): return _PW()
    return _Mgr()


def test_context_reuse(monkeypatch):
    # hijack sync_playwright so no real browsers are required
    monkeypatch.setattr(br, "sync_playwright", _fake_playwright)

    with br.new_page(engine="chromium", proxy=None) as (b1, c1, p1):
        pass
    with br.new_page(engine="chromium", proxy=None) as (b2, c2, p2):
        pass

    # shared Browser object was already tested in test_browser_pool
    assert c1 is c2, "Context should be pooled across calls with same identity" 