import json
import pathlib
from unittest.mock import patch, MagicMock

import pytest

from site_downloader.session import load_cookie_file, interactive_login

def test_load_cookie_file_exists(tmp_path):
    """Test loading cookies from an existing file."""
    # Create a temporary cookie file
    cookie_data = [{"name": "test", "value": "123", "domain": "example.com"}]
    cookie_file = tmp_path / "cookies.json"
    cookie_file.write_text(json.dumps(cookie_data))
    
    # Test loading the cookies
    cookies = load_cookie_file(cookie_file)
    assert len(cookies) == 1
    assert cookies[0]["name"] == "test"
    assert cookies[0]["value"] == "123"
    assert cookies[0]["domain"] == "example.com"

def test_load_cookie_file_not_exists(tmp_path):
    """Test loading cookies from a non-existent file returns empty list."""
    cookie_file = tmp_path / "nonexistent.json"
    cookies = load_cookie_file(cookie_file)
    assert cookies == []

@patch('site_downloader.session.sync_playwright')
def test_interactive_login(mock_sync_playwright, tmp_path):
    """Test interactive login flow."""
    # Setup mocks
    mock_pw_manager = MagicMock()
    mock_pw = mock_pw_manager.__enter__.return_value
    mock_sync_playwright.return_value = mock_pw_manager

    mock_browser = mock_pw.chromium.launch.return_value
    mock_context = mock_browser.new_context.return_value
    mock_page = mock_context.new_page.return_value
    
    # Mock the cookies that would be returned
    test_cookies = [{"name": "session", "value": "abc123", "domain": "example.com"}]
    mock_context.cookies.return_value = test_cookies
    
    # Mock the input function to simulate user pressing Enter
    with patch('builtins.input', return_value=''):
        # Call the function
        out_path = tmp_path / "cookies.json"
        cookies = interactive_login("https://example.com/login", out_path)
    
    # Verify the cookies were returned
    assert cookies == test_cookies
    
    # Verify the cookies were written to the file
    assert out_path.exists()
    saved_cookies = json.loads(out_path.read_text())
    assert saved_cookies == test_cookies
    
    # Verify the browser interactions
    mock_pw.chromium.launch.assert_called_once_with(headless=False)
    mock_page.goto.assert_called_once_with("https://example.com/login")
    mock_browser.close.assert_called_once()
    mock_pw_manager.__exit__.assert_called_once()
