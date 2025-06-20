from site_downloader.browser import build_headers


def test_mobile_flag_android():
    ua = (
        "Mozilla/5.0 (Linux; Android 14; Pixel 8) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Mobile Safari/537.36"
    )
    h = build_headers(ua)
    assert h["Sec-CH-UA-Mobile"] == "?1"


def test_desktop_flag_windows():
    ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
    )
    h = build_headers(ua)
    assert h["Sec-CH-UA-Mobile"] == "?0"
