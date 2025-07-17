import json
import re
from pathlib import Path
import pytest
from yt_bulk_cc import yt_bulk_cc as ytb
from conftest import run_cli, strip_ansi, stats_lines


# S-01  +  S-02  (ordering  &  dynamic index width)
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("patch_transcript", "patch_scrapetube", "patch_detect")
def test_stats_block_order_and_index_width(tmp_path: Path, capsys):
    """The stats list must be char-descending and zero-padded to the max index."""
    run_cli(tmp_path, "dummy", "-f", "text", "-n", "5")  # no --concat
    out = strip_ansi(capsys.readouterr().out)
    lines = stats_lines(out)

    # ---- S-02  index padding ------------------------------------------------
    pad = len(str(len(lines))) or 1
    for idx, line in enumerate(lines, 1):
        assert re.match(rf"\s*{idx:0{pad}d}\.", line), f"bad index width: {line!r}"

    # ---- S-01  descending char-count order ----------------------------------
    char_counts = [
        int(re.search(r"(\d[\d,]*)\s*c\b", l).group(1).replace(",", "")) for l in lines
    ]
    assert char_counts == sorted(char_counts, reverse=True), "stats not descending"


# ---------------------------------------------------------------------------
# S-03   (--stats-top cap)     &     S-04  (--stats-top 0 → all)
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("patch_transcript", "patch_scrapetube", "patch_detect")
def test_stats_top_cap_and_all(tmp_path: Path, capsys):
    # cap = 3  → exactly 3 lines
    run_cli(tmp_path, "dummy", "-f", "json", "--stats-top", "3", "-n", "10")
    lines = stats_lines(strip_ansi(capsys.readouterr().out))
    assert len(lines) == 3, "stats-top 3 not honoured"

    # cap = 0  → show *all* files
    capsys.readouterr()  # clear buffer
    run_cli(tmp_path, "dummy", "-f", "json", "--stats-top", "0", "-n", "10")
    out = strip_ansi(capsys.readouterr().out)
    lines = stats_lines(out)
    files = list(tmp_path.glob("*.json"))
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
    txt = jfile.read_text()
    obj = json.loads(txt)

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
        l
        for l in strip_ansi(capsys.readouterr().out).splitlines()
        if "File statistics" in l
    )
    assert hdr_line.strip() == "File statistics (top 1):", "header wording incorrect"
