# packages/site_downloader/tests/unit/test_cli_error_cases.py
import subprocess, sys, pathlib, pytest
from typer.testing import CliRunner
from site_downloader.cli import app

BIN = pathlib.Path(sys.executable).parent / "sdl"

def test_unknown_format():
    # This test is valid as-is, checking that the CLI exits with an error for bad input.
    with pytest.raises(subprocess.CalledProcessError):
        subprocess.run([BIN, "grab", "https://example.com", "-f", "xyz"], check=True, capture_output=True)

def test_missing_format_defaults_to_html(monkeypatch):
    """
    Verify that calling `grab` without `-f` results in the underlying
    logic being called with `fmt='html'`. This is a unit test.
    """
    # Track what gets called in the conversion step
    convert_calls = []

    def fake_convert_html(html_raw, fmt):
        convert_calls.append(fmt)
        return html_raw  # Just return the input

    def fake_fetch_clean_html(*args, **kwargs):
        return "<html><body>test</body></html>"

    # Patch the conversion and fetching functions at their source modules
    monkeypatch.setattr("site_downloader.convert.convert_html", fake_convert_html)
    monkeypatch.setattr("site_downloader.fetcher.fetch_clean_html", fake_fetch_clean_html)

    runner = CliRunner()
    # Invoke the CLI command in-process without specifying a format.
    result = runner.invoke(app, ["grab", "https://example.com"])

    # Check that the CLI command exited successfully.
    assert result.exit_code == 0, result.stdout
    # Verify that convert_html was called with the correct default format.
    assert len(convert_calls) == 1
    assert convert_calls[0] == "html"


def test_nonexistent_batch_file():
    """
    The CLI layer raises ``typer.Exit`` which is an alias for
    ``click.exceptions.Exit``.  That is the *correct* sentinel to signal an
    early-abort from Typer - not ``SystemExit``.
    """
    import click
    from site_downloader.cli import batch

    with pytest.raises(click.exceptions.Exit):
        # Directly call the typer-decorated function's callback with a bad path
        batch.callback(pathlib.Path("does_not_exist.txt"), fmt="md")
