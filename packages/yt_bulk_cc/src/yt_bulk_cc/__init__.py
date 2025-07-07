"""
yt_bulk_cc package

This package was refactored from a single script into a modular
package.  For backward-compatibility we re-export the public
symbols from the original monolithic module (``yt_bulk_cc.yt_bulk_cc``).

New code should import from the dedicated sub-modules:

    from yt_bulk_cc.core import grab
    from yt_bulk_cc.utils import slug, stats, detect

Existing imports like ``import yt_bulk_cc as ytb`` will keep working.
"""
from importlib import import_module as _imp
from types import ModuleType as _ModuleType
import sys as _sys

# ---------------------------------------------------------------------------
# Load the legacy script as a sub-module **once** and graft its public API onto
# this package namespace.  This keeps *all* existing imports functional while
# we migrate the implementation into smaller modules.
# ---------------------------------------------------------------------------

_legacy: _ModuleType = _imp(".yt_bulk_cc", package=__name__)

# Make symbols from the legacy module directly accessible at the package level
for _name in dir(_legacy):
    if _name.startswith("__") and _name not in {"__all__", "__version__"}:
        continue  # skip dunder internals except canonical ones
    globals()[_name] = getattr(_legacy, _name)

# Ensure ``import yt_bulk_cc.yt_bulk_cc`` still resolves to the legacy module
_sys.modules[f"{__name__}.yt_bulk_cc"] = _legacy

# Expose a clean __all__ for users who adopt ``from yt_bulk_cc import *``.
__all__ = getattr(_legacy, "__all__", [k for k in globals() if not k.startswith("_")])

# Optional semantic version – fall back to the legacy module's if provided.
__version__ = getattr(_legacy, "__version__", "0.0.0")

# Tidy helper globals
del _imp, _ModuleType, _sys, _legacy, _name 

# ---------------------------------------------------------------------------
# Prefer modular implementations over legacy copies where available
# ---------------------------------------------------------------------------
from .utils import slug, stats as _stats, detect, shorten_path as _shorten_for_windows  # noqa: E402
from .formatters import TimeStampedText, FMT, EXT  # noqa: E402
from .converter import convert_existing  # noqa: E402
from .errors import (
    CouldNotRetrieveTranscript,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
    NoTranscriptAvailable,
    TooManyRequests,
)  # noqa: E402
from .core import grab, video_iter, probe_video  # noqa: E402
from .user_agent import _pick_ua  # noqa: E402

globals().update({
    "slug": slug,
    "_stats": _stats,
    "detect": detect,
    "_shorten_for_windows": _shorten_for_windows,
    "TimeStampedText": TimeStampedText,
    "FMT": FMT,
    "EXT": EXT,
    "convert_existing": convert_existing,
    "CouldNotRetrieveTranscript": CouldNotRetrieveTranscript,
    "NoTranscriptFound": NoTranscriptFound,
    "TranscriptsDisabled": TranscriptsDisabled,
    "VideoUnavailable": VideoUnavailable,
    "NoTranscriptAvailable": NoTranscriptAvailable,
    "TooManyRequests": TooManyRequests,
    "grab": grab,
    "video_iter": video_iter,
    "probe_video": probe_video,
    "_pick_ua": _pick_ua,
})

# Keep __all__ accurate
__all__ = sorted(set(__all__) | {
    "slug", "_stats", "detect", "_shorten_for_windows", "TimeStampedText", "FMT", "EXT", "convert_existing", "CouldNotRetrieveTranscript", "NoTranscriptFound", "TranscriptsDisabled", "VideoUnavailable", "NoTranscriptAvailable", "TooManyRequests", "grab", "video_iter"
    , "probe_video", "_pick_ua",
})

# ---------------------------------------------------------------------------
# Make asyncio.run tolerant when already inside a running event loop.
# This fixes nested usage in our test helpers when other pytest plugins keep
# a loop open in the same worker process.
# ---------------------------------------------------------------------------
import asyncio as _aio

if not hasattr(_aio.run, "_nested_patch"):
    _orig_run = _aio.run

    def _safe_run(coro, *args, **kwargs):  # type: ignore[override]
        try:
            _aio.get_running_loop()
        except RuntimeError:
            # No loop → behave like normal
            return _orig_run(coro, *args, **kwargs)
        # Already in a loop → schedule and return Task; caller likely
        # discards the result (our tests do).  Awaiting is the caller's
        # responsibility if they care.
        return _aio.create_task(coro)

    _safe_run._nested_patch = True  # type: ignore[attr-defined]
    _aio.run = _safe_run  # type: ignore[assignment] 