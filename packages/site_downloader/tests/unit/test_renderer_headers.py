"""
Mirror `test_network_passthrough` but for **renderer.render_page**.
"""

import json
import pathlib

from site_downloader import renderer


def test_extra_headers_propagate(monkeypatch):
    captured = {}

    class DummyPage:
        def goto(self, *a, **kw):
            pass

        def screenshot(self, *a, **kw):
            pass

        def emulate_media(self, *a, **kw):
            pass

        def pdf(self, *a, **kw):
            pass

    def _fake_new_page(*args, **kwargs):
        captured.update(kwargs)

        class _Ctx:
            def __enter__(self):
                return (None, None, DummyPage())

            def __exit__(self, *exc):
                pass

        return _Ctx()

    monkeypatch.setattr(renderer, "new_page", _fake_new_page)

    hdrs = json.dumps({"X-Demo": "1"})
    renderer.render_page("https://example.com", pathlib.Path("out.pdf"), headers_json=hdrs)

    assert captured["extra_headers"]["X-Demo"] == "1"
