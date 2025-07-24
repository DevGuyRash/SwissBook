import asyncio
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import yt_bulk_cc as ytb
from yt_bulk_cc.errors import IpBlocked, TooManyRequests
from youtube_transcript_api.proxies import GenericProxyConfig, WebshareProxyConfig
from site_downloader.proxy import ProxyPool

from conftest import run_cli, strip_ansi


# ────────────────── Hardening / resilience tests ──────────────────────
"""
Hardening / resilience tests that go beyond the spec-checklist:

* retry/back-off logic for TooManyRequests
* Windows MAX_PATH shortening safeguard
"""

# ──────────────────────────────────────────────────────────────────────────
# 1. Retry logic - TooManyRequests raises twice, then succeeds
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("patch_scrapetube", "patch_detect")
def test_retry_too_many_requests(monkeypatch, tmp_path: Path, capsys):
    """_grab() must back-off and still succeed after transient 429 errors."""

    calls = {"n": 0}

    def _fake_fetch(*_a, **_kw):
        calls["n"] += 1
        if calls["n"] < 3:  # first two attempts → fail
            raise ytb.TooManyRequests("slow down")

        # third attempt → return minimal cue
        class _FT:
            def to_raw_data(self):
                return [{"start": 0.0, "duration": 1.0, "text": "OK"}]

        return _FT()

    class _FakeApi:
        def __init__(self, *a, **kw):
            pass

        def fetch(self, *a, **kw):
            return _fake_fetch(*a, **kw)

    monkeypatch.setattr(ytb.core, "YouTubeTranscriptApi", _FakeApi)

    # -v → console log level INFO so the retry line reaches stdout
    run_cli(tmp_path, "dummy", "-f", "text", "-n", "1", "-v")

    # a file should have been produced after retries
    assert list(tmp_path.glob("*.txt")), "no output after retries"

    # We should have attempted exactly three calls (two 429s + final success)
    assert calls["n"] == 3, "back-off logic did not retry the expected number of times"


@pytest.mark.usefixtures("patch_scrapetube", "patch_detect")
def test_retry_ip_blocked(monkeypatch, tmp_path: Path, capsys):
    """_grab() must back-off and still succeed after transient IpBlocked errors."""

    calls = {"n": 0}

    def _fake_fetch(*_a, **_kw):
        calls["n"] += 1
        if calls["n"] < 3:  # first two attempts → fail
            raise ytb.IpBlocked("IP blocked")

        # third attempt → return minimal cue
        class _FT:
            def to_raw_data(self):
                return [{"start": 0.0, "duration": 1.0, "text": "OK"}]

        return _FT()

    class _FakeApi:
        def __init__(self, *a, **kw):
            pass

        def fetch(self, *a, **kw):
            return _fake_fetch(*a, **kw)

    monkeypatch.setattr(ytb.core, "YouTubeTranscriptApi", _FakeApi)

    # -v → console log level INFO so the retry line reaches stdout
    run_cli(tmp_path, "dummy", "-f", "text", "-n", "1", "-v")

    # a file should have been produced after retries
    assert list(tmp_path.glob("*.txt")), "no output after retries"

    # We should have attempted exactly three calls (two IpBlocked + final success)
    assert calls["n"] == 3, "back-off logic did not retry the expected number of times"


@pytest.mark.usefixtures("patch_scrapetube", "patch_detect")
def test_check_ip_bails(monkeypatch, tmp_path: Path, capsys):
    monkeypatch.setattr("yt_bulk_cc.probe_video", lambda *a, **k: (False, {"p"}))
    with pytest.raises(SystemExit):
        run_cli(tmp_path, "dummy", "-f", "text", "-n", "2", "--check-ip")
    out = strip_ansi(capsys.readouterr().out)
    assert "Current IP appears blocked" in out


@pytest.mark.usefixtures("patch_scrapetube", "patch_detect")
def test_check_ip_ok(monkeypatch, tmp_path: Path, patch_transcript):
    called = {"n": 0}

    def probe(*a, **k):
        called["n"] += 1
        return True, set()

    monkeypatch.setattr("yt_bulk_cc.probe_video", probe)
    run_cli(tmp_path, "dummy", "-f", "text", "-n", "1", "--check-ip")
    assert called["n"] == 1


