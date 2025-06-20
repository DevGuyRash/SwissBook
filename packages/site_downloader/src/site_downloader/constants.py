"""
Single place for constants that are used across the package.
"""

from typing import Final, Set

VALID_FORMATS: Final[Set[str]] = {
    # text-like
    "html",
    "md",
    "txt",
    "docx",
    "epub",
    # rendered / binary
    "pdf",
    "png",
}

DEFAULT_OUTDIR: Final = "out"

# --------------------------- runtime defaults --------------------------- #
DEFAULT_VIEWPORT: Final[int] = 1280
DEFAULT_SCALE: Final[float] = 2.0

# files that are **treated as a list of URLs** when passed to `grab`
LIST_FILE_SUFFIXES: Final[Set[str]] = {".txt", ".urls"}

USER_AGENTS_POOL: Final[list[str]] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]
