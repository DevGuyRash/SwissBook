"""yt_bulk_cc.cli
Entry-point module that delegates to the original implementation.
This indirection lets us change internals without breaking the
console-script registered in *pyproject.toml*.
"""
from __future__ import annotations

from asyncio import run as _run
from importlib import import_module as _imp

# Lazily import the legacy implementation only when invoked.
_legacy = _imp(".yt_bulk_cc", package=__name__.rsplit(".", 1)[0])

main = _legacy.main  # type: ignore[attr-defined]
cli_entry = _legacy.cli_entry  # type: ignore[attr-defined]

# If you run ``python -m yt_bulk_cc.cli`` directly, execute the program.
if __name__ == "__main__":
    _run(main()) 