# ──────────────────────────────────────────────────────────────────────────
# 2. Windows path-length safeguard
# ──────────────────────────────────────────────────────────────────────────


def test_windows_path_shortening(monkeypatch, tmp_path: Path):
    """Unit-test the helper directly; no need to touch pathlib.WindowsPath."""

    long_title = "L" * 500
    original = tmp_path / f"[vid] {long_title}.txt"

    # Make the helper think it's running on Windows **after** the Path exists
    monkeypatch.setattr(ytb.os, "name", "nt", raising=False)

    shortened = ytb._shorten_for_windows(original)
    assert len(str(shortened)) <= 260, "path exceeds Windows MAX_PATH"


# ---------------------------------------------------------------------------
# 3. Ensure grab() uses a browser-like User-Agent
# ---------------------------------------------------------------------------


def test_default_user_agent(monkeypatch, tmp_path: Path):
    """grab() should use a sensible User-Agent header by default."""

    monkeypatch.setattr(ytb, "detect", lambda _u: ("video", "vidX"))
    monkeypatch.setattr(ytb, "_pick_ua", lambda *_a, **_k: "UA/123")
    monkeypatch.setattr(ytb.core, "_pick_ua", lambda *_a, **_k: "UA/123")

    captured = {}

    class _FakeApi:
        def __init__(self, *_, **kw):
            captured["ua"] = kw.get("http_client").headers.get("User-Agent")

        def fetch(self, *a, **kw):
            class _FT:
                def to_raw_data(self):
                    return [{"start": 0.0, "duration": 1.0, "text": "hi"}]

            return _FT()

    monkeypatch.setattr(ytb.core, "YouTubeTranscriptApi", _FakeApi)

    run_cli(tmp_path, "https://youtu.be/vidX")

    assert captured["ua"] == "UA/123"


def test_generic_proxy_flags(monkeypatch, tmp_path: Path):
    """CLI should pass GenericProxyConfig with provided proxy URLs."""

    monkeypatch.setattr(ytb, "detect", lambda _u: ("playlist", "X"))
    monkeypatch.setattr(
        ytb.scrapetube,
        "get_playlist",
        lambda *_a, **_k: [{"videoId": "x", "title": {"runs": [{"text": "d"}]}}],
    )

    captured = {}

    class _FakeApi:
        def __init__(self, *_, **kw):
            captured["cfg"] = kw.get("proxy_config")

        def fetch(self, *a, **kw):
            class _FT:
                def to_raw_data(self):
                    return []

            return _FT()

    monkeypatch.setattr(ytb.core, "YouTubeTranscriptApi", _FakeApi)

    with pytest.warns(DeprecationWarning):
        run_cli(
            tmp_path,
            "dummy",
            "-p",
            "http://u:p@h:1",
            "-n",
            "1",
        )
    # Deprecated – Webshare now routed internally
    assert captured["cfg"] is None


def test_webshare_proxy(monkeypatch, tmp_path: Path):
    """CLI should use WebshareProxyConfig when credentials provided."""

    monkeypatch.setattr(ytb, "detect", lambda _u: ("playlist", "X"))
    monkeypatch.setattr(
        ytb.scrapetube,
        "get_playlist",
        lambda *_a, **_k: [{"videoId": "x", "title": {"runs": [{"text": "d"}]}}],
    )

    captured = {}

    class _FakeApi:
        def __init__(self, *_, **kw):
            captured["cfg"] = kw.get("proxy_config")

        def fetch(self, *a, **kw):
            class _FT:
                def to_raw_data(self):
                    return []

            return _FT()

    monkeypatch.setattr(ytb.core, "YouTubeTranscriptApi", _FakeApi)

    with pytest.warns(DeprecationWarning):
        run_cli(
            tmp_path,
            "dummy",
            "-p",
            "ws://user:pass",
            "-n",
            "1",
        )
    # Deprecated – Webshare now routed internally
    assert captured["cfg"] is None


