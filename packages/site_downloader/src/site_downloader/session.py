"""
Cookie helpers - load JSON cookies or perform an **interactive login**
to capture cookies for later headless use.
"""

from __future__ import annotations

import json
import pathlib
from typing import List

from playwright.sync_api import sync_playwright


def load_cookie_file(path: str | pathlib.Path) -> List[dict]:
    p = pathlib.Path(path)
    return json.loads(p.read_text()) if p.exists() else []


def interactive_login(url: str, out_path: pathlib.Path) -> list[dict]:
    """
    Launch non-headless Chromium so the user can log in.
    Writes cookies JSON to *out_path* and returns the list.
    """
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        ctx = browser.new_context()
        page = ctx.new_page()
        print("🔓  A browser window will open - log in then press <Enter> here.")
        page.goto(url)
        input("\n<Enter> once logged-in and the page is fully loaded…")
        raw_cookies = ctx.cookies()
        # ensure JSON-serialisable (MagicMock → str; real dict stays unchanged)
        cookies = json.loads(json.dumps(raw_cookies, default=str))
        out_path.write_text(json.dumps(cookies, indent=2))
        print(f"✅  Cookies saved to {out_path}")
        browser.close()
        return cookies
