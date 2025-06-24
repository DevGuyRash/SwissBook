import pathlib

import pytest

from site_downloader import renderer, convert
from site_downloader.errors import InvalidURL, PandocMissing


def test_invalid_url():
    with pytest.raises(InvalidURL):
        renderer.render_page("ftp://example.org", pathlib.Path("x.pdf"))


def test_pandoc_missing(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda *_: None)
    with pytest.raises(PandocMissing):
        convert.convert_html("<p>Hi</p>", "docx")
