from __future__ import annotations

import logging
from typing import Final

from faker import Faker
from fake_useragent import UserAgent

_Faker: Final = Faker()


def _pick_ua(browser: str | None = None, os: str | None = None) -> str:
    """Return a plausible User-Agent string."""
    try:
        ua_src = UserAgent(browsers=[browser] if browser else None,
                           os=[os] if os else None)
        return ua_src.random
    except Exception as exc:  # noqa: BLE001
        logging.warning("fake-useragent failed (%s) - using fallback UA", exc)
        return _Faker.user_agent()

