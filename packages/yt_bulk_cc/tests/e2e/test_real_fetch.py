import urllib.request
import asyncio
from pathlib import Path
import sys
import pytest

from yt_bulk_cc import yt_bulk_cc as ytb

pytestmark = pytest.mark.e2e

try:
    urllib.request.urlopen('https://www.youtube.com', timeout=5)
except Exception:
    pytest.skip('YouTube unreachable', allow_module_level=True)


def run_cli(tmp_path: Path, *argv: str) -> None:
    sys.argv[:] = ['yt_bulk_cc.py', *argv]
    if '-o' not in argv and '--folder' not in argv:
        sys.argv += ['-o', str(tmp_path)]
    try:
        asyncio.run(ytb.main())
    except SystemExit as e:
        if e.code not in (0, None):
            raise


def test_real_playlist(tmp_path: Path):
    playlist = 'https://www.youtube.com/playlist?list=PLjV3HijScGMynGvjJrvNNd5Q9pPy255dL'
    run_cli(tmp_path, playlist, '-n', '1')
    assert list(tmp_path.glob('*.json'))
