"""
Async-friendly browser-context pool (draft for future batch-rewrite).

Not yet wired into the CLI, but ready for experimentation:

    from site_downloader.pool import get_pool
    pool = await get_pool(engine="chromium", proxy=None, size=4)
    async with pool.page() as page:
        await page.goto("https://example.com")

The pool re-uses the caching layer added in *browser.new_page* so launching the
first context is essentially free.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Tuple

from playwright.async_api import BrowserContext, Page, async_playwright

# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #
class _ContextPool:
    def __init__(self, *, engine: str, proxy: str | None, size: int):
        self.engine = engine
        self.proxy = proxy
        self._size = size
        self._queue: asyncio.Queue[BrowserContext] | None = None
        self._pw = None
        self._browser = None

    async def start(self) -> None:
        self._pw = await async_playwright().start()
        launcher = getattr(self._pw, self.engine)
        self._browser = await launcher.launch(
            headless=True, proxy={"server": self.proxy} if self.proxy else None
        )
        self._queue = asyncio.Queue(self._size)
        for _ in range(self._size):
            ctx = await self._browser.new_context()
            await self._queue.put(ctx)

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()

    @asynccontextmanager
    async def page(self) -> Page:
        if self._queue is None:
            raise RuntimeError("Pool not started – call await start() first")
        ctx = await self._queue.get()
        try:
            page = await ctx.new_page()
            yield page
        finally:
            await page.close()
            await self._queue.put(ctx)


# --------------------------------------------------------------------------- #
# Global cache  (engine, proxy, size) → started pool
# --------------------------------------------------------------------------- #
_POOLS: Dict[Tuple[str, str | None, int], _ContextPool] = {}


async def get_pool(engine: str = "chromium", proxy: str | None = None, size: int = 4) -> _ContextPool:
    key = (engine, proxy, size)
    if key not in _POOLS:
        pool = _ContextPool(engine=engine, proxy=proxy, size=size)
        await pool.start()
        _POOLS[key] = pool
    return _POOLS[key] 