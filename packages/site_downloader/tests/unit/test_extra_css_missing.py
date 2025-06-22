"""
Passing a non‑existent --extra-css file should raise FileNotFoundError
early, before any Playwright work is attempted.
"""

import pathlib
import pytest

from site_downloader.browser import new_page


def test_missing_css_raises(tmp_path: pathlib.Path) -> None:
    bogus = tmp_path / "nope.css"
    with pytest.raises(FileNotFoundError):
        # use contextmanager directly so no CLI parsing is involved
        with new_page(extra_css=[str(bogus)]):
            pass  # pragma: no cover
