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

import logging
import os

_LEVEL = os.getenv("SDL_LOGLEVEL", "INFO").upper()
logging.basicConfig(
    level=_LEVEL,
    format="%(asctime)s  %(levelname)-8s  %(name)s › %(message)s",
)

log = logging.getLogger("site_downloader")
