"""
new_page(...) must register a `route` filter when block_assets=True.
"""
import site_downloader.browser as br

def make_stubs():
    class _Page:
        def __init__(self):
            self.routes = []
        def route(self, pattern, handler):
            self.routes.append(pattern)
        # required noop methods
        def add_init_script(self, *a, **kw): ...
    class _Ctx:
        def __init__(self): self.page = _Page()
        def new_page(self): return self.page
        def close(self): ...
    class _Browser:
        def new_context(self, **kw): return _Ctx()
        def close(self): ...
    class _PW:
        def __init__(self): self.chromium = self
        def launch(self, **kw): return _Browser()
    class _SyncMgr:
        def start(self): return _PW()
    return _SyncMgr()

def test_route_added(monkeypatch):
    monkeypatch.setattr(br, "sync_playwright", make_stubs)
    with br.new_page(block_assets=True) as (_, context, page):
        pass
    # our stub stored the pattern
    assert page.routes == ["**/*"] 

