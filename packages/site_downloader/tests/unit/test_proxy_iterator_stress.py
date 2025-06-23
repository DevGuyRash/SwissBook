"""
Ensure a single-value proxy pool never exhausts (10 000 iterations).
"""
from site_downloader.proxy import pool


def test_single_proxy_infinite_cycle() -> None:
    rot = pool(single="http://p:1")
    for _ in range(10_000):
        assert next(rot) == "http://p:1"
