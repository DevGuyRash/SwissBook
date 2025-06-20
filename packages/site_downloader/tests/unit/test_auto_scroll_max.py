"""Edge‑case: _auto_scroll must stop at max_scrolls even if height grows."""

from site_downloader.fetcher import _auto_scroll


class _Page:
    def __init__(self, heights):
        self.heights = list(heights)
        self.reads = 0

    def evaluate(self, script):
        if "scrollHeight" in script and "scrollTo" not in script:
            self.reads += 1
            return self.heights.pop(0)
        return None


def test_max_scroll_cutoff():
    # 15 increasing heights but max_scrolls is 10 ⇒ stop after 10 reads
    page = _Page(list(range(1000, 2500, 100)))
    _auto_scroll(page, max_scrolls=10, pause=0)
    assert page.reads == 10
