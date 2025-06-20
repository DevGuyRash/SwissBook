import re

from site_downloader.utils import sec_ch_headers


def _brand(hdrs):
    return hdrs["Sec-CH-UA"]


def test_chrome_brand():
    ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
    assert "Google Chrome" in _brand(sec_ch_headers(ua))


def test_edge_brand():
    ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36 Edg/120.0"
    )
    brand = _brand(sec_ch_headers(ua))
    assert "Microsoft Edge" in brand
    assert "Google Chrome" not in brand
