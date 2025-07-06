"""yt_bulk_cc.formatters – caption formatting helpers extracted from the
legacy script.
"""
from __future__ import annotations

from datetime import timedelta

from youtube_transcript_api import formatters as yt_fmt

__all__ = [
    "TimeStampedText",
    "FMT",
    "EXT",
]


class TimeStampedText(yt_fmt.TextFormatter):
    """Plain/pretty formatter that can prefix timestamps."""

    def __init__(self, show: bool = False):
        super().__init__()
        self.show = show

    @staticmethod
    def _ts(sec: float) -> str:
        td = timedelta(seconds=sec)
        base = f"{td}"
        if "." not in base:
            base += ".000000"
        h, m, rest = base.split(":")
        s, micro = rest.split(".")
        return f"{h}:{m}:{s}.{micro[:3]}"

    def format_transcript(self, transcript, **kw):  # type: ignore[override]
        if not self.show:
            return super().format_transcript(transcript, **kw)
        # yt_fmt base class expects attribute access
        return "\n".join(f"[{self._ts(c.start)}] {c.text}" for c in transcript)


FMT = {
    "srt": yt_fmt.SRTFormatter(),
    "webvtt": yt_fmt.WebVTTFormatter(),
    "text": TimeStampedText(),
    "pretty": TimeStampedText(),
}

EXT = {
    "json": "json",
    "srt": "srt",
    "webvtt": "vtt",
    "text": "txt",
    "pretty": "txt",
} 