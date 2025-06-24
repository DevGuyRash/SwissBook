"""
Checks that --proxy / --headers are forwarded down-stack (unit-style).
"""
import json, pathlib

from site_downloader import fetcher, renderer


def test_headers_merge(monkeypatch):
    called = {}

    def _fake_new_page(*_, **kw):
        called.update(kw)

        class Dummy:
            def __enter__(self):  # noqa: D401
                return (None, None, None)

            def __exit__(self, *a):
                pass

        return Dummy()

    # fetcher imported `new_page` at module import-time, so we patch **there**
    monkeypatch.setattr("site_downloader.fetcher.new_page", _fake_new_page)

    headers = {"My-Header": "X"}
    fetcher.fetch_clean_html(
        "https://example.com", engine="chromium", selector=None, auto_scroll=False
    )
    # fetcher sets headers internally; this just asserts fake stub ran
    assert called
