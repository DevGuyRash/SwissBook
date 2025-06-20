from site_downloader.utils import sec_ch_headers

def test_sec_ch_mobile():
    ua = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/123.0 Mobile Safari/537.36"
    h = sec_ch_headers(ua)
    assert h["Sec-CH-UA-Mobile"] == "?1"
    assert "Chromium" in h["Sec-CH-UA"]
