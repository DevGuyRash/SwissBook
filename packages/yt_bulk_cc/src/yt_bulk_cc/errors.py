"""yt_bulk_cc.errors – compatibility wrappers around youtube-transcript-api
error classes.  New modules should import from here instead of digging into
private `_errors` internals.
"""
from __future__ import annotations

from importlib import import_module

_errors = import_module("youtube_transcript_api._errors")

CouldNotRetrieveTranscript = getattr(_errors, "CouldNotRetrieveTranscript")
NoTranscriptFound = getattr(_errors, "NoTranscriptFound")
TranscriptsDisabled = getattr(_errors, "TranscriptsDisabled")
VideoUnavailable = getattr(_errors, "VideoUnavailable")

# Optional classes – provide dummies if missing

class _Placeholder(Exception):
    """Stub used when the underlying library removed a class."""


NoTranscriptAvailable = getattr(_errors, "NoTranscriptAvailable", _Placeholder)
TooManyRequests = getattr(_errors, "TooManyRequests", _Placeholder)

__all__ = [
    "CouldNotRetrieveTranscript",
    "NoTranscriptFound",
    "TranscriptsDisabled",
    "VideoUnavailable",
    "NoTranscriptAvailable",
    "TooManyRequests",
] 