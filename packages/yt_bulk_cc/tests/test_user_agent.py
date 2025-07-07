import pytest
from unittest.mock import patch, MagicMock

from yt_bulk_cc.user_agent import _pick_ua


def test_ua_browser_filter():
    mock_ua = MagicMock()
    mock_ua.random = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123.0.0.0"
    with patch('yt_bulk_cc.user_agent.UserAgent', return_value=mock_ua) as mock_cls:
        ua = _pick_ua(browser="chrome")
        assert "Chrome" in ua
        mock_cls.assert_called_once_with(browsers=["chrome"], os=None)


def test_ua_os_filter():
    mock_ua = MagicMock()
    mock_ua.random = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123.0.0.0"
    with patch('yt_bulk_cc.user_agent.UserAgent', return_value=mock_ua) as mock_cls:
        ua = _pick_ua(os="windows")
        assert "Windows" in ua
        mock_cls.assert_called_once_with(browsers=None, os=["windows"])


def test_ua_fallback():
    def mock_init(*args, **kwargs):
        raise Exception("Network error")

    with patch('yt_bulk_cc.user_agent.UserAgent.__init__', side_effect=mock_init):
        with patch('yt_bulk_cc.user_agent._Faker.user_agent', return_value="fallback-ua") as mock_faker:
            ua = _pick_ua()
            assert ua == "fallback-ua"
            mock_faker.assert_called_once()


def test_ua_no_filters():
    mock_ua = MagicMock()
    mock_ua.random = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123.0.0.0"
    with patch('yt_bulk_cc.user_agent.UserAgent', return_value=mock_ua) as mock_cls:
        ua = _pick_ua()
        assert ua is not None
        mock_cls.assert_called_once_with(browsers=None, os=None)



def test_ua_invoked_when_unpatched(monkeypatch):
    called = {}
    class DummyUA:
        def __init__(self, *a, **kw):
            called['kw'] = kw
        @property
        def random(self):
            return 'dummy-UA'
    monkeypatch.setattr('yt_bulk_cc.user_agent.UserAgent', DummyUA)
    ua = _pick_ua()
    assert ua == 'dummy-UA'
    assert called['kw'] == {'browsers': None, 'os': None}
