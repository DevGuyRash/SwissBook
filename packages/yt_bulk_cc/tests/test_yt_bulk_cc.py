"""
End-to-end and unit-level tests for yt_bulk_cc.py.

A strict no-network policy is enforced:  YouTubeTranscriptApi.get_transcript,
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

import pytest
import re

# ---------------------------------------------------------------------------
# ensure scripts/ is importable
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "yt_bulk_cc"))

import yt_bulk_cc as ytb  # noqa: E402  (import after path tweak)

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
    """Stub out YouTubeTranscriptApi.get_transcript."""
    class _FakeApi:
        @staticmethod
        def get_transcript(*_, **__):
            return fake_cues

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
def test_json_concat_contains_meta_and_stats(tmp_path: Path):
    run_cli(
        tmp_path,
        "dummy",
        "-f",
        "json",
        "-C",
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
        "-C", "combo",
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
        @staticmethod
        def get_transcript(video_id, *_, **__):
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
    run_cli(tmp_path, "dummy", "-f", "json", "-C", "combo", "-n", "3")
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
    run_cli(tmp_path, "dummy", "-f", "json", "-C", "combo", "-n", "2")
    combo = tmp_path / "combo.json"
    run_cli(tmp_path, "--convert", str(combo), "-f", dest_fmt)
    out = combo.with_suffix(f".{ytb.EXT[dest_fmt]}")
    head = out.read_text().lstrip().splitlines()[0]
    assert re.match(r"(?:NOTE|#)\s+stats:", head)

def test_convert_video_separators(tmp_path, patch_transcript, patch_scrapetube,
                                  patch_detect):
    run_cli(tmp_path, "dummy", "-f", "json", "-C", "combo", "-n", "2")
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
    run_cli(tmp_path, "dummy", "-f", "json", "-C", "combo", "-n", "3")
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

    def _fake_get_transcript(*_a, **_kw):
        calls["n"] += 1
        if calls["n"] < 3:  # first two attempts → fail
            raise ytb.TooManyRequests("slow down")
        # third attempt → return minimal cue
        return [{"start": 0.0, "duration": 1.0, "text": "OK"}]

    monkeypatch.setattr(
        ytb,
        "YouTubeTranscriptApi",
        type("FakeApi", (), {"get_transcript": staticmethod(_fake_get_transcript)}),
    )

    # -v → console log level INFO so the retry line reaches stdout
    run_cli(tmp_path, "dummy", "-f", "text", "-n", "1", "-v")

    # a file should have been produced after retries
    assert list(tmp_path.glob("*.txt")), "no output after retries"

    # We should have attempted exactly three calls (two 429s + final success)
    assert calls["n"] == 3, "back-off logic did not retry the expected number of times"


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
