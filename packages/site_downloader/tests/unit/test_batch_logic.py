import pathlib, subprocess, sys

import pytest

BIN = pathlib.Path(sys.executable).parent / "sdl"


def _fake_grab(*args, **kw):
    # Simply touch the expected output file so batch logic can see it.
    out = pathlib.Path(kw["out"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("ok")


def test_batch_all_formats(tmp_path: pathlib.Path, monkeypatch):
    # Stub grab() so Playwright isn't invoked.
    monkeypatch.setattr("site_downloader.cli.grab", _fake_grab)

    batch_file = tmp_path / "urls.txt"
    batch_file.write_text("https://example.com\n")

    subprocess.run(
        [
            BIN,
            "batch",
            str(batch_file),
            "-f",
            "md",
            "--jobs",
            "1",
        ],
        check=True,
    )
    out = tmp_path / "out" / "example.com.md"
    assert out.exists()
