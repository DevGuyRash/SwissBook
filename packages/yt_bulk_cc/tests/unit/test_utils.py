from pathlib import Path
import json
import re

import pytest

from yt_bulk_cc import yt_bulk_cc as ytb
from conftest import run_cli, extract_header_counts


def test_slug_strips_bad_chars():
    assert ytb.slug("A/B<C>D|E?F", 20) == "A_B_C_D_E_F"


def test_stats_helper():
    txt = "one two\nthree"
    w, l, c = ytb._stats(txt)
    assert (w, l, c) == (3, 1, len(txt))


def test_stats_no_final_newline():
    txt = "hello world"
    assert ytb._stats(txt) == (2, 0, 11)
