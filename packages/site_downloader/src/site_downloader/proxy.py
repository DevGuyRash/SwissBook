"""
Proxy-rotation helper.
Accepts *one* of:
• single URL            (``--proxy``)
• CSV string            (``--proxies``)
• file with 1/line      (``--proxy-file``)
Returns an **infinite** iterator (cycle) of proxies or ``None``.
"""

from __future__ import annotations

import asyncio
import itertools
import pathlib
import requests
from typing import Iterator, Optional
from random import choice
from threading import Thread

try:  # pragma: no cover - optional dependency
    from swiftshadow.classes import ProxyInterface  # type: ignore
except Exception:  # pragma: no cover - swiftshadow not installed
    ProxyInterface = None  # type: ignore


def _iter_from_file(path: str | pathlib.Path) -> list[str]:
    lines = pathlib.Path(path).read_text().splitlines()
    return [ln.strip() for ln in lines if ln.strip()]


def _running_loop() -> bool:
    try:
        return asyncio.get_running_loop().is_running()
    except RuntimeError:
        return False


def _in_thread(fn):
    result: list[str] = []

    def _wrap() -> None:
        nonlocal result
        result = fn()

    t = Thread(target=_wrap)
    t.start()
    t.join()
    return result


def pool(
    single: Optional[str] = None,
    csv: Optional[str] = None,
    list_file: Optional[str | pathlib.Path] = None,
    *,
    public_proxy: int | None = None,
    public_proxy_country: str | None = None,
    public_proxy_type: str | None = None,
) -> Iterator[str | None]:
    proxies: list[str] = []

    if single:
        proxies.append(single)
    if csv:
        proxies.extend(p.strip() for p in csv.split(",") if p.strip())
    if list_file:
        proxies.extend(_iter_from_file(list_file))

    if public_proxy is not None:
        countries: list[str] = []
        if public_proxy_country:
            countries = [c.strip().upper() for c in public_proxy_country.split(',') if c.strip()]

        if public_proxy_type is None:
            if ProxyInterface is None:
                public_proxy_type = "socks"
            else:
                public_proxy_type = choice(["http", "https"])
        elif public_proxy_type in {"http", "https"} and ProxyInterface is None:
            public_proxy_type = "socks"

        if public_proxy_type == "socks":
            try:
                resp = requests.get(
                    "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt",
                    timeout=10,
                )
                resp.raise_for_status()
                lines = [ln.strip() for ln in resp.text.splitlines() if ln.strip()]
                proxies.extend(f"socks5://{ln}" for ln in lines[:public_proxy])
            except Exception:
                pass
        else:
            if ProxyInterface is not None:
                def _fetch() -> list[str]:
                    mgr = ProxyInterface(
                        countries=countries,
                        protocol=public_proxy_type,
                        maxProxies=public_proxy,
                    )
                    return [p.as_string() for p in mgr.proxies]

                try:
                    if _running_loop():
                        proxies.extend(_in_thread(_fetch))
                    else:
                        proxies.extend(_fetch())
                except Exception:
                    pass

    if not proxies:
        proxies.append(None)

    return itertools.cycle(proxies)
