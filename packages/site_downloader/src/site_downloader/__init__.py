"""Public package API."""

from .proxy import ProxyPool  # re-export for external users

__all__ = [*globals().get("__all__", []), "ProxyPool"]
__version__ = "0.2.0"
