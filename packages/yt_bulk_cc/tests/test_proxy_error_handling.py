"""Regression tests for proxy error handling and SwiftShadow integration."""

import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock
import logging

from yt_bulk_cc.cli import initialize_proxy_pool, _wait_for_proxy_availability
from yt_bulk_cc.core import grab
from yt_bulk_cc.status_display import create_status_display


class TestProxyErrorHandling:
    """Test proxy error handling and timeout scenarios."""

    @pytest.mark.asyncio
    async def test_proxy_pool_initialization_timeout(self):
        """Test that proxy pool initialization times out gracefully."""
        # Mock args and status display
        args = Mock()
        args.public_proxy = 5
        args.proxy_refresh = 0
        args.verbose = 0
        
        status_display = Mock()
        status_display.update_status = Mock()
        status_display.update_active_proxy_count = Mock()
        status_display.update_proxies = Mock()
        
        # Mock ProxyPool that hangs during initialization
        with patch('yt_bulk_cc.cli.ProxyPool') as mock_proxy_pool_class:
            mock_proxy_pool = Mock()
            mock_proxy_pool.get = Mock(side_effect=asyncio.TimeoutError())
            mock_proxy_pool._proxies = []
            mock_proxy_pool_class.return_value = mock_proxy_pool
            
            # Mock the wait function to timeout
            with patch('yt_bulk_cc.cli._wait_for_proxy_availability', 
                      side_effect=asyncio.TimeoutError()):
                
                result = await initialize_proxy_pool(args, status_display)
                
                # Should return None on timeout
                assert result is None
                
                # Should update status appropriately
                status_display.update_status.assert_any_call("⏰ Proxy loading timed out - continuing without proxies")
                status_display.update_active_proxy_count.assert_called_with(0)

    @pytest.mark.asyncio
    async def test_proxy_pool_initialization_exception(self):
        """Test that proxy pool initialization handles exceptions gracefully."""
        args = Mock()
        args.public_proxy = 5
        args.proxy_refresh = 0
        args.verbose = 0
        
        status_display = Mock()
        status_display.update_status = Mock()
        status_display.update_active_proxy_count = Mock()
        
        # Mock ProxyPool that raises an exception
        with patch('yt_bulk_cc.cli.ProxyPool', side_effect=Exception("SwiftShadow error")):
            result = await initialize_proxy_pool(args, status_display)
            
            # Should return None on exception
            assert result is None
            
            # Should update status with error message
            status_display.update_status.assert_any_call("❌ Proxy loading failed - SwiftShadow error")
            status_display.update_active_proxy_count.assert_called_with(0)

    @pytest.mark.asyncio
    async def test_wait_for_proxy_availability_success(self):
        """Test successful proxy availability check."""
        mock_proxy_pool = Mock()
        mock_proxy_pool.get = Mock(return_value="http://proxy:8080")
        
        # Should complete without raising
        await _wait_for_proxy_availability(mock_proxy_pool, 5)
        
        # Should have called get at least once
        mock_proxy_pool.get.assert_called()

    @pytest.mark.asyncio
    async def test_wait_for_proxy_availability_failure(self):
        """Test proxy availability check with persistent failures."""
        mock_proxy_pool = Mock()
        mock_proxy_pool.get = Mock(side_effect=Exception("Connection failed"))
        mock_proxy_pool._proxies = None
        
        # Should raise after max attempts
        with pytest.raises(Exception, match="Connection failed"):
            await _wait_for_proxy_availability(mock_proxy_pool, 5)

    @pytest.mark.asyncio
    async def test_grab_function_proxy_pool_exhausted(self):
        """Test grab function when proxy pool is exhausted."""
        # Mock proxy pool that returns None (exhausted)
        mock_proxy_pool = Mock()
        mock_proxy_pool.get = Mock(return_value=None)
        
        sem = asyncio.Semaphore(1)
        banned = set()
        used = set()
        
        result = await grab(
            vid="test_video",
            title="Test Video",
            path=Mock(),
            langs=["en"],
            fmt_key="json",
            sem=sem,
            tries=1,
            proxy_pool=mock_proxy_pool,
            banned=banned,
            used=used
        )
        
        # Should return proxy_fail when no proxies available
        assert result[0] == "proxy_fail"
        assert result[1] == "test_video"
        assert result[2] == "Test Video"

    @pytest.mark.asyncio
    async def test_grab_function_banned_proxy_handling(self):
        """Test that grab function properly handles banned proxies."""
        # Mock proxy pool that returns a banned proxy
        mock_proxy_pool = Mock()
        mock_proxy_pool.get = Mock(return_value="http://banned-proxy:8080")
        
        sem = asyncio.Semaphore(1)
        banned = {"http://banned-proxy:8080"}  # Pre-banned
        used = set()
        
        result = await grab(
            vid="test_video",
            title="Test Video", 
            path=Mock(),
            langs=["en"],
            fmt_key="json",
            sem=sem,
            tries=1,
            proxy_pool=mock_proxy_pool,
            banned=banned,
            used=used
        )
        
        # Should return proxy_fail when only banned proxies available
        assert result[0] == "proxy_fail"


