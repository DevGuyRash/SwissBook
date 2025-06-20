"""
Shared fixtures & helpers replacing the old Bash *test_helpers.sh*.
"""
import os, pathlib, subprocess, textwrap, sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]   # repo root
BIN = pathlib.Path(sys.executable).parent / "sdl"

def run_cli(*args, check=True, **kw):
    return subprocess.run([BIN, *args], capture_output=True, text=True, check=check, **kw)


@pytest.fixture(autouse=True)
def tmp_cwd(tmp_path, monkeypatch):
    """Run each test in an isolated tmp dir (mimics helpers.sh)."""
    monkeypatch.chdir(tmp_path)
    yield

def touch(path: pathlib.Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("dummy")
    return path
