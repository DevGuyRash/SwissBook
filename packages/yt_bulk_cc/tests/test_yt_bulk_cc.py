"""
End-to-end and unit-level tests for yt_bulk_cc.py.

A strict no-network policy is enforced:  YouTubeTranscriptApi.fetch,
scrapetube.get_playlist / get_channel, and the detect() helper are patched with
in-memory stubs so the suite can run anywhere (CI, air-gapped laptop, etc.).

pytest -q tests/test_yt_bulk_cc.py
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# ensure scripts/ is importable
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from yt_bulk_cc import yt_bulk_cc as ytb
from yt_bulk_cc.errors import IpBlocked, TooManyRequests, NoTranscriptFound
from youtube_transcript_api.proxies import GenericProxyConfig, WebshareProxyConfig

# ────────────────────────── shared fixtures ────────────────────────────── #
@pytest.fixture(autouse=True)
def restore_sys_argv(monkeypatch):
    """Each test manipulates sys.argv; restore afterwards."""
    original = sys.argv.copy()
    yield
    sys.argv[:] = original


@pytest.fixture
def fake_cues():
    """Return a list of dictionaries mimicking the real API response."""
    return [
        {"start": 0.0, "duration": 1.0, "text": "Hello"},
        {"start": 1.0, "duration": 1.5, "text": "world"},
    ]


@pytest.fixture
def patch_transcript(monkeypatch, fake_cues):
    """Stub out YouTubeTranscriptApi.fetch."""
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

    monkeypatch.setattr(ytb, "YouTubeTranscriptApi", _FakeApi)
    yield


@pytest.fixture
def patch_scrapetube(monkeypatch):
    """Patch scrapetube helpers to return a deterministic playlist of 3 vids."""
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
    """Force detect() to think every URL is a playlist with id 'PLfake'."""
    monkeypatch.setattr(ytb, "detect", lambda url: ("playlist", "PLfake"))
    yield


# ---------------------------------------------------------------------------
# helper to invoke main() with patched argv - catch SystemExit cleanly
def run_cli(tmp_path: Path, *argv: str) -> None:
    sys.argv[:] = ["yt_bulk_cc.py", *argv]
    # patch output folder to tmp_path if not explicitly passed
    if "-o" not in argv and "--folder" not in argv:
        sys.argv += ["-o", str(tmp_path)]
    try:
        asyncio.run(ytb.main())
    except SystemExit as e:  # main() calls sys.exit on some paths
        if e.code not in (0, None):
            raise


# ────────────────────────── new helper  ──────────────────────────────── #
def _extract_header_counts(txt: str) -> tuple[int,int,int]:
    m = re.search(r"stats:\s+([\d,]+)\s+words.+?([\d,]+)\s+lines.+?([\d,]+)\s+chars",
                  txt, re.I|re.S)
    if not m:
        raise AssertionError("stats header missing")
    w,l,c = (int(x.replace(",","")) for x in m.groups())
    return w,l,c


# ────────────────────────── unit tests  ─────────────────────────────────── #
def test_slug_strips_bad_chars():
    assert ytb.slug("A/B<C>D|E?F", 20) == "A_B_C_D_E_F"


def test_stats_helper():
    txt = "one two\nthree"
    w, l, c = ytb._stats(txt)
    # 1 newline → wc -l semantics
    assert (w, l, c) == (3, 1, len(txt))

# new: file with **no** trailing newline
def test_stats_no_final_newline():
    txt = "hello world"
    assert ytb._stats(txt) == (2, 0, 11)


# ────────────────────────── CLI / end-to-end  ─────────────────────────── #
@pytest.mark.usefixtures("patch_transcript", "patch_scrapetube", "patch_detect")
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
        "dummy",                    # URL ignored by detect patch
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
        "dummy",                # URL ignored by patched detect()
        "-f", "json",
        "-C", "--basename", "combo",
        "-n", "3",
    )
    combo = tmp_path / "combo.json"
    assert combo.exists()

    # Step-2: convert it
    run_cli(
        tmp_path,
        "--convert", str(combo),
        "-f", dest_fmt,
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

    monkeypatch.setattr(ytb, "YouTubeTranscriptApi", _NoneApi)
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
@pytest.mark.parametrize("fmt", ["srt","webvtt","text","pretty"])
def test_header_stats_match(tmp_path: Path, fmt):
    run_cli(tmp_path, "dummy", "-f", fmt, "-n", "1")
    f = next(tmp_path.glob(f"*.{ytb.EXT[fmt]}"))
    txt   = f.read_text()
    w0,l0,c0 = ytb._stats(txt)
    w1,l1,c1 = _extract_header_counts(txt)
    assert (w0,l0,c0) == (w1,l1,c1), f"{fmt} header mismatch"

# ────────────────────────── helpers ─────────────────────────────────────── #

def _stats_line_tuple(txt: str) -> tuple[int, int, int]:
    """
    Extract the `(words, lines, chars)` triple from NOTE/# header.

    Raises AssertionError if the header is missing.
    """
    m = re.search(
        r"stats:\s+([\d,]+)\s+words.+?([\d,]+)\s+lines.+?([\d,]+)\s+chars",
        txt,
        re.I | re.S,
    )
    if not m:
        raise AssertionError("stats header missing")
    return tuple(int(x.replace(",", "")) for x in m.groups())


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
        "srt",                       # ← default is now JSON - request SRT explicitly
    ]
    ytb.asyncio.run(ytb.main())

    # Validate output
    out = next(tmp_path.glob("*.srt"))
    data = out.read_text()
    assert data.lstrip().startswith("NOTE stats:")
    # header figures must match whole file
    assert ytb._stats(data) == _stats_line_tuple(data)


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
    sys.argv[:] = ["yt_bulk_cc.py", "dummy", "-f", "text", "--split", "10w", "-o", str(tmp_path)]
    with pytest.raises(SystemExit):
        asyncio.run(ytb.main())

# ───────────────────────── concat ordering sanity ────────────────────── #
@pytest.mark.usefixtures("patch_transcript")
def test_concat_order(tmp_path: Path, monkeypatch):
    """
    Ensure transcripts are concatenated strictly in playlist order and
    roll over when the split limit would be exceeded.
    """
    vids = [f"v{i}" for i in range(5)]                     # v0 … v4, in order

    # Patch scrapetube for this one test
    monkeypatch.setattr(
        ytb.scrapetube,
        "get_playlist",
        lambda *_a, **_k: [
            {"videoId": v, "title": {"runs": [{"text": v}]}} for v in vids
        ],
    )

    # Realistic playlist URL → no need for patch_detect
    run_cli(
        tmp_path,
        "https://youtube.com/playlist?list=PLx",
        "-f",
        "text",
        "-C",
        "--basename",
        "bundle",
        "--split",
        "30w",          # tiny threshold → multiple files for 5 videos
    )

    # ----- verify ordering across *and* within files -----
    seen = []
    for p in sorted(tmp_path.glob("bundle*.txt")):          # bundle_00001.txt …
        data = p.read_text()
        for v in vids:
            if f"──── {v} " in data:
                seen.append(v)

    assert seen == vids, f"order mismatch: {seen} vs {vids}"

# ───────────────────────── file stats test ────────────────────── #
@pytest.mark.usefixtures("patch_transcript", "patch_scrapetube", "patch_detect")
def test_json_stats_are_accurate(tmp_path: Path):
    run_cli(tmp_path, "dummy", "-f", "json", "-C", "--basename", "combo", "-n", "3")
    jfile = tmp_path / "combo.json"
    data  = json.loads(jfile.read_text())
    w,l,c = ytb._stats(jfile.read_text())
    assert (w,l,c) == (data["stats"]["words"],
                       data["stats"]["lines"],
                       data["stats"]["chars"]), "JSON stats header mismatch"

# ────────────────────────── NEW: split-cap sanity  ────────────────────────── #
@pytest.mark.usefixtures("patch_transcript", "patch_scrapetube", "patch_detect")
@pytest.mark.parametrize("fmt", ["srt", "webvtt", "text", "pretty"])
@pytest.mark.parametrize(
    "unit,limit", [("w", 60), ("l", 40), ("c", 600)]
)
def test_split_limit_respected(tmp_path: Path, fmt: str, unit: str, limit: int):
    """
    End-to-end: download 3 stub videos, concat with a *tiny* split threshold
    and verify every emitted file honours that cap **including** the header.
    """
    run_cli(
        tmp_path,
        "dummy",
        "-f",
        fmt,
        "-C",
        "--basename",
        "bundle",
        "--split",
        f"{limit}{unit}",
        "-n",
        "3",
    )

    for f in tmp_path.glob(f"bundle_*.{ytb.EXT[fmt]}"):
        w, l, c = ytb._stats(f.read_text())
        if unit == "w":
            assert w <= limit, f"{f} exceeds word cap"
        elif unit == "l":
            assert l <= limit, f"{f} exceeds line cap"
        else:
            assert c <= limit, f"{f} exceeds char cap"


def test_runlog_summary_is_last(tmp_path, patch_transcript, patch_scrapetube,
                                patch_detect):
    """Summary must be the final non-blank line in the run-log."""
    lf = tmp_path / "run.log"
    run_cli(tmp_path, "dummy", "-f", "text", "-n", "1",
            "-L", str(lf))          # force explicit log path
    lines = [l.rstrip() for l in lf.read_text().splitlines() if l.strip()]
    assert lines[-1].startswith("Summary:")

def test_stats_block_no_duplicates(tmp_path, patch_transcript,
                                   patch_scrapetube, patch_detect, capsys):
    run_cli(tmp_path, "dummy", "-f", "json", "-n", "3")
    # capture the console output from the helper
    out = capsys.readouterr().out
    assert out.count("File statistics:") == 1

@pytest.mark.parametrize("dest_fmt", ["srt", "text"])
def test_convert_includes_headers(tmp_path, patch_transcript, patch_scrapetube,
                                  patch_detect, dest_fmt):
    run_cli(tmp_path, "dummy", "-f", "json", "-C", "--basename", "combo", "-n", "2")
    combo = tmp_path / "combo.json"
    run_cli(tmp_path, "--convert", str(combo), "-f", dest_fmt)
    out = combo.with_suffix(f".{ytb.EXT[dest_fmt]}")
    head = out.read_text().lstrip().splitlines()[0]
    assert re.match(r"(?:NOTE|#)\s+stats:", head)

def test_convert_video_separators(tmp_path, patch_transcript, patch_scrapetube,
                                  patch_detect):
    run_cli(tmp_path, "dummy", "-f", "json", "-C", "--basename", "combo", "-n", "2")
    combo = tmp_path / "combo.json"
    run_cli(tmp_path, "--convert", str(combo), "-f", "text")
    out = combo.with_suffix(".txt").read_text()
    assert out.count("────") == 2      # one per video

# ────────────────────────── NEW BEHAVIOUR TESTS ──────────────────────────
# These tests exercise the S-, J-, SP- and UI-series guarantees that were
# recently fixed but previously uncovered.  All rely on the run_cli() helper
# and the patched network stubs already defined in this suite.

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
_ANSI_RE = re.compile(r"\x1B\[[0-9;]*[A-Za-z]")

def _strip_ansi(txt: str) -> str:
    """Remove colour escape sequences - keeps test parsing simple."""
    return _ANSI_RE.sub("", txt)


def _stats_lines(block: str) -> list[str]:
    """
    Return the non-blank *lines* in the "File statistics" section.

    `block` must already be ANSI-stripped.
    """
    m = re.search(r"File statistics[^\n]*\n(.*?)(?:\n\s*$|\n\n)", block, re.S)
    if not m:
        raise AssertionError("File statistics block not found")
    return [l for l in m.group(1).splitlines() if l.strip()]


# ---------------------------------------------------------------------------
# S-01  +  S-02  (ordering  &  dynamic index width)
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("patch_transcript", "patch_scrapetube", "patch_detect")
def test_stats_block_order_and_index_width(tmp_path: Path, capsys):
    """The stats list must be char-descending and zero-padded to the max index."""
    run_cli(tmp_path, "dummy", "-f", "text", "-n", "5")          # no --concat
    out   = _strip_ansi(capsys.readouterr().out)
    lines = _stats_lines(out)

    # ---- S-02  index padding ------------------------------------------------
    pad = len(str(len(lines))) or 1
    for idx, line in enumerate(lines, 1):
        assert re.match(fr"\s*{idx:0{pad}d}\.", line), f"bad index width: {line!r}"

    # ---- S-01  descending char-count order ----------------------------------
    char_counts = [
        int(re.search(r"(\d[\d,]*)\s*c\b", l).group(1).replace(",", ""))
        for l in lines
    ]
    assert char_counts == sorted(char_counts, reverse=True), "stats not descending"


# ---------------------------------------------------------------------------
# S-03   (--stats-top cap)     &     S-04  (--stats-top 0 → all)
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("patch_transcript", "patch_scrapetube", "patch_detect")
def test_stats_top_cap_and_all(tmp_path: Path, capsys):
    # cap = 3  → exactly 3 lines
    run_cli(tmp_path, "dummy", "-f", "json", "--stats-top", "3", "-n", "10")
    lines = _stats_lines(_strip_ansi(capsys.readouterr().out))
    assert len(lines) == 3, "stats-top 3 not honoured"

    # cap = 0  → show *all* files
    capsys.readouterr()                  # clear buffer
    run_cli(tmp_path, "dummy", "-f", "json", "--stats-top", "0", "-n", "10")
    out    = _strip_ansi(capsys.readouterr().out)
    lines  = _stats_lines(out)
    files  = list(tmp_path.glob("*.json"))
    assert len(lines) == len(files), "stats-top 0 did not show all files"


# ---------------------------------------------------------------------------
# J-01  (per-item stats in concatenated JSON)
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("patch_transcript", "patch_scrapetube", "patch_detect")
def test_item_stats_inside_concat_json(tmp_path: Path):
    run_cli(tmp_path, "dummy", "-f", "json", "-C", "--basename", "combo", "-n", "3")
    data = json.loads((tmp_path / "combo.json").read_text())

    for item in data["items"]:
        assert "stats" in item, "item missing stats block"
        # reproduce the representation used when stats were computed (indent=2 + \n)
        txt = json.dumps(item, indent=2, ensure_ascii=False)
        if not txt.endswith("\n"):
            txt += "\n"
        w, l, c = ytb._stats(txt)
        assert (w, l, c) == (
            item["stats"]["words"],
            item["stats"]["lines"],
            item["stats"]["chars"],
        ), "per-item stats mismatch"


# ---------------------------------------------------------------------------
# J-02  (stats in single-file JSON)  +  J-03  (trailing newline)
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("patch_transcript", "patch_scrapetube", "patch_detect")
def test_single_json_stats_and_trailing_newline(tmp_path: Path):
    run_cli(tmp_path, "dummy", "-f", "json", "-n", "1")
    jfile = next(tmp_path.glob("*.json"))
    txt   = jfile.read_text()
    obj   = json.loads(txt)

    # trailing newline (J-03)
    assert txt.endswith("\n"), "JSON does not end with newline"

    # stats match exact file bytes (J-02)
    w, l, c = ytb._stats(txt)
    assert (w, l, c) == (
        obj["stats"]["words"],
        obj["stats"]["lines"],
        obj["stats"]["chars"],
    ), "top-level stats mismatch"


# ---------------------------------------------------------------------------
# SP-01  (split limit 5 000 chars honoured for concatenated JSON)
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("patch_transcript", "patch_scrapetube", "patch_detect")
def test_json_split_char_limit_respected(tmp_path: Path):
    run_cli(
        tmp_path,
        "dummy",
        "-f",
        "json",
        "-C",
        "--basename",
        "combo",
        "--split",
        "5000c",
        "-n",
        "10",
    )
    for part in tmp_path.glob("combo_*.json"):
        _, _, c = ytb._stats(part.read_text())
        assert c <= 5000, f"{part.name} has {c} chars - exceeds 5 000 cap"


# ---------------------------------------------------------------------------
# UI-01  (header wording when only a single entry is shown)
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("patch_transcript", "patch_scrapetube", "patch_detect")
def test_stats_header_singular_plural(tmp_path: Path, capsys):
    run_cli(tmp_path, "dummy", "-f", "text", "--stats-top", "1", "-n", "1")
    hdr_line = next(
        l for l in _strip_ansi(capsys.readouterr().out).splitlines()
        if "File statistics" in l
    )
    assert hdr_line.strip() == "File statistics (top 1):", "header wording incorrect"


# ────────────────── Hardening / resilience tests ──────────────────────
"""
Hardening / resilience tests that go beyond the spec-checklist:

