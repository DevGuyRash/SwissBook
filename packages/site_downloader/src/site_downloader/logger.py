"""
Tiny façade over :pymod:`logging` so internal modules can do

```python
from site_downloader.logger import log
log.debug("Hi")
```

and end-users can tweak verbosity via the environment:

```bash
export SDL_LOGLEVEL=DEBUG
```
"""

import logging, os

_FMT = "%(asctime)s  %(levelname)-8s  %(name)s › %(message)s"
_ENV_LEVEL = os.getenv("SDL_LOGLEVEL")

def configure_logging(verbose: int) -> None:
    """
    Initialize root logging once. If SDL_LOGLEVEL is set it overrides verbosity.
    Verbosity: 0/1 => INFO, >=2 => DEBUG.
    """
    root = logging.getLogger()
    if root.handlers:
        return
    if _ENV_LEVEL:
        level = getattr(logging, _ENV_LEVEL.upper(), logging.INFO)
    else:
        level = logging.DEBUG if verbose >= 2 else logging.INFO
    logging.basicConfig(level=level, format=_FMT)

log = logging.getLogger("site_downloader")