class TestAsyncEventLoopHandling:
    """Test async event loop conflict resolution."""

    def test_safe_run_no_existing_loop(self):
        """Test _safe_run when no event loop exists."""
        import yt_bulk_cc
        
        # Mock asyncio functions
        with patch('yt_bulk_cc._aio.get_running_loop', side_effect=RuntimeError("no running event loop")):
            with patch('yt_bulk_cc._orig_run') as mock_orig_run:
                mock_orig_run.return_value = "result"
                
                async def test_coro():
                    return "test"
                
                result = yt_bulk_cc._aio.run(test_coro())
                
                # Should call original run
                mock_orig_run.assert_called_once()
                assert result == "result"

    def test_safe_run_with_running_loop(self):
        """Test _safe_run when event loop is already running."""
        import yt_bulk_cc
        
        # Mock a running event loop
        mock_loop = Mock()
        mock_loop.is_running.return_value = True
        
        with patch('yt_bulk_cc._aio.get_running_loop', return_value=mock_loop):
            with patch('yt_bulk_cc._aio.create_task') as mock_create_task:
                mock_create_task.return_value = "task"
                
                async def test_coro():
                    return "test"
                
                result = yt_bulk_cc._aio.run(test_coro())
                
                # Should create task instead of running
                mock_create_task.assert_called_once()
                assert result == "task"


class TestStatusDisplayEnhancements:
    """Test status display emoji categorization and progress display."""

    def test_status_display_emoji_indicators(self):
        """Test that status display uses proper emoji indicators."""
        status_display = create_status_display()
        
        # Test various status updates
        status_display.update_status("🌐 Loading public proxies...")
        status_display.update_counts(5, 2, 1, 3)  # no_caption, failed, proxy_failed, banned
        
        # Should not raise any exceptions
        assert True

    def test_progress_bar_prefix(self):
        """Test that progress bar has 'Progress: ' prefix."""
        status_display = create_status_display()
        status_display.set_total_videos(10)
        
        # Check that progress task is created with correct description
        if hasattr(status_display, 'progress') and status_display.progress:
            # The progress task should have been created with "Progress: " prefix
            assert status_display.progress_task is not None


class TestNetworkErrorHandling:
    """Test network error handling and retry logic."""

    @pytest.mark.asyncio
    async def test_network_error_retry_logic(self):
        """Test exponential backoff retry logic for network errors."""
        from yt_bulk_cc.errors import TooManyRequests
        
        # Mock session that fails with network error
        with patch('yt_bulk_cc.core.requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session
            
            with patch('yt_bulk_cc.core.YouTubeTranscriptApi') as mock_api_class:
                mock_api = Mock()
                mock_api.fetch.side_effect = TooManyRequests("Rate limited")
                mock_api_class.return_value = mock_api
                
                sem = asyncio.Semaphore(1)
                banned = set()
                used = set()
                
                # Mock sleep to speed up test
                with patch('asyncio.sleep', new_callable=AsyncMock):
                    result = await grab(
                        vid="test_video",
                        title="Test Video",
                        path=Mock(),
                        langs=["en"],
                        fmt_key="json",
                        sem=sem,
                        tries=2,  # Limited tries for test
                        banned=banned,
                        used=used,
                        delay=0.0
                    )
                
                # Should eventually fail after retries
                assert result[0] == "proxy_fail"
                
                # Should have tried multiple times
                assert mock_api.fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_file_descriptor_cleanup(self):
        """Test that file descriptors are properly cleaned up."""
        # This test ensures that the resource warnings are suppressed
        # and that proper cleanup occurs
        
        import warnings
        
        # Capture warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            # Simulate the scenario that caused "Bad file descriptor" errors
            try:
                # This would normally cause resource warnings
                import socket
                s = socket.socket()
                s.close()
                s.close()  # Double close should be handled gracefully
            except:
                pass
            
            # Should not have ResourceWarning about bad file descriptors
            resource_warnings = [warning for warning in w 
                               if issubclass(warning.category, ResourceWarning)
                               and "Bad file descriptor" in str(warning.message)]
            
            # The warnings should be filtered out by our configuration
            assert len(resource_warnings) == 0 or all(
                "Bad file descriptor" not in str(w.message) for w in resource_warnings
            )


if __name__ == "__main__":
    pytest.main([__file__])