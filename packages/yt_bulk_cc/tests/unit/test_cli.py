import asyncio
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from yt_bulk_cc import yt_bulk_cc as ytb
from yt_bulk_cc.errors import IpBlocked, TooManyRequests, NoTranscriptFound
from youtube_transcript_api.proxies import GenericProxyConfig, WebshareProxyConfig

from conftest import (
    run_cli,
    extract_header_counts,
    strip_ansi,
    stats_lines,
    stats_line_tuple,
)


@pytest.mark.parametrize("fmt", ["srt", "webvtt", "text", "pretty", "json"])
def test_download_single_format(tmp_path: Path, fmt):
    """Download playlist (stubbed) in every format; verify 3 files appear."""
    run_cli(tmp_path, "https://youtu.be/dQw4w9WgXcQ", "-f", fmt, "-n", "3")
    files = sorted(tmp_path.glob(f"*.{ytb.EXT[fmt]}"))
    assert len(files) == 3, f"expected 3 {fmt} files, got {files}"


@pytest.mark.usefixtures("patch_transcript", "patch_scrapetube", "patch_detect")
@pytest.mark.parametrize("unit", ["w", "c", "l"])
def test_concat_with_split(tmp_path: Path, unit):
    """Force split threshold of 1 so every transcript rolls to next file."""
    run_cli(
        tmp_path,
        "dummy",  # URL ignored by detect patch
        "-f",
        "text",
        "-C",
        "--basename",
        "bundle",
        "--split",
        f"1{unit}",
        "-n",
        "3",
    )
    parts = sorted(tmp_path.glob("bundle_*.txt"))
    # 3 videos * separator headings -> at least 3 files when threshold is tiny
    assert len(parts) >= 3
    # header must contain stats line
    header = parts[0].read_text().splitlines()[0]
    assert header.startswith("# stats:")


@pytest.mark.usefixtures("patch_transcript", "patch_scrapetube", "patch_detect")
def test_text_concat_unique_videos(tmp_path: Path):
    """Concatenated text output should contain each video once in order."""
    run_cli(
        tmp_path,
        "dummy",
        "-f",
        "text",
        "-C",
        "--basename",
        "bundle",
        "-n",
        "3",
    )
    out = tmp_path / "bundle.txt"
    data = out.read_text()
    ids = [f"vid{i}" for i in range(3)]
    for vid in ids:
        assert data.count(vid) >= 1, f"{vid} missing in concat"
    seps = [l for l in data.splitlines() if l.startswith("──── ")]
    assert len(seps) == 3


@pytest.mark.usefixtures("patch_transcript", "patch_scrapetube", "patch_detect")
def test_json_concat_contains_meta_and_stats(tmp_path: Path):
    run_cli(
        tmp_path,
        "dummy",
        "-f",
        "json",
        "-C",
        "--basename",
        "combo",
        "-n",
        "3",
    )
    out = tmp_path / "combo.json"
    assert out.exists()
    data = json.loads(out.read_text())
    assert {"stats", "items"} <= data.keys()
    assert data["stats"]["words"] > 0
    assert len(data["items"]) == 3


@pytest.mark.usefixtures("patch_transcript", "patch_scrapetube", "patch_detect")
def test_json_concat_unique_videos(tmp_path: Path):
    """Ensure concatenated JSON lists each video exactly once."""
    run_cli(
        tmp_path,
        "dummy",
        "-f",
        "json",
        "-C",
        "--basename",
        "combo",
        "-n",
        "3",
    )
    out = tmp_path / "combo.json"
    vids = [item["video_id"] for item in json.loads(out.read_text())["items"]]
    assert vids == [f"vid{i}" for i in range(3)]


# ────────────────────────── converter  ─────────────────────────────────── #
@pytest.mark.usefixtures("patch_transcript", "patch_scrapetube", "patch_detect")
def test_converter_to_srt(tmp_path: Path):
    """Generate JSON first, then convert to SRT via --convert."""
    # step 1: download single JSON file
    run_cli(tmp_path, "dummy", "-f", "json", "-n", "1")
    jfile = next(tmp_path.glob("*.json"))
    # step 2: convert
    run_cli(tmp_path, "--convert", str(jfile), "-f", "srt")
    converted = jfile.with_suffix(".srt")
    assert converted.exists()
    txt = converted.read_text()
    assert "NOTE stats:" in txt.splitlines()[0] or txt.startswith("1\n")


# NEW: convert a *concatenated* JSON created by --concat, exercising _extract_cues
@pytest.mark.usefixtures("patch_transcript", "patch_scrapetube", "patch_detect")
@pytest.mark.parametrize("dest_fmt", ["text", "srt", "webvtt"])
def test_convert_concat_json(tmp_path: Path, dest_fmt):
    """
    End-to-end:
      1. Download 3 stubbed videos as JSON with --concat.
      2. Convert that concatenated JSON to *dest_fmt*.
    Regression: must not raise AttributeError ('SimpleNamespace' has no attr .text)
    and must create exactly one output file.
    """
    # Step-1: make a concatenated JSON file
    run_cli(
        tmp_path,
        "dummy",  # URL ignored by patched detect()
        "-f",
        "json",
        "-C",
        "--basename",
        "combo",
        "-n",
        "3",
    )
    combo = tmp_path / "combo.json"
    assert combo.exists()

    # Step-2: convert it
    run_cli(
        tmp_path,
        "--convert",
        str(combo),
        "-f",
        dest_fmt,
    )
    converted = combo.with_suffix(f".{ytb.EXT[dest_fmt]}")
    assert converted.exists(), "converter did not write output file"

    # Quick smoke-checks on the result
    out = converted.read_text()
    assert out.strip(), "converted file is empty"
    if dest_fmt in ("text", "pretty"):
        # concatenated -> plain text should contain at least one cue
        assert "Hello" in out or "world" in out
    if dest_fmt == "srt":
        assert re.match(r"^1\s*\n00:00:00", out.lstrip()), "SRT numbering missing"


# ────────────────────────── edge cases  ───────────────────────────────── #
def test_no_caption_flow(monkeypatch, tmp_path):
    """Patch API to raise NoTranscriptFound and ensure graceful summary."""

    class _NoneApi:
        def __init__(self, *a, **kw):
            pass

        def fetch(self, video_id, *_, **__):
            # Must instantiate with the video_id (mimics real library).
            raise ytb.NoTranscriptFound(video_id)

    monkeypatch.setattr(ytb.core, "YouTubeTranscriptApi", _NoneApi)
    monkeypatch.setattr(
        ytb,
        "scrapetube",
        SimpleNamespace(
            get_playlist=lambda *a, **k: [
                {"videoId": "abc", "title": {"runs": [{"text": "t"}]}}
            ]
        ),
    )
    monkeypatch.setattr(ytb, "detect", lambda _: ("playlist", "X"))
    run_cli(tmp_path, "x", "-f", "text", "-n", "1")
    # No output files should be created when a caption is not found
    assert not list(tmp_path.iterdir())


# ────────────────────────── header-stats sanity  ─────────────────────── #
@pytest.mark.usefixtures("patch_transcript", "patch_scrapetube", "patch_detect")
@pytest.mark.parametrize("fmt", ["srt", "webvtt", "text", "pretty"])
def test_header_stats_match(tmp_path: Path, fmt):
    run_cli(tmp_path, "dummy", "-f", fmt, "-n", "1")
    f = next(tmp_path.glob(f"*.{ytb.EXT[fmt]}"))
    txt = f.read_text()
    w0, l0, c0 = ytb._stats(txt)
    w1, l1, c1 = _extract_header_counts(txt)
    assert (w0, l0, c0) == (w1, l1, c1), f"{fmt} header mismatch"


# ────────────────────────── helpers ─────────────────────────────────────── #


# ---------------------------------------------------------------------------
# NEW: stats-off validation
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("patch_transcript", "patch_scrapetube", "patch_detect")
@pytest.mark.parametrize("fmt", ["srt", "webvtt", "text", "pretty"])
def test_no_stats_header_absent(tmp_path: Path, fmt):
    """--no-stats should omit the header in every non-JSON format."""
    run_cli(tmp_path, "dummy", "-f", fmt, "-n", "1", "--no-stats")
    f = next(tmp_path.glob(f"*.{ytb.EXT[fmt]}"))
    first = f.read_text().lstrip().splitlines()[0]
    assert not re.match(r"(?:NOTE|#)\s+stats:", first, re.I)


@pytest.mark.usefixtures("patch_transcript", "patch_scrapetube", "patch_detect")
def test_json_concat_no_stats_key(tmp_path: Path):
    """With --no-stats, concatenated JSON must NOT contain a top-level stats obj."""
    run_cli(
        tmp_path,
        "dummy",
        "-f",
        "json",
        "-C",
        "--basename",
        "combo",
        "-n",
        "3",
        "--no-stats",
    )
    payload = json.loads((tmp_path / "combo.json").read_text())
    # With --no-stats, the top-level "stats" object must *not* exist
    assert "stats" not in payload


