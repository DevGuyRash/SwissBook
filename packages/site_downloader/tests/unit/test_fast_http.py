"""
Fast-HTTP path must bypass Playwright & return body.
"""
import site_downloader.fetcher as _fetcher

def test_fast_http(monkeypatch):
    html_stub = "<html><body>hi</body></html>"
    # monkey-patch urllib so there is zero network traffic
    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *exc): pass
        def read(self): return html_stub.encode()

    def _urlopen(req, timeout=0):          # noqa: D401
        return _Resp()

    monkeypatch.setattr(_fetcher.urllib.request, "urlopen", _urlopen)

    out = _fetcher.fetch_clean_html("https://ex.com", fast_http=True)
    assert out == html_stub 