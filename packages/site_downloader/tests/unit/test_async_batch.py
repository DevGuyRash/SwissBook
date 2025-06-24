"""
Ensure cli.batch internal async pipeline works and never spawns extra threads.
We patch anew_page so no browser is required.
"""
import asyncio, pathlib
from site_downloader.cli import batch as _batch
import site_downloader.browser as br

class _StubAsyncPage:
    async def goto(self, *a, **kw): ...
    async def evaluate(self, script):
        if "scrollHeight" in script and "scrollTo" not in script:
            return 1000
    async def screenshot(self, *, path, full_page): pathlib.Path(path).write_text("x")
    async def pdf(self, *, path, **kw): pathlib.Path(path).write_text("x")
    async def emulate_media(self, *a, **kw): ...
    async def close(self): ...

class _Ctx:
    async def __aenter__(self): return (None, None, _StubAsyncPage())
    async def __aexit__(self, *exc): ...

async def _fake_anew_page(*a, **kw): return _Ctx()

def test_async_batch(monkeypatch, tmp_path):
    monkeypatch.setattr(br, "anew_page", _fake_anew_page)

    url_file = tmp_path / "urls.txt"
    url_file.write_text("https://example.com\n")
    _batch(url_file, fmt="png", jobs=2)     # should finish without error
    assert (pathlib.Path("out") / "example.com.png").exists() 