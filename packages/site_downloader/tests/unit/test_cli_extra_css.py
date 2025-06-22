import pathlib
from typer.testing import CliRunner
from site_downloader.cli import app as _cli

def test_extra_css_passthrough(tmp_path, monkeypatch):
    css = tmp_path / "hacking.css"
    css.write_text("body{opacity:.5}")

    captured = {}
    def _fake_new_page(*args, **kw):
        captured.update(kw)
        class Dummy:  # noqa: D401
            def __enter__(self): return (None, None, None)
            def __exit__(self, *exc): pass
        return Dummy()

    monkeypatch.setattr("site_downloader.browser.new_page", _fake_new_page)
    CliRunner().invoke(
        _cli,
        ["grab", "https://example.com", "--extra-css", str(css)]
    )
    assert str(css) in captured["extra_css"]
