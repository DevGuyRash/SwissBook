from __future__ import annotations

import io
import shutil
import subprocess
from typing import Literal

import html2text
from markdownify import markdownify as mdify  # pip install markdownify

# try Microsoft MarkItDown when available (optional runtime dependency)
try:  # pragma: no cover - optional dependency
    from markitdown import MarkItDown, StreamInfo

    _MARKITDOWN_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - library not installed
    _MARKITDOWN_AVAILABLE = False

from site_downloader.constants import VALID_FORMATS
from site_downloader.errors import PandocMissing


# NOTE: pdf / png are *rendered*, not converted - still useful for CLI validation
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
            try:
                md = MarkItDown()
                result = md.convert_stream(
                    io.BytesIO(html.encode("utf-8")),
                    stream_info=StreamInfo(extension=".html", mimetype="text/html"),
                    keep_data_uris=True,
                )
                return result.text_content
            except Exception:
                # graceful fallback to markdownify on failure
                pass
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
