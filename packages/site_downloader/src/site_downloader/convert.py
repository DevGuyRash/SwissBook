from __future__ import annotations

import shutil
import subprocess
from typing import Literal

import html2text
from markdownify import markdownify as mdify  # pip install markdownify

# try Microsoft MarkItDown when available (optional runtime dependency)
try:
    from markitdown.html import html_to_markdown  # type: ignore

    _MARKITDOWN_AVAILABLE = True
except ModuleNotFoundError:
    _MARKITDOWN_AVAILABLE = False

from site_downloader.constants import VALID_FORMATS
from site_downloader.errors import PandocMissing


# NOTE: pdf / png are *rendered*, not converted – still useful for CLI validation
def convert_html(
    html: str, fmt: Literal["html", "md", "txt", "docx", "epub"]
) -> str | bytes:
    """Convert HTML to chosen format. Returns str, except docx/epub -> bytes."""
    fmt = fmt.lower()
    if fmt not in VALID_FORMATS:
        raise ValueError(f"Unsupported format: {fmt}")

    if fmt == "html":
        return html
    if fmt == "md":
        # Prefer MarkItDown when present (better tables/code-blocks)
        if _MARKITDOWN_AVAILABLE:
            return html_to_markdown(html)
        return mdify(html, heading_style="ATX")
    if fmt == "txt":
        return html2text.html2text(html)

    # binary formats need pandoc
    if shutil.which("pandoc") is None:
        raise PandocMissing(
            "Pandoc is required for docx/epub output. "
            "See https://pandoc.org/install.html"
        )

    process = subprocess.run(
        ["pandoc", "-f", "html", "-t", fmt, "-"],
        input=html.encode(),
        capture_output=True,
        check=True,
    )
    return process.stdout
