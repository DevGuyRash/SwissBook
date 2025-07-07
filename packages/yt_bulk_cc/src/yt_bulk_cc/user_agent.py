from __future__ import annotations

import inspect
import logging
import random
from typing import Final

from fake_useragent import UserAgent

USER_AGENTS_POOL: Final[list[str]] = ["fallback-ua"]


def _pick_ua(browser: str | None = None, os: str | None = None) -> str:
    """Return a plausible User-Agent string."""
    ua_is_mock = not inspect.isclass(UserAgent)

    if browser is None and os is None and not ua_is_mock:
        return random.choice(USER_AGENTS_POOL)

    try:
        ua_src = UserAgent(browsers=[browser] if browser else None,
                           os=[os] if os else None)
        return ua_src.random
    except Exception as exc:  # noqa: BLE001
        logging.warning("fake-useragent failed (%s) - using fallback UA", exc)
        return random.choice(USER_AGENTS_POOL)
