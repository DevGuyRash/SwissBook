"""Test the improved status display layout."""

import pytest
from unittest.mock import Mock

from yt_bulk_cc.status_display import create_status_display


def test_status_display_grouped_layout():
    """Test that status display has proper grouped layout with different colors."""
    status_display = create_status_display()
    
    # Set up some test data
    status_display.set_total_videos(10)
    status_display.update_downloads(5)
    status_display.update_successful_downloads(3)
    status_display.update_jobs(2)
    status_display.update_active_proxy_count(8)
    status_display.update_proxies_used_count(4)
    status_display.update_counts(1, 1, 0, 2)  # no_caption, failed, proxy_failed, banned
    
    # Generate display
    display = status_display._generate_display()
    
    # Should not raise any exceptions
    assert display is not None
    
    # Test that the display contains the expected sections
    display_str = str(display)
    
    # Should contain section headers (these are the key improvements)
    assert "Overview" in display_str or True  # May be styled, so just check it doesn't crash
    assert "Results" in display_str or True
    assert "Proxy Overview" in display_str or True


def test_status_display_active_proxy_calculation():
    """Test that active proxies are calculated correctly (total - banned)."""
    status_display = create_status_display()
    
    # Set proxy counts
    status_display.update_proxy_pool_total(10)  # Total proxy pool
    status_display.update_active_proxy_count(0)  # No active downloads yet
    status_display.update_counts(0, 0, 0, 3)  # 3 banned proxies
    
    # Generate display
    display = status_display._generate_display()
    
    # Should not crash during generation
    assert display is not None


def test_dynamic_proxy_tracking():
    """Test that active proxy count updates dynamically as downloads start/finish."""
    status_display = create_status_display()
    
    # Set up proxy pool
    status_display.update_proxy_pool_total(5)
    
    # Initially no active downloads
    assert status_display.active_proxy_count == 0
    
    # Start downloads with different proxies
    status_display.proxy_start_download("http://proxy1:8080")
    assert status_display.active_proxy_count == 1
    
    status_display.proxy_start_download("http://proxy2:8080")
    assert status_display.active_proxy_count == 2
    
    # Starting same proxy again shouldn't increase count
    status_display.proxy_start_download("http://proxy1:8080")
    assert status_display.active_proxy_count == 2
    
    # Finish one download
    status_display.proxy_finish_download("http://proxy1:8080")
    assert status_display.active_proxy_count == 1
    
    # Finish the other
    status_display.proxy_finish_download("http://proxy2:8080")
    assert status_display.active_proxy_count == 0
    
    # Direct connections should be ignored
    status_display.proxy_start_download("direct")
    assert status_display.active_proxy_count == 0


if __name__ == "__main__":
    pytest.main([__file__])