* retry/back-off logic for TooManyRequests
* Windows MAX_PATH shortening safeguard
"""

# ──────────────────────────────────────────────────────────────────────────
# 1. Retry logic - TooManyRequests raises twice, then succeeds
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("patch_scrapetube", "patch_detect")
def test_retry_too_many_requests(monkeypatch, tmp_path: Path, capsys):
    """_grab() must back-off and still succeed after transient 429 errors."""

    calls = {"n": 0}

    def _fake_fetch(*_a, **_kw):
        calls["n"] += 1
        if calls["n"] < 3:  # first two attempts → fail
            raise ytb.TooManyRequests("slow down")
        # third attempt → return minimal cue
        class _FT:
            def to_raw_data(self):
                return [{"start": 0.0, "duration": 1.0, "text": "OK"}]

        return _FT()

    class _FakeApi:
        def __init__(self, *a, **kw):
            pass

        def fetch(self, *a, **kw):
            return _fake_fetch(*a, **kw)

    monkeypatch.setattr(ytb, "YouTubeTranscriptApi", _FakeApi)

    # -v → console log level INFO so the retry line reaches stdout
    run_cli(tmp_path, "dummy", "-f", "text", "-n", "1", "-v")

    # a file should have been produced after retries
    assert list(tmp_path.glob("*.txt")), "no output after retries"

    # We should have attempted exactly three calls (two 429s + final success)
    assert calls["n"] == 3, "back-off logic did not retry the expected number of times"


@pytest.mark.usefixtures("patch_scrapetube", "patch_detect")
def test_retry_ip_blocked(monkeypatch, tmp_path: Path, capsys):
    """_grab() must back-off and still succeed after transient IpBlocked errors."""

    calls = {"n": 0}

    def _fake_fetch(*_a, **_kw):
        calls["n"] += 1
        if calls["n"] < 3:  # first two attempts → fail
            raise ytb.IpBlocked("IP blocked")
        # third attempt → return minimal cue
        class _FT:
            def to_raw_data(self):
                return [{"start": 0.0, "duration": 1.0, "text": "OK"}]

        return _FT()

    class _FakeApi:
        def __init__(self, *a, **kw):
            pass

        def fetch(self, *a, **kw):
            return _fake_fetch(*a, **kw)

    monkeypatch.setattr(ytb, "YouTubeTranscriptApi", _FakeApi)

    # -v → console log level INFO so the retry line reaches stdout
    run_cli(tmp_path, "dummy", "-f", "text", "-n", "1", "-v")

    # a file should have been produced after retries
    assert list(tmp_path.glob("*.txt")), "no output after retries"

    # We should have attempted exactly three calls (two IpBlocked + final success)
    assert calls["n"] == 3, "back-off logic did not retry the expected number of times"


@pytest.mark.usefixtures("patch_scrapetube", "patch_detect")
def test_check_ip_bails(monkeypatch, tmp_path: Path, capsys):
    monkeypatch.setattr(
        "yt_bulk_cc.core.probe_video", lambda *a, **k: (False, {"p"})
    )
    with pytest.raises(SystemExit):
        run_cli(tmp_path, "dummy", "-f", "text", "-n", "2", "--check-ip")
    out = _strip_ansi(capsys.readouterr().out)
    assert "Summary:" in out
    assert "failed 2" in out
    assert "proxies banned 1" in out


@pytest.mark.usefixtures("patch_scrapetube", "patch_detect")
def test_check_ip_ok(monkeypatch, tmp_path: Path, patch_transcript):
    called = {"n": 0}

    def probe(*a, **k):
        called["n"] += 1
        return True, set()

    monkeypatch.setattr("yt_bulk_cc.core.probe_video", probe)
    run_cli(tmp_path, "dummy", "-f", "text", "-n", "1", "--check-ip")
    assert called["n"] == 1


# ──────────────────────────────────────────────────────────────────────────
# 2. Windows path-length safeguard
# ──────────────────────────────────────────────────────────────────────────


def test_windows_path_shortening(monkeypatch, tmp_path: Path):
    """Unit-test the helper directly; no need to touch pathlib.WindowsPath."""

    long_title = "L" * 500
    original   = tmp_path / f"[vid] {long_title}.txt"

    # Make the helper think it's running on Windows **after** the Path exists
    monkeypatch.setattr(ytb.os, "name", "nt", raising=False)

    shortened = ytb._shorten_for_windows(original)
    assert len(str(shortened)) <= 260, "path exceeds Windows MAX_PATH"


# ---------------------------------------------------------------------------
# 3. Ensure grab() uses a browser-like User-Agent
# ---------------------------------------------------------------------------

def test_default_user_agent(monkeypatch, tmp_path: Path):
    """grab() should use a sensible User-Agent header by default."""

    monkeypatch.setattr(ytb, "detect", lambda _u: ("video", "vidX"))
    monkeypatch.setattr(ytb, "_pick_ua", lambda *_a, **_k: "UA/123")

    captured = {}

    class _FakeApi:
        def __init__(self, *_, **kw):
            captured["ua"] = kw.get("http_client").headers.get("User-Agent")

        def fetch(self, *a, **kw):
            class _FT:
                def to_raw_data(self):
                    return [{"start": 0.0, "duration": 1.0, "text": "hi"}]

            return _FT()

    monkeypatch.setattr(ytb, "YouTubeTranscriptApi", _FakeApi)

    run_cli(tmp_path, "https://youtu.be/vidX")

    assert captured["ua"] == "UA/123"


def test_generic_proxy_flags(monkeypatch, tmp_path: Path):
    """CLI should pass GenericProxyConfig with provided proxy URLs."""

    monkeypatch.setattr(ytb, "detect", lambda _u: ("playlist", "X"))
    monkeypatch.setattr(
        ytb.scrapetube,
        "get_playlist",
        lambda *_a, **_k: [{"videoId": "x", "title": {"runs": [{"text": "d"}]}}],
    )

    captured = {}

    class _FakeApi:
        def __init__(self, *_, **kw):
            captured["cfg"] = kw.get("proxy_config")

        def fetch(self, *a, **kw):
            class _FT:
                def to_raw_data(self):
                    return []

            return _FT()

    monkeypatch.setattr(ytb, "YouTubeTranscriptApi", _FakeApi)

    run_cli(
        tmp_path,
        "dummy",
        "-p",
        "http://u:p@h:1",
        "-n",
        "1",
    )

    cfg = captured["cfg"]
    assert isinstance(cfg, ytb.GenericProxyConfig)
    assert cfg.http_url == "http://u:p@h:1"
    assert cfg.https_url == "https://u:p@h:1"


def test_webshare_proxy(monkeypatch, tmp_path: Path):
    """CLI should use WebshareProxyConfig when credentials provided."""

    monkeypatch.setattr(ytb, "detect", lambda _u: ("playlist", "X"))
    monkeypatch.setattr(
        ytb.scrapetube,
        "get_playlist",
        lambda *_a, **_k: [{"videoId": "x", "title": {"runs": [{"text": "d"}]}}],
    )

    captured = {}

    class _FakeApi:
        def __init__(self, *_, **kw):
            captured["cfg"] = kw.get("proxy_config")

        def fetch(self, *a, **kw):
            class _FT:
                def to_raw_data(self):
                    return []

            return _FT()

    monkeypatch.setattr(ytb, "YouTubeTranscriptApi", _FakeApi)

    run_cli(
        tmp_path,
        "dummy",
        "-p",
        "ws://user:pass",
        "-n",
        "1",
    )

    cfg = captured["cfg"]
    assert isinstance(cfg, ytb.WebshareProxyConfig)
    assert cfg.proxy_username == "user"
    assert cfg.proxy_password == "pass"


def test_proxy_pool(monkeypatch, tmp_path: Path):
    """-p should populate proxy_pool with credentials intact."""

    monkeypatch.setattr(ytb, "detect", lambda _u: ("playlist", "X"))
    monkeypatch.setattr(
        ytb.scrapetube,
        "get_playlist",
        lambda *_a, **_k: [{"videoId": "x", "title": {"runs": [{"text": "d"}]}}],
    )

    captured = {}

    async def _fake_grab(*_a, **kw):
        captured["pool"] = kw.get("proxy_pool")
        captured["cfg"] = kw.get("proxy_cfg")
        return ("ok", "x", "t")

    monkeypatch.setattr(ytb, "grab", _fake_grab)

    run_cli(
        tmp_path,
        "dummy",
        "-p",
        "http://u:p@h:1,https://u2:p2@h2:2",
        "-n",
        "1",
    )

    assert captured["pool"] == ["http://u:p@h:1", "https://u2:p2@h2:2"]


def test_pool_multiple_webshare(monkeypatch, tmp_path: Path):
    """Multiple ws:// credentials should pass through to grab()."""

    monkeypatch.setattr(ytb, "detect", lambda _u: ("playlist", "X"))
    monkeypatch.setattr(
        ytb.scrapetube,
        "get_playlist",
        lambda *_a, **_k: [{"videoId": "x", "title": {"runs": [{"text": "d"}]}}],
    )

    captured = {}

    async def _fake_grab(*_a, **kw):
        captured["pool"] = kw.get("proxy_pool")
        return ("ok", "x", "t")

    monkeypatch.setattr(ytb, "grab", _fake_grab)

    run_cli(
        tmp_path,
        "dummy",
        "-p",
        "ws://u:p,ws://u2:p2",
        "-n",
        "1",
    )

    assert captured["pool"] == ["ws://u:p", "ws://u2:p2"]


def test_make_proxy_ws():
    """_make_proxy should return WebshareProxyConfig for ws:// URLs."""

    from yt_bulk_cc.core import _make_proxy as core_make
    from yt_bulk_cc.yt_bulk_cc import _make_proxy as cli_make

    cfg1 = core_make("ws://aa:bb")
    cfg2 = cli_make("ws://aa:bb")

    for cfg in (cfg1, cfg2):
        assert isinstance(cfg, ytb.WebshareProxyConfig)
        assert cfg.proxy_username == "aa"
        assert cfg.proxy_password == "bb"

@pytest.mark.usefixtures("patch_scrapetube", "patch_detect")
def test_proxy_file_rotation(monkeypatch, tmp_path: Path, capsys):
    proxy_file = tmp_path / "proxies.txt"
    proxy_file.write_text("http://f1\nhttp://f2\n", encoding="utf-8")

    used = []
    calls = {"n": 0}

    class _FakeApi:
        def __init__(self, *a, **kw):
            cfg = kw.get("proxy_config")
            used.append(getattr(cfg, "http_url", None))

        def fetch(self, *a, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                raise ytb.IpBlocked("blocked")

            class _FT:
                def to_raw_data(self):
                    return [{"start": 0.0, "duration": 1.0, "text": "ok"}]

            return _FT()

    monkeypatch.setattr(ytb, "YouTubeTranscriptApi", _FakeApi)

    captured = {}
    orig_grab = ytb.grab

    async def _wrap(*args, **kw):
        captured["pool"] = kw.get("proxy_pool")
        return await orig_grab(*args, **kw)

    monkeypatch.setattr(ytb, "grab", _wrap)

    async def _no_sleep(*a, **k):
        return None

    monkeypatch.setattr(ytb.asyncio, "sleep", _no_sleep)

    run_cli(
        tmp_path,
        "dummy",
        "-p",
        "http://cli",
        "--proxy-file",
        str(proxy_file),
        "-f",
        "text",
        "-n",
        "1",
        "-v",
        "-s",
        "0",
    )

    assert captured["pool"] == ["http://cli", "http://f1", "http://f2"]
    assert used[:2] == ["http://cli", "http://f1"]
    out = _strip_ansi(capsys.readouterr().out)
    assert "proxies banned 1" in out


@pytest.mark.usefixtures("patch_scrapetube", "patch_detect")
def test_public_proxy(monkeypatch, tmp_path: Path):
    captured: dict[str, Any] = {}

    class _PI:
        def __init__(self, *a, **k):
            _PI.called = True
            captured.update(k)
            self.proxies = [SimpleNamespace(as_string=lambda: "http://pub:1")]

    monkeypatch.setattr(ytb, "ProxyInterface", _PI)
    monkeypatch.setattr(ytb, "choice", lambda seq: seq[0])

    async def _fake_grab(*_a, **kw):
        captured["pool"] = kw.get("proxy_pool")
        return ("ok", "x", "t")

    monkeypatch.setattr(ytb, "grab", _fake_grab)

    _PI.called = False
    run_cli(tmp_path, "dummy", "--public-proxy", "3", "-n", "1")

    assert _PI.called
    assert captured["maxProxies"] == 3
    assert captured["protocol"] == "http"


@pytest.mark.usefixtures("patch_scrapetube", "patch_detect")
def test_public_proxy_with_cli(monkeypatch, tmp_path: Path):
    captured = {}

    class _PI:
        def __init__(self, *a, **k):
            _PI.called = True
            self.proxies = [SimpleNamespace(as_string=lambda: "http://pub:1")]

    monkeypatch.setattr(ytb, "ProxyInterface", _PI)
    monkeypatch.setattr(ytb, "choice", lambda seq: seq[0])

    async def _fake_grab(*_a, **kw):
        captured["pool"] = kw.get("proxy_pool")
        return ("ok", "x", "t")

    monkeypatch.setattr(ytb, "grab", _fake_grab)

    _PI.called = False
    run_cli(tmp_path, "dummy", "-p", "http://cli", "--public-proxy", "-n", "1")

    assert _PI.called
    assert captured["pool"] == ["http://cli", "http://pub:1"]


@pytest.mark.usefixtures("patch_scrapetube", "patch_detect")
def test_public_proxy_https(monkeypatch, tmp_path: Path):
    called: dict[str, Any] = {}

    class _PI:
        def __init__(self, *a, **k):
            called.update(k)
            self.proxies = [SimpleNamespace(as_string=lambda: "https://pub:1")]

    monkeypatch.setattr(ytb, "ProxyInterface", _PI)

    async def _fake_grab(*_a, **kw):
        return ("ok", "x", "t")

    monkeypatch.setattr(ytb, "grab", _fake_grab)

    run_cli(
        tmp_path,
        "dummy",
        "--public-proxy",
        "2",
        "--public-proxy-type",
        "https",
        "-n",
        "1",
    )

    assert called["protocol"] == "https"
    assert called["maxProxies"] == 2


@pytest.mark.usefixtures("patch_scrapetube", "patch_detect")
def test_public_proxy_socks(monkeypatch, tmp_path: Path):
    called = {}

    class FakeResponse:
        status_code = 200
        text = "1.1.1.1:1080\n2.2.2.2:1080"

        def raise_for_status(self):
            pass

    monkeypatch.setattr(ytb.requests, "get", lambda *a, **k: FakeResponse())

    async def _fake_grab(*_a, **kw):
        called["pool"] = kw.get("proxy_pool")
        called["cfg"] = kw.get("proxy_cfg")
        return ("ok", "x", "t")

    monkeypatch.setattr(ytb, "grab", _fake_grab)

    run_cli(
        tmp_path,
        "dummy",
        "--public-proxy",
        "1",
        "--public-proxy-type",
        "socks",
        "-n",
        "1",
    )

    cfg = called["cfg"]
    assert isinstance(cfg, ytb.GenericProxyConfig)
    assert cfg.http_url == "socks5://1.1.1.1:1080"


@pytest.mark.usefixtures("patch_scrapetube", "patch_detect")
def test_public_proxy_no_swiftshadow(monkeypatch, tmp_path: Path):
    class FakeResp:
        status_code = 200
        text = "1.2.3.4:1080"

        def raise_for_status(self):
            pass

    monkeypatch.setattr(ytb, "ProxyInterface", None)
    monkeypatch.setattr(ytb.requests, "get", lambda *a, **k: FakeResp())

    captured = {}

    async def _fake_grab(*_a, **kw):
        captured["cfg"] = kw.get("proxy_cfg")
        return ("ok", "x", "t")

    monkeypatch.setattr(ytb, "grab", _fake_grab)

    run_cli(tmp_path, "dummy", "--public-proxy", "1", "-n", "1")

    cfg = captured["cfg"]
    assert isinstance(cfg, ytb.GenericProxyConfig)
    assert cfg.http_url.startswith("socks5://")
