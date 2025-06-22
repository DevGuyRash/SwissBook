"""
Confirm cli.batch honours the --jobs semaphore and never invokes
grab concurrently more than the requested amount.
"""

import asyncio
import pathlib
from collections import Counter

import pytest
from site_downloader.cli import batch as _batch_cmd


def test_batch_jobs_limit(monkeypatch, tmp_path: pathlib.Path):
    # record timestamps when fake_grab is entered
    current = Counter()

    async def _fake_to_thread(func, *args, **kwargs):
        # func is cli.grab ; we don't await, just increment concurrency counter
        current["active"] += 1
        # mimic IO wait
        await asyncio.sleep(0.01)
        current["max"] = max(current["max"], current["active"])
        current["active"] -= 1

    monkeypatch.setattr(asyncio, "to_thread", _fake_to_thread)

    # Stub grab to no‑op; batch indirectly calls it via to_thread
    monkeypatch.setattr("site_downloader.cli.grab", lambda *a, **kw: None)

    url_file = tmp_path / "urls.txt"
    url_file.write_text("\n".join(f"https://ex{i}.com" for i in range(20)))

    # run batch with --jobs 5
    _batch_cmd(url_file, fmt="html", jobs=5)

    assert current["max"] <= 5
