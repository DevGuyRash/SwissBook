from __future__ import annotations

import logging
import random
from typing import Final

from fake_useragent import UserAgent

USER_AGENTS_POOL: Final[list[str]] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/123.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/123.0",
]


def _pick_ua(browser: str | None = None, os: str | None = None) -> str:
    """Return a plausible User-Agent string."""
    try:
        ua_src = UserAgent(browsers=[browser] if browser else None,
                           os=[os] if os else None)
        return ua_src.random
    except Exception as exc:  # noqa: BLE001
        logging.warning("fake-useragent failed (%s) - using fallback UA", exc)
        return random.choice(USER_AGENTS_POOL)