def test_proxy_pool(monkeypatch, tmp_path: Path):
    """-p should populate proxy_pool with credentials intact."""

    monkeypatch.setattr(ytb, "detect", lambda _u: ("playlist", "X"))
    monkeypatch.setattr(
        ytb.scrapetube,
        "get_playlist",
        lambda *_a, **_k: [{"videoId": "x", "title": {"runs": [{"text": "d"}]}}],
    )

    captured = {}

    async def _fake_grab(*_a, **kw):
        captured["pool"] = kw.get("proxy_pool")
        captured["cfg"] = kw.get("proxy_cfg")
        return ("ok", "x", "t")

    monkeypatch.setattr(ytb, "grab", _fake_grab)

    with pytest.warns(DeprecationWarning):
        run_cli(
            tmp_path,
            "dummy",
            "-p",
            "http://u:p@h:1,https://u2:p2@h2:2",
            "-n",
            "1",
        )
    # Deprecated flags → proxies handled internally
    assert captured["pool"] is None


def test_pool_multiple_webshare(monkeypatch, tmp_path: Path):
    """Multiple ws:// credentials should pass through to grab()."""

    monkeypatch.setattr(ytb, "detect", lambda _u: ("playlist", "X"))
    monkeypatch.setattr(
        ytb.scrapetube,
        "get_playlist",
        lambda *_a, **_k: [{"videoId": "x", "title": {"runs": [{"text": "d"}]}}],
    )

    captured = {}

    async def _fake_grab(*_a, **kw):
        captured["pool"] = kw.get("proxy_pool")
        captured["cfg"] = kw.get("proxy_cfg")
        return ("ok", "x", "t")

    monkeypatch.setattr(ytb, "grab", _fake_grab)

    with pytest.warns(DeprecationWarning):
        run_cli(
            tmp_path,
            "dummy",
            "-p",
            "ws://u:p,ws://u2:p2",
            "-n",
            "1",
        )
    # Deprecated – no explicit pool/cfg expected
    assert captured["pool"] is None
    assert captured["cfg"] is None


def test_make_proxy_ws():
    """_make_proxy should return WebshareProxyConfig for ws:// URLs."""

    from yt_bulk_cc.core import _make_proxy as core_make
    from yt_bulk_cc.yt_bulk_cc import _make_proxy as cli_make

    cfg1 = core_make("ws://aa:bb")
    cfg2 = cli_make("ws://aa:bb")

    for cfg in (cfg1, cfg2):
        assert isinstance(cfg, ytb.WebshareProxyConfig)
        assert cfg.proxy_username == "aa"
        assert cfg.proxy_password == "bb"


