"""
Property‑based fuzzing for utils.sanitize_url_for_filename.

Ensures the function never:
* raises,
* produces path separators,
* emits non‑ASCII,
* returns an empty or >255‑char string.
"""
import unicodedata

import pytest

# Hypothesis is optional at runtime - skip gracefully when absent
hyp = pytest.importorskip("hypothesis")

from hypothesis import given, strategies as st

from site_downloader.utils import sanitize_url_for_filename


@given(st.text(min_size=1, max_size=512))
def test_slug_invariants(random_text: str) -> None:
    slug = sanitize_url_for_filename(random_text)
    # ---- structural guarantees ------------------------------------------- #
    assert slug, "slug should never be empty"
    assert len(slug) <= 255, "slug must fit common FS limits"
    assert "/" not in slug and "\\" not in slug, "no path separators allowed"
    assert all(ord(ch) < 128 for ch in slug), "result should be ASCII"

    # double‑normalisation must be idempotent
    assert sanitize_url_for_filename(slug) == slug
    # stylistic: no repeated underscores
    assert "__" not in slug

    # extra sanity: Unicode normalisation round‑trip is stable
    assert unicodedata.normalize("NFKD", slug) == slug
