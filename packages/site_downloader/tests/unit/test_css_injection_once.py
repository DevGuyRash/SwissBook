# packages/site_downloader/tests/unit/test_css_injection_once.py
import pathlib
from unittest.mock import MagicMock
from site_downloader import browser

def test_only_injects_css_once(monkeypatch, tmp_path: pathlib.Path):
    """
    Verify that CSS files are read from disk and injected only once per process,
    hitting a cache on subsequent requests for the same file.
    """
    css_file = tmp_path / "mystyle.css"
    css_file.write_text("body{opacity:.3}")

    # Isolate the test by resetting the global caches, which is critical.
    monkeypatch.setattr(browser, "_INJECTED", set())
    monkeypatch.setattr(browser, "_CONTEXTS", {})
    monkeypatch.setattr(browser, "_CSS_CACHE", {})
    monkeypatch.setattr(browser, "_BROWSERS", {})
    monkeypatch.setattr(browser, "_PW", None) # Ensure Playwright manager is re-initialized

    # --- We need to mock the entire Playwright object chain ---
    mock_page = MagicMock()
    mock_page.add_init_script = MagicMock()
    mock_page.close = MagicMock()

    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page
    mock_context.add_cookies = MagicMock()
    mock_context.close = MagicMock()

    mock_browser_obj = MagicMock()
    mock_browser_obj.new_context.return_value = mock_context
    mock_browser_obj.close = MagicMock()

    # The launcher is an attribute on the playwright instance (e.g., pw.chromium)
    mock_launcher = MagicMock()
    mock_launcher.launch.return_value = mock_browser_obj

    # The playwright instance itself
    mock_pw_instance = MagicMock()
    mock_pw_instance.chromium = mock_launcher

    # sync_playwright() returns a context manager that, when started,
    # returns the playwright instance.
    mock_pw_manager = MagicMock()
    mock_pw_manager.start.return_value = mock_pw_instance

    monkeypatch.setattr(browser, "sync_playwright", lambda: mock_pw_manager)

    # Run the function multiple times to test caching
    for _ in range(3):
        with browser.new_page(extra_css=[str(css_file)]):
            pass # The work happens inside the context manager

    # Assert that add_init_script was called exactly twice.
    # Once for the default annoyances.css, once for our custom file.
    # Subsequent calls should have been cached and not trigger injection.
    assert mock_page.add_init_script.call_count == 2, \
        f"Expected 2 script injections, but got {mock_page.add_init_script.call_count}"

    # Verify the content of the injected scripts for robustness.
    # The order of injection isn't guaranteed, so check for presence.
    scripts_injected = [
        args[0] for args, kwargs in mock_page.add_init_script.call_args_list
    ]
    
    annoyance_found = any("Cookie, GDPR, and Privacy Banners" in script for script in scripts_injected)
    custom_css_found = any("body{opacity:.3}" in script for script in scripts_injected)

    assert annoyance_found, "Default annoyances.css was not injected"
    assert custom_css_found, "Custom mystyle.css was not injected"
