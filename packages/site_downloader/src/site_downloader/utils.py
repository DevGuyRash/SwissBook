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


def sanitize_url_for_filename(url: str) -> str:
    """
    Turn a URL into a filesystem-safe slug:  `https://a/b?q=v`
    → `a_b_q_v`
    """
    url = re.sub(r"^https?://", "", url)
    url = re.sub(r"[/?=&#:]+", "_", url)
    slug = re.sub(r"_{2,}", "_", url).strip("_")
    normalized = unicodedata.normalize("NFKD", slug).encode("ascii", "ignore").decode()
    return normalized or "index"


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
        major_ver = re.search(r"edg/(\d+)", ua).group(1)
        headers["Sec-CH-UA"] = (
            f'"Not_A Brand";v="8", "Chromium";v="{major_ver}", '
            f'"Microsoft Edge";v="{major_ver}"'
        )
    elif "chrome/" in ua:
        major_ver = re.search(r"chrome/(\d+)", ua).group(1)
        headers["Sec-CH-UA"] = (
            f'"Not_A Brand";v="8", "Chromium";v="{major_ver}", '
            f'"Google Chrome";v="{major_ver}"'
        )
    elif "firefox/" in ua:
        major_ver = re.search(r"firefox/(\d+)", ua).group(1)
        headers["Sec-CH-UA"] = f'"Firefox";v="{major_ver}"'

    return headers
