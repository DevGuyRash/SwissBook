import pytest

from site_downloader.convert import convert_html

HTML = "<h1>Title</h1><p><b>bold</b> and <i>italic</i></p>"


@pytest.mark.parametrize("fmt", ["html", "md", "txt"])
def test_text_conversions(fmt):
    out = convert_html(HTML, fmt)
    assert isinstance(out, str) and len(out) > 10


def test_markitdown_path(monkeypatch):
    class DummyResult:
        text_content = "ok"

    class DummyMD:
        def convert_stream(self, *args, **kwargs):
            return DummyResult()

    monkeypatch.setattr("site_downloader.convert.MarkItDown", lambda: DummyMD())
    monkeypatch.setattr("site_downloader.convert._MARKITDOWN_AVAILABLE", True)
    out = convert_html(HTML, "md")
    assert out == "ok"


def test_markdownify_fallback(monkeypatch):
    calls = {}

    def fake_mdify(html, *, heading_style="ATX"):
        calls["html"] = html
        calls["style"] = heading_style
        return "fallback"

    monkeypatch.setattr("site_downloader.convert._MARKITDOWN_AVAILABLE", False)
    monkeypatch.setattr("site_downloader.convert.mdify", fake_mdify)
    out = convert_html(HTML, "md")
    assert out == "fallback"
    assert calls["style"] == "ATX"
