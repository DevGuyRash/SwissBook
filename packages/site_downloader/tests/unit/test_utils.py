from site_downloader.utils import extract_url, sanitize_url_for_filename

def test_extract_url():
    assert extract_url("[x](https://a/b)") == "https://a/b"
    assert extract_url("https://a/b") == "https://a/b"

def test_sanitize():
    assert sanitize_url_for_filename("https://ex.com/p?q=v") == "ex.com_p_q_v"
