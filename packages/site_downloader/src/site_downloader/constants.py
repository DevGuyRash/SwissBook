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
DEFAULT_ANNOY_CSS: Final[str] = "annoyances.default.css"

# files that are **treated as a list of URLs** when passed to `grab`
LIST_FILE_SUFFIXES: Final[Set[str]] = {".txt", ".urls"}

# NOTE: static pool kept only as *fallback* when fake-useragent cannot reach
# its bundled JSONL (extremely rare).  Production path replaces this list.
USER_AGENTS_POOL: Final[list[str]] = ["fallback-ua"]