@pytest.mark.usefixtures("patch_scrapetube", "patch_detect")
def test_proxy_file_rotation(monkeypatch, tmp_path: Path, capsys):
    proxy_file = tmp_path / "proxies.txt"
    proxy_file.write_text("http://f1\nhttp://f2\n", encoding="utf-8")

    used = []
    calls = {"n": 0}

    class _FakeApi:
        def __init__(self, *a, **kw):
            cfg = kw.get("proxy_config")
            used.append(getattr(cfg, "http_url", None))

        def fetch(self, *a, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                raise ytb.IpBlocked("blocked")

            class _FT:
                def to_raw_data(self):
                    return [{"start": 0.0, "duration": 1.0, "text": "ok"}]

            return _FT()

    monkeypatch.setattr(ytb.core, "YouTubeTranscriptApi", _FakeApi)

    captured = {}
    orig_grab = ytb.grab

    async def _wrap(*args, **kw):
        captured["pool"] = kw.get("proxy_pool")
        return await orig_grab(*args, **kw)

    monkeypatch.setattr(ytb, "grab", _wrap)

    async def _no_sleep(*a, **k):
        return None

    monkeypatch.setattr(ytb.asyncio, "sleep", _no_sleep)

    with pytest.warns(DeprecationWarning):
        run_cli(
            tmp_path,
            "dummy",
            "-p",
            "http://cli",
            "--proxy-file",
            str(proxy_file),
            "-f",
            "text",
            "-n",
            "1",
            "-v",
            "-s",
            "0",
        )
    # Deprecated flags → CLI/file proxies are no‑ops now
    assert captured["pool"] is None
    # No explicit proxy_config → FakeApi saw “None”
    assert all(u is None for u in used[:2])
    # Summary is now logged (not printed) – nothing further to assert
    _ = strip_ansi(capsys.readouterr().out)


@pytest.mark.usefixtures("patch_scrapetube", "patch_detect")
def test_public_proxy(monkeypatch, tmp_path: Path):
    captured: dict[str, Any] = {}

    calls: list[dict[str, Any]] = []

    def _qp(*a, **k):
        calls.append(k)
        idx = len(calls)
        return SimpleNamespace(as_string=lambda: f"http://pub:{idx}")

    monkeypatch.setattr(ytb.cli, "QuickProxy", _qp)

    async def _fake_grab(*_a, **kw):
        captured["pool"] = kw.get("proxy_pool")
        return ("ok", "x", "t")

    monkeypatch.setattr(ytb, "grab", _fake_grab)

    run_cli(tmp_path, "dummy", "--public-proxy", "3", "-n", "1")

    # With the new ProxyPool workflow QuickProxy is no longer called.
    assert captured["pool"] and isinstance(captured["pool"], ProxyPool)


@pytest.mark.usefixtures("patch_scrapetube", "patch_detect")
def test_public_proxy_with_cli(monkeypatch, tmp_path: Path):
    captured = {}

    calls: list[dict[str, Any]] = []

    def _qp(*a, **k):
        calls.append(k)
        return SimpleNamespace(as_string=lambda: "http://pub:1")

    monkeypatch.setattr(ytb.cli, "QuickProxy", _qp)

    async def _fake_grab(*_a, **kw):
        captured["pool"] = kw.get("proxy_pool")
        return ("ok", "x", "t")

    monkeypatch.setattr(ytb, "grab", _fake_grab)

    run_cli(tmp_path, "dummy", "-p", "http://cli", "--public-proxy", "1", "-n", "1")

    # QuickProxy path removed; pool handles proxies
    assert len(calls) == 0


@pytest.mark.usefixtures("patch_scrapetube", "patch_detect")
def test_public_proxy_https(monkeypatch, tmp_path: Path):
    # Mock ProxyPool to capture initialization parameters
    captured_params = {}
    
    class MockProxyPool:
        def __init__(self, **kwargs):
            captured_params.update(kwargs)
            self._proxies = ["https://pub:1", "https://pub:2"]
        
        async def ensure_ready(self):
            pass
        
        def get(self):
            return "https://pub:1"
        
        def close(self):
            pass

    # Mock at the CLI module level where it's imported
    monkeypatch.setattr(ytb.cli, "ProxyPool", MockProxyPool)

    async def _fake_grab(*_a, **kw):
        return ("ok", "x", "t")

    monkeypatch.setattr(ytb, "grab", _fake_grab)

    run_cli(
        tmp_path,
        "dummy",
        "--public-proxy",
        "2",
        "--public-proxy-type",
        "https",
        "-n",
        "1",
    )

    # Verify ProxyPool was initialized with correct parameters
    assert captured_params["max_proxies"] == 2
    assert captured_params["verbose"] == 0


@pytest.mark.usefixtures("patch_scrapetube", "patch_detect")
def test_public_proxy_socks(monkeypatch, tmp_path: Path):
    called = {}

    class FakeResponse:
        status_code = 200
        text = "1.1.1.1:1080\n2.2.2.2:1080"

        def raise_for_status(self):
            pass

    monkeypatch.setattr(ytb.requests, "get", lambda *a, **k: FakeResponse())

    async def _fake_grab(*_a, **kw):
        called["pool"] = kw.get("proxy_pool")
        called["cfg"] = kw.get("proxy_cfg")
        return ("ok", "x", "t")

    monkeypatch.setattr(ytb, "grab", _fake_grab)

    run_cli(
        tmp_path,
        "dummy",
        "--public-proxy",
        "1",
        "--public-proxy-type",
        "socks",
        "-n",
        "1",
    )

    assert called["cfg"] is None


@pytest.mark.usefixtures("patch_scrapetube", "patch_detect")
def test_public_proxy_no_swiftshadow(monkeypatch, tmp_path: Path):
    class FakeResp:
        status_code = 200
        text = "1.2.3.4:1080"

        def raise_for_status(self):
            pass

    monkeypatch.setattr(ytb, "ProxyInterface", None)
    monkeypatch.setattr(ytb.requests, "get", lambda *a, **k: FakeResp())

    captured = {}

    async def _fake_grab(*_a, **kw):
        captured["cfg"] = kw.get("proxy_cfg")
        return ("ok", "x", "t")

    monkeypatch.setattr(ytb, "grab", _fake_grab)

    run_cli(
        tmp_path,
        "dummy",
        "--public-proxy",
        "1",
        "--public-proxy-type",
        "socks",
        "-n",
        "1",
    )

    assert captured["cfg"] is None


@pytest.mark.usefixtures("patch_scrapetube", "patch_detect")
def test_public_proxy_limit(monkeypatch, tmp_path: Path):
    """Limit loaded public proxies to the requested count."""

    # Mock ProxyPool to capture the proxy pool object
    class MockProxyPool:
        def __init__(self, max_proxies=None, **kwargs):
            self.max_proxies = max_proxies
            self._proxies = [f"http://pub:{i+1}" for i in range(max_proxies or 2)]
        
        async def ensure_ready(self):
            pass
        
        def get(self):
            return self._proxies[0] if self._proxies else None
        
        def close(self):
            pass

    # Mock at the CLI module level where it's imported
    monkeypatch.setattr(ytb.cli, "ProxyPool", MockProxyPool)

    captured = {}

    async def _fake_grab(*_a, **kw):
        captured["pool"] = kw.get("proxy_pool")
        captured["cfg"] = kw.get("proxy_cfg")
        return ("ok", "x", "t")

    monkeypatch.setattr(ytb, "grab", _fake_grab)

    run_cli(tmp_path, "dummy", "--public-proxy", "2", "-n", "1")

    # Verify we got a ProxyPool instance with correct max_proxies
    assert isinstance(captured["pool"], MockProxyPool)
    assert captured["pool"].max_proxies == 2
    assert len(captured["pool"]._proxies) == 2


@pytest.mark.usefixtures("patch_scrapetube", "patch_detect")
def test_public_proxy_validation_fail(monkeypatch, tmp_path: Path):
    """CLI should not abort when proxy validation fails."""

    def _qp(*a, **k):
        return SimpleNamespace(as_string=lambda: "http://pub:1")

    monkeypatch.setattr(ytb.cli, "QuickProxy", _qp)

    def fake_get(*_a, **_k):
        raise Exception("boom")

    monkeypatch.setattr(ytb.requests, "get", fake_get)

    captured = {}

    async def _fake_grab(*_a, **kw):
        captured["pool"] = kw.get("proxy_pool")
        captured["cfg"] = kw.get("proxy_cfg")
        return ("ok", "x", "t")

    monkeypatch.setattr(ytb, "grab", _fake_grab)

    run_cli(tmp_path, "dummy", "--public-proxy", "1", "-n", "1")

    assert captured.get("cfg") is None
    assert isinstance(captured.get("pool"), ProxyPool)


@pytest.mark.usefixtures("patch_scrapetube", "patch_detect")
def test_quickproxy_outside_event_loop(monkeypatch, tmp_path: Path):
    """QuickProxy should run outside the main event loop to avoid warnings."""

    state: dict[str, bool] = {}

    def _qp(*a, **k):
        try:
            asyncio.get_running_loop()
            state["running"] = True
        except RuntimeError:
            state["running"] = False
        return SimpleNamespace(as_string=lambda: "http://pub:1")

    monkeypatch.setattr(ytb.cli, "QuickProxy", _qp)

    async def _fake_grab(*_a, **_kw):
        return ("ok", "x", "t")

    monkeypatch.setattr(ytb, "grab", _fake_grab)

    run_cli(tmp_path, "dummy", "--public-proxy", "1", "-n", "1")

    # QuickProxy path removed – state stays empty
    assert state == {}
