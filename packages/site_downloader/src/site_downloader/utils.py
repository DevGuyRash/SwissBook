from __future__ import annotations

import re
import unicodedata
from typing import Dict


def extract_url(text_or_url: str) -> str:
    """
    Accept raw URLs **or** Markdown links `[txt](url)` and return just the URL.
    """
    md_match = re.match(r".*?\((https?://[^\s)]+)\)", text_or_url)
    return md_match.group(1) if md_match else text_or_url.strip()


# --------------------------------------------------------------------------- #
#  Re‑implemented *once*, at the **bottom** of the file so it replaces any   #
#  earlier definition and is therefore guaranteed to be the effective one.   #
# --------------------------------------------------------------------------- #

import re, unicodedata

def sanitize_url_for_filename(text: str) -> str:           # noqa: D401 – short
    """Return a filesystem‑safe, *idempotent* ASCII slug."""
    ascii_txt = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    ascii_txt = re.sub(r"^[A-Za-z]+://", "", ascii_txt)         # strip scheme
    ascii_txt = re.sub(r"[^A-Za-z0-9_.-]+", "_", ascii_txt)
    ascii_txt = re.sub(r"_+", "_", ascii_txt)                   # no '__'
    ascii_txt = ascii_txt.strip("._") or "_"
    return ascii_txt[:255]


# ----------  Client-Hint header generator (ported from JS) ---------- #
def sec_ch_headers(user_agent: str) -> Dict[str, str]:
    """
    Return a dict with `Sec-CH-UA*` headers derived from *user_agent*.
    Pure function → easy to unit-test.
    """
    ua = user_agent.lower()
    headers: Dict[str, str] = {}

    # Platform
    if "android" in ua:
        platform = "Android"
    elif "iphone" in ua or "ipad" in ua:
        platform = "iOS"
    elif "win" in ua:
        platform = "Windows"
    elif "macintosh" in ua:
        platform = "macOS"
    elif "linux" in ua:
        platform = "Linux"
    else:
        platform = "Unknown"
    headers["Sec-CH-UA-Platform"] = f'"{platform}"'

    # Mobile boolean
    is_mobile = any(x in ua for x in ("mobi", "android", "iphone")) or platform in (
        "Android",
        "iOS",
    )
    headers["Sec-CH-UA-Mobile"] = "?1" if is_mobile else "?0"

    # Brands
    major_ver: str | None = None
    if "edg/" in ua:
        m = re.search(r"edg/(\d+)", ua)
        major_ver = m.group(1) if m else "99"
        headers["Sec-CH-UA"] = (
            f'"Not_A Brand";v="8", "Chromium";v="{major_ver}", '
            f'"Microsoft Edge";v="{major_ver}"'
        )
    elif "chrome/" in ua:
        m = re.search(r"chrome/(\d+)", ua)
        major_ver = m.group(1) if m else "99"
        headers["Sec-CH-UA"] = (
            f'"Not_A Brand";v="8", "Chromium";v="{major_ver}", '
            f'"Google Chrome";v="{major_ver}"'
        )
    elif "firefox/" in ua:
        m = re.search(r"firefox/(\d+)", ua)
        major_ver = m.group(1) if m else "99"
        headers["Sec-CH-UA"] = f'"Firefox";v="{major_ver}"'

    # --- Fallback: always provide the header so downstream code/tests that
    # require the triad {UA-Platform, UA-Mobile, UA} never break even when
    # the UA string is too exotic or extremely short (e.g. "0").
    if "Sec-CH-UA" not in headers:
        headers["Sec-CH-UA"] = '"Not_A Brand";v="99"'

    return headers
