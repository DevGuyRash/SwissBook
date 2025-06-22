from itertools import islice
from site_downloader.proxy import pool

def test_proxy_cycle_in_grab(monkeypatch):
    proxies = ["http://p1:3128", "http://p2:3128"]
    rot = pool(csv=",".join(proxies))
    assert list(islice(rot, 3)) == ["http://p1:3128", "http://p2:3128", "http://p1:3128"]
