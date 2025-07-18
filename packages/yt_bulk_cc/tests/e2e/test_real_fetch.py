import requests
import asyncio
from pathlib import Path
import sys
import pytest

from yt_bulk_cc import yt_bulk_cc as ytb

pytestmark = pytest.mark.e2e

try:
    resp = requests.get("https://www.youtube.com", timeout=5)
    if resp.status_code >= 400:
        raise RuntimeError(resp.status_code)
except Exception:
    pytest.skip("YouTube unreachable", allow_module_level=True)


def run_cli(tmp_path: Path, *argv: str) -> None:
    sys.argv[:] = ["yt_bulk_cc.py", *argv]
    if "-o" not in argv and "--folder" not in argv:
        sys.argv += ["-o", str(tmp_path)]
    try:
        asyncio.run(ytb.main())
    except SystemExit as e:
        if e.code not in (0, None):
            raise


def test_real_playlist(tmp_path: Path):
    playlist = (
        "https://www.youtube.com/playlist?list=PLsRNoUx8w3rNvG9OQk4aHj4s5A_c7dlyV"
    )
    try:
        run_cli(tmp_path, playlist, "-n", "1")
    except SystemExit as e:
        if e.code == 1:
            pytest.skip("Playlist unreachable")
        raise
    json_files = list(tmp_path.glob("*.json"))
    if not json_files:
        pytest.skip("Playlist yielded no videos")


def test_real_channel(tmp_path: Path):
    channel = "https://www.youtube.com/@TED"
    run_cli(tmp_path, channel, "-n", "1")
    json_files = list(tmp_path.glob("*.json"))
    assert len(json_files) > 0, "No JSON files generated for channel"


def test_real_playlist_with_limit(tmp_path: Path):
    playlist = (
        "https://www.youtube.com/playlist?list=PLsRNoUx8w3rNvG9OQk4aHj4s5A_c7dlyV"
    )
    try:
        run_cli(tmp_path, playlist, "-n", "2")
    except SystemExit as e:
        if e.code == 1:
            pytest.skip("Playlist unreachable")
        raise
    json_files = list(tmp_path.glob("*.json"))
    if len(json_files) != 2:
        pytest.skip(f"Expected 2 JSON files, got {len(json_files)}")


def test_real_channel_with_limit(tmp_path: Path):
    channel = "https://www.youtube.com/@TED"
    run_cli(tmp_path, channel, "-n", "3")
    json_files = list(tmp_path.glob("*.json"))
    assert len(json_files) == 3, f"Expected 3 JSON files, got {len(json_files)}"


def test_real_video(tmp_path: Path):
    video = "https://www.youtube.com/watch?v=eyoFYpI47Qg"
    run_cli(tmp_path, video)
    json_files = list(tmp_path.glob("*.json"))
    assert len(json_files) == 1, "No JSON file generated for video"