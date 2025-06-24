"""
Fuzz `sec_ch_headers` with arbitrary UA strings.
The function must never crash and must always return mandatory keys.
"""
import pytest

hyp = pytest.importorskip("hypothesis")
from hypothesis import given, strategies as st

from site_downloader.utils import sec_ch_headers


MANDATORY = {"Sec-CH-UA", "Sec-CH-UA-Mobile", "Sec-CH-UA-Platform"}


@given(st.text(min_size=1))
def test_headers_always_present(ua: str) -> None:
    hdrs = sec_ch_headers(ua)
    assert MANDATORY.issubset(hdrs.keys())
    # Mobile flag is always ?0 / ?1
    assert hdrs["Sec-CH-UA-Mobile"] in {"?0", "?1"}
