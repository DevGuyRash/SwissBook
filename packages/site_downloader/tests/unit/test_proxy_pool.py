from site_downloader.proxy import pool

def test_cycle_from_single_proxy():
    """Test that a single proxy cycles correctly."""
    rot = pool(single="http://proxy1:8080")
    assert next(rot) == "http://proxy1:8080"
    assert next(rot) == "http://proxy1:8080"  # Should keep returning the same proxy

def test_cycle_from_csv():
    """Test cycling through multiple proxies from a CSV string."""
    rot = pool(csv="http://proxy1:8080,http://proxy2:8080")
    assert next(rot) == "http://proxy1:8080"
    assert next(rot) == "http://proxy2:8080"
    assert next(rot) == "http://proxy1:8080"  # Should cycle back to the beginning

def test_cycle_from_file(tmp_path):
    """Test cycling through proxies from a file."""
    proxy_file = tmp_path / "proxies.txt"
    proxy_file.write_text("http://proxy1:8080\nhttp://proxy2:8080\n")
    
    rot = pool(list_file=proxy_file)
    assert next(rot) == "http://proxy1:8080"
    assert next(rot) == "http://proxy2:8080"
    assert next(rot) == "http://proxy1:8080"  # Should cycle back to the beginning

def test_no_proxies():
    """Test behavior when no proxies are provided."""
    rot = pool()
    assert next(rot) is None
    assert next(rot) is None  # Should keep returning None


def test_combined_sources(tmp_path):
    """Proxies from single, CSV and file should all be used."""
    proxy_file = tmp_path / "proxies.txt"
    proxy_file.write_text("http://p3:8080\nhttp://p4:8080\n")

    rot = pool(
        single="http://p1:8080",
        csv="http://p2:8080",
        list_file=proxy_file,
    )

    assert [next(rot) for _ in range(5)] == [
        "http://p1:8080",
        "http://p2:8080",
        "http://p3:8080",
        "http://p4:8080",
        "http://p1:8080",
    ]


def test_public_proxy_swiftshadow(monkeypatch):
    """Public proxies are appended when Swiftshadow is available."""
    called = {}

    class _PI:
        def __init__(self, *a, **k):
            called.update(k)
            self.proxies = [type("_P", (), {"as_string": lambda _: "http://pub"})()]

    monkeypatch.setattr("site_downloader.proxy.ProxyInterface", _PI)

    rot = pool(public_proxy=1, public_proxy_type="http")

    assert called["protocol"] == "http"
    assert list(next(rot) for _ in range(2)) == ["http://pub", "http://pub"]


def test_public_proxy_no_swiftshadow(monkeypatch):
    """Fallback to SOCKS list when Swiftshadow missing."""

    class FakeResp:
        status_code = 200
        text = "1.1.1.1:1080"

        def raise_for_status(self):
            pass

    monkeypatch.setattr("site_downloader.proxy.ProxyInterface", None)
    monkeypatch.setattr(
        "site_downloader.proxy.requests.get", lambda *a, **k: FakeResp()
    )

    rot = pool(public_proxy=1, public_proxy_type="https")

    assert next(rot).startswith("socks5://1.1.1.1:1080")


def test_swiftshadow_running_loop(monkeypatch):
    """Swiftshadow runs in a thread when an event loop is active."""

    class _PI:
        def __init__(self, *a, **k):
            self.proxies = [type("_P", (), {"as_string": lambda _: "http://pub"})()]

    # Pretend an event loop is already running
    class _Loop:
        def is_running(self):
            return True

    class DummyThread:
        def __init__(self, target):
            self._target = target

        def start(self):
            self._target()

        def join(self):
            pass

    monkeypatch.setattr("site_downloader.proxy.ProxyInterface", _PI)
    monkeypatch.setattr("asyncio.get_running_loop", lambda: _Loop())
    monkeypatch.setattr("site_downloader.proxy.Thread", DummyThread)

    rot = pool(public_proxy=1, public_proxy_type="http")

    assert next(rot) == "http://pub"
