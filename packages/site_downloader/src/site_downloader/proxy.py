"""
Proxy-rotation helper.
Accepts *one* of:
• single URL            (``--proxy``)
• CSV string            (``--proxies``)
• file with 1/line      (``--proxy-file``)
Returns an **infinite** iterator (cycle) of proxies or ``None``.
"""

from __future__ import annotations

import itertools
import pathlib
from typing import Iterator, Optional


def _iter_from_file(path: str | pathlib.Path) -> list[str]:
    lines = pathlib.Path(path).read_text().splitlines()
    return [ln.strip() for ln in lines if ln.strip()]


def pool(
    single: Optional[str] = None,
    csv: Optional[str] = None,
    list_file: Optional[str | pathlib.Path] = None,
) -> Iterator[str | None]:
    if single:
        return itertools.cycle([single])
    if csv:
        return itertools.cycle([p.strip() for p in csv.split(",") if p.strip()])
    if list_file:
        return itertools.cycle(_iter_from_file(list_file))
    return itertools.cycle([None])
