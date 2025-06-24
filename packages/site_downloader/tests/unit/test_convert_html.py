import pytest

from site_downloader.convert import convert_html

HTML = "<h1>Title</h1><p><b>bold</b> and <i>italic</i></p>"


@pytest.mark.parametrize("fmt", ["html", "md", "txt"])
def test_text_conversions(fmt):
    out = convert_html(HTML, fmt)
    assert isinstance(out, str) and len(out) > 10
