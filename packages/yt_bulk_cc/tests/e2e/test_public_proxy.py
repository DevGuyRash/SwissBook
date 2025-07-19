
import asyncio
from pathlib import Path
import sys
import pytest
import requests

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
        # Exit code 2 is used for proxy/IP block errors
        if e.code == 2:
            pytest.skip(f"CLI exited with code {e.code}, likely due to proxy/network issues.")
        if e.code not in (0, None):
            raise


def test_real_video_with_public_proxy(tmp_path: Path):
    """
    Uses --public-proxy to fetch a real video transcript.
    This test is designed to be skipped if public proxies fail,
    preventing CI flakes.
    """
    video = "https://www.youtube.com/watch?v=eyoFYpI47Qg"  # A short, stable video
    run_cli(tmp_path, video, "--public-proxy", "5")
    json_files = list(tmp_path.glob("*.json"))
    assert len(json_files) >= 1, "No JSON file generated for video using public proxy"
