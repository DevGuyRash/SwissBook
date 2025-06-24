from site_downloader.fetcher import _auto_scroll


class _DummyPage:
    """
    Fake Playwright page for auto-scroll testing.

    • We *only* consume one number per read of ``document.body.scrollHeight``.  
    • Calls that merely *scroll* the page must not consume the list.
    """

    def __init__(self, heights):
        self._heights = list(heights)
        self.calls = 0

    def evaluate(self, script):
        # only count height *reads* (same metric original test expects)
        if "scrollTo" not in script and "scrollHeight" in script:
            self.calls += 1
            return self._heights.pop(0)
        # it's a scroll instruction, nothing to pop / return or count
        return None


def test_auto_scroll_stops_when_height_stable():
    page = _DummyPage([800, 1200, 1200])  # stabilises on 3rd call
    _auto_scroll(page, max_scrolls=10, pause=0)
    assert page.calls == 3
