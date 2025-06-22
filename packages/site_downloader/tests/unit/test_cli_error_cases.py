import subprocess, sys, pathlib, pytest

BIN = pathlib.Path(sys.executable).parent / "sdl"


def test_unknown_format():
    with pytest.raises(subprocess.CalledProcessError):
        subprocess.run([BIN, "grab", "https://example.com", "-f", "xyz"], check=True)


def test_missing_format_defaults_to_html():
    # This should *succeed* because grab defaults to html.
    out = pathlib.Path("dummy.html")
    p = subprocess.run(
        [BIN, "grab", "https://example.com", "-o", out],
        capture_output=True,
        text=True,
    )
    assert p.returncode == 0


def test_nonexistent_batch_file():
    """
    The CLI layer raises ``typer.Exit`` which is an alias for
    ``click.exceptions.Exit``.  That is the *correct* sentinel to signal an
    early‑abort from Typer - not ``SystemExit``.
    """
    import click

    with pytest.raises(click.exceptions.Exit):
        from site_downloader.cli import batch

        batch.callback  # keep the static‑analysis happy
        batch("does_not_exist.txt", fmt="md")