# ---------------------------------------------------------------------------
# 1. URL detector matrix
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "url, kind, ident",
    [
        ("https://youtu.be/abcdefghijk", "video", "abcdefghijk"),
        (
            "https://www.youtube.com/watch?v=ID123456789",
            "video",
            "ID123456789",
        ),
        (
            "https://youtube.com/playlist?list=PLxyz",
            "playlist",
            "PLxyz",
        ),
        (
            "https://www.youtube.com/@SomeChannel/videos",
            "channel",
            "https://www.youtube.com/@SomeChannel/videos",
        ),
    ],
)
def test_detect_matrix(url: str, kind: str, ident: str):
    k, i = ytb.detect(url)
    assert (k, i) == (kind, ident)


# ---------------------------------------------------------------------------
# 2. single-video end-to-end, SRT format
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("patch_transcript")
def test_single_video_flow(tmp_path: Path, monkeypatch):
    """Run main() on a pure watch-URL → expect one SRT with a proper header."""
    # Force detect() to choose the "video" path
    monkeypatch.setattr(ytb, "detect", lambda _u: ("video", "vidX"))

    # Make video_iter return a single stub video
    monkeypatch.setattr(
        ytb,
        "video_iter",
        lambda *_a, **_k: [
            {
                "videoId": "vidX",
                "title": {"runs": [{"text": "Solo demo"}]},
            }
        ],
    )

    # Run CLI
    sys.argv[:] = [
        "yt_bulk_cc.py",
        "https://youtu.be/vidX",
        "-o",
        str(tmp_path),
        "-f",
        "srt",  # ← default is now JSON - request SRT explicitly
    ]
    ytb.asyncio.run(ytb.main())

    # Validate output
    out = next(tmp_path.glob("*.srt"))
    data = out.read_text()
    assert data.lstrip().startswith("NOTE stats:")
    # header figures must match whole file
    assert ytb._stats(data) == stats_line_tuple(data)


# ---------------------------------------------------------------------------
# 3. channel JSON download with --timestamps
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("patch_transcript")
def test_channel_json_with_timestamps(tmp_path: Path, monkeypatch):
    """Channel → JSON path with timestamps flag (formatter swap exercised)."""
    # Pretend detect() saw a channel URL
    chan_url = "https://www.youtube.com/@Chan/videos"
    monkeypatch.setattr(ytb, "detect", lambda _u: ("channel", chan_url))

    # Fake three videos from scrapetube.get_channel
    vids = [
        {
            "videoId": f"c{i}",
            "title": {"runs": [{"text": f"Chan video {i}"}]},
        }
        for i in range(3)
    ]
    monkeypatch.setattr(ytb.scrapetube, "get_channel", lambda *a, **k: vids)

    # CLI: json format, timestamps ON, limit 1
    sys.argv[:] = [
        "yt_bulk_cc.py",
        chan_url,
        "-f",
        "json",
        "-t",
        "-o",
        str(tmp_path),
        "-n",
        "1",
    ]
    ytb.asyncio.run(ytb.main())

    # Validate output JSON exists & minimal structure correct
    jfile = next(tmp_path.glob("*.json"))
    obj = ytb.json.loads(jfile.read_text())
    assert obj["video_id"] in {"c0", "c1", "c2"}
    assert len(obj["transcript"]) == 2


def test_split_without_concat_exits(tmp_path, patch_transcript, patch_scrapetube):
    sys.argv[:] = [
        "yt_bulk_cc.py",
        "dummy",
        "-f",
        "text",
        "--split",
        "10w",
        "-o",
        str(tmp_path),
    ]
    with pytest.raises(SystemExit):
        asyncio.run(ytb.main())


# ───────────────────────── concat ordering sanity ────────────────────── #
@pytest.mark.usefixtures("patch_transcript")
def test_concat_order(tmp_path: Path, monkeypatch):
    """
    Ensure transcripts are concatenated strictly in playlist order and
    roll over when the split limit would be exceeded.
    """
    vids = [f"v{i}" for i in range(5)]  # v0 … v4, in order

    # Patch scrapetube for this one test
    monkeypatch.setattr(ytb, "detect", lambda _u: ("playlist", "demo"))
    monkeypatch.setattr(
        ytb,
        "video_iter",
        lambda *_a, **_k: [
            {"videoId": vid, "title": {"runs": [{"text": vid}]}} for vid in vids
        ],
    )
    sys.argv[:] = [
        "yt_bulk_cc.py",
        "demo",
        "-o",
        str(tmp_path),
        "-f",
        "text",
        "-C",
        "--basename",
        "combined",
    ]
    ytb.asyncio.run(ytb.main())

    data = (tmp_path / "combined.txt").read_text()
    found = [line.split()[1] for line in data.splitlines() if line.startswith("──── ")]
    assert found == vids
