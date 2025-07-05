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