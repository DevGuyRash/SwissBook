from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from yt_bulk_cc import yt_bulk_cc as ytb


@pytest.fixture(autouse=True)
def restore_sys_argv(monkeypatch):
    original = sys.argv.copy()
    yield
    sys.argv[:] = original


@pytest.fixture
def fake_cues():
    return [
        {"start": 0.0, "duration": 1.0, "text": "Hello"},
        {"start": 1.0, "duration": 1.5, "text": "world"},
    ]


@pytest.fixture
def patch_transcript(monkeypatch, fake_cues):
    class _FakeApi:
        def __init__(self, *a, **kw):
            pass

        def fetch(self, *_, **__):
            class _FT:
                def __init__(self, data):
                    self._data = data

                def to_raw_data(self):
                    return self._data

            return _FT(fake_cues)

    monkeypatch.setattr(ytb.core, "YouTubeTranscriptApi", _FakeApi)
    yield


@pytest.fixture
def patch_scrapetube(monkeypatch):
    vids = [
        {"videoId": f"vid{i}", "title": {"runs": [{"text": f"Demo video {i}"}]}}
        for i in range(3)
    ]
    fake = SimpleNamespace(
        get_playlist=lambda ident, **kw: vids,
        get_channel=lambda channel_url, **kw: vids,
    )
    monkeypatch.setattr(ytb, "scrapetube", fake)
    yield


@pytest.fixture
def patch_detect(monkeypatch):
    monkeypatch.setattr(ytb, "detect", lambda url: ("playlist", "PLfake"))
    yield


def run_cli(tmp_path: Path, *argv: str) -> None:
    sys.argv[:] = ["yt_bulk_cc.py", *argv]
    if "-o" not in argv and "--folder" not in argv:
        sys.argv += ["-o", str(tmp_path)]
    try:
        asyncio.run(ytb.main())
    except SystemExit as e:
        if e.code not in (0, None):
            raise


def extract_header_counts(txt: str) -> tuple[int, int, int]:
    m = re.search(
        r"stats:\s+([\d,]+)\s+words.+?([\d,]+)\s+lines.+?([\d,]+)\s+chars",
        txt,
        re.I | re.S,
    )
    if not m:
        raise AssertionError("stats header missing")
    return tuple(int(x.replace(",", "")) for x in m.groups())


_ANSI_RE = re.compile(r"\x1B\[[0-9;]*[A-Za-z]")


def strip_ansi(txt: str) -> str:
    return _ANSI_RE.sub("", txt)


def stats_lines(block: str) -> list[str]:
    m = re.search(r"File statistics[^\n]*\n(.*?)(?:\n\s*$|\n\n)", block, re.S)
    if not m:
        raise AssertionError("File statistics block not found")
    return [l for l in m.group(1).splitlines() if l.strip()]


def stats_line_tuple(txt: str) -> tuple[int, int, int]:
    m = re.search(
        r"stats:\s+([\d,]+)\s+words.+?([\d,]+)\s+lines.+?([\d,]+)\s+chars",
        txt,
        re.I | re.S,
    )
    if not m:
        raise AssertionError("stats header missing")
    return tuple(int(x.replace(",", "")) for x in m.groups())
