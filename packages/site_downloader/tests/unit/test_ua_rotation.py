import pytest
from unittest.mock import patch, MagicMock

from site_downloader.browser import _pick_ua

def test_ua_browser_filter(monkeypatch):
    """Test filtering user agents by browser."""
    # Mock the UserAgent class to return a fixed value
    mock_ua = MagicMock()
    mock_ua.random = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123.0.0.0"
    
    with patch('site_downloader.browser.UserAgent', return_value=mock_ua) as mock_ua_class:
        ua = _pick_ua(browser="chrome")
        assert "Chrome" in ua
        mock_ua_class.assert_called_once_with(browsers=["chrome"], os=None)

def test_ua_os_filter(monkeypatch):
    """Test filtering user agents by OS."""
    # Mock the UserAgent class to return a fixed value
    mock_ua = MagicMock()
    mock_ua.random = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123.0.0.0"
    
    with patch('site_downloader.browser.UserAgent', return_value=mock_ua) as mock_ua_class:
        ua = _pick_ua(os="windows")
        assert "Windows" in ua
        mock_ua_class.assert_called_once_with(browsers=None, os=["windows"])

def test_ua_fallback(monkeypatch):
    """Test fallback to static UA list when fake-useragent fails."""
    # Make UserAgent initialization raise an exception
    def mock_init(*args, **kwargs):
        raise Exception("Network error")
    
    with patch('site_downloader.browser.UserAgent.__init__', side_effect=mock_init):
        with patch('random.choice', return_value="fallback-ua") as mock_choice:
            ua = _pick_ua()
            assert ua == "fallback-ua"
            mock_choice.assert_called_once()

def test_ua_no_filters(monkeypatch):
    """Test UA generation with no filters."""
    mock_ua = MagicMock()
    mock_ua.random = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123.0.0.0"
    
    with patch('site_downloader.browser.UserAgent', return_value=mock_ua) as mock_ua_class:
        ua = _pick_ua()
        assert ua is not None
        mock_ua_class.assert_called_once_with(browsers=None, os=None)
