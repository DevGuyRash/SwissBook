"""Ensure `sdl grab list.txt` triggers the internal batch logic."""

import pathlib

from typer.testing import CliRunner

from site_downloader.cli import app as _cli


def test_auto_batch_detection(tmp_path, monkeypatch):
    called = {}

    def _fake_batch(file, **kw):
        called["file"] = pathlib.Path(file)

    monkeypatch.setattr("site_downloader.cli.batch", _fake_batch)

    url_list = tmp_path / "sites.urls"
    url_list.write_text("https://example.com\nhttps://python.org\n")

    CliRunner().invoke(_cli, ["grab", str(url_list), "-f", "md"])
    assert called["file"] == url_list
