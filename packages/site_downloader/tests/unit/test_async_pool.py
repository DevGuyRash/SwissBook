# packages/site_downloader/tests/unit/test_async_pool.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from site_downloader.pool import get_pool, _ContextPool

@pytest.fixture(autouse=True)
def clear_pools_cache(monkeypatch):
    """Ensure the global pool cache is empty for each test for isolation."""
    monkeypatch.setattr("site_downloader.pool._POOLS", {})
    yield

@pytest.fixture
def mock_playwright(monkeypatch):
    """A general-purpose, robust mock for the async playwright stack."""
    mock_page = AsyncMock()
    mock_context = AsyncMock()
    mock_context.new_page.return_value = mock_page
    mock_browser = AsyncMock()
    mock_browser.new_context.return_value = mock_context
    mock_browser.close = AsyncMock()

    mock_launcher = AsyncMock()
    mock_launcher.launch.return_value = mock_browser

    mock_pw = MagicMock()
    # Set attributes for all browser engines
    setattr(mock_pw, "chromium", mock_launcher)
    setattr(mock_pw, "firefox", mock_launcher)
    setattr(mock_pw, "webkit", mock_launcher)
    mock_pw.stop = AsyncMock()

    # This correctly models the playwright startup: an awaitable `start()` method
    async def mock_start():
        return mock_pw

    mock_pw_manager = MagicMock()
    mock_pw_manager.start = mock_start

    monkeypatch.setattr("site_downloader.pool.async_playwright", lambda: mock_pw_manager)
    return mock_pw, mock_browser, mock_context, mock_page


@pytest.mark.asyncio
async def test_get_pool_creates_and_caches_pool(mock_playwright):
    """Test that get_pool creates a new pool and correctly caches it."""
    # Import _POOLS inside the test to get the patched version
    from site_downloader.pool import _POOLS
    
    mock_pw, _, _, _ = mock_playwright
    mock_pw.chromium.launch.call_count = 0 # Reset for a clean assertion

    # First call should create the pool
    pool1 = await get_pool(engine="chromium", proxy=None, size=2)
    assert ("chromium", None, 2) in _POOLS
    assert isinstance(pool1, _ContextPool)
    assert mock_pw.chromium.launch.call_count == 1

    # Second call with same parameters should return the cached instance
    pool2 = await get_pool(engine="chromium", proxy=None, size=2)
    assert pool1 is pool2
    # The browser launch method should NOT be called again
    assert mock_pw.chromium.launch.call_count == 1

@pytest.mark.asyncio
async def test_pool_page_context_manager(mock_playwright):
    """Test the page() async context manager of the pool."""
    _, _, _, mock_page = mock_playwright

    pool = await get_pool(engine="chromium", proxy=None, size=1)

    assert pool._queue.qsize() == 1
    async with pool.page() as page:
        assert page is mock_page
        # A context should be taken from the queue while in use
        assert pool._queue.qsize() == 0

    # The context should be returned to the queue after use
    assert pool._queue.qsize() == 1
    mock_page.close.assert_awaited_once()

@pytest.mark.asyncio
async def test_pool_close(mock_playwright):
    """Test that the pool's close method cleans up browser and playwright resources."""
    mock_pw, mock_browser, _, _ = mock_playwright

    pool = await get_pool(engine="chromium", proxy=None, size=1)
    await pool.close()

    mock_browser.close.assert_awaited_once()
    mock_pw.stop.assert_awaited_once()

@pytest.mark.asyncio
async def test_pool_page_raises_if_not_started():
    """Test that pool.page() raises RuntimeError if the pool hasn't been started."""
    pool = _ContextPool(engine="chromium", proxy=None, size=1)
    # Note: pool.start() is deliberately not called here
    with pytest.raises(RuntimeError, match="Pool not started"):
        async with pool.page():
            pass # pragma: no cover
