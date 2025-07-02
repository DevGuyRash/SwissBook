"""
Spin-up / tear-down of the official Playwright Docker image.

Only used when:
    • env SDL_PLAYWRIGHT_DOCKER=1   OR
    • CLI flag --docker             OR
    • browser.new_page(..., use_docker=True)
"""

from __future__ import annotations
import contextlib, os, socket, random
from typing import Dict

try:
    import docker  # type: ignore
except ModuleNotFoundError:
    docker = None

# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #
_IMAGE        = "mcr.microsoft.com/playwright:v1.44.0-focal"
_REMOTE_PORT  = 9222                           # inside the container
# How long we wait for Chrome ⇆ CDP to become available
# Cold starts on CI runners (image pull + first‑run) often need >30 s.
_STARTUP_TIMEOUT = max(45, int(os.getenv("SDL_DOCKER_TIMEOUT", "30")))  # seconds

# ── helpers --------------------------------------------------------------- #
def _free_port(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0

def _pick_host_port() -> int:
    """
    Pick a *free* TCP port – prefer the canonical 9222‑9232 range so Docker
    rules (firewalls, SELinux…) that were already opened for Playwright keep
    working, but fall back to the OS‑allocated ephemeral range when needed
    (xdist → many parallel workers).
    """
    preferred = list(range(9222, 9233))
    random.shuffle(preferred)
    for p in preferred + [0]:             # 0 ⇒ "ask the OS to pick"
        if p == 0:         # let the kernel decide, then reuse the port
            with socket.socket() as s:
                s.bind(("", 0))
                return s.getsockname()[1]
        if _free_port(p):
            return p
    raise RuntimeError("No free TCP port found for the Playwright container")

@contextlib.contextmanager
def docker_chromium() -> Dict[str, str]:
    """
    Yield mapping for CDP connect:
        {"wsEndpoint": "<ws-url>"}
    """
    if docker is None:
        raise RuntimeError(
            "`docker` extras not installed – pip install site_downloader[docker]"
        )

    client = docker.from_env()

    def _safe_kill(c):
        from docker.errors import APIError, NotFound
        try:
            c.reload()
        except (APIError, NotFound):
            return
        if c.status == "running":
            with contextlib.suppress(APIError, NotFound, Exception):
                c.kill()

    host_port = _pick_host_port()

    # Shell snippet that *first* tries the Playwright‑bundled browser, then
    # falls back to anything discoverable on $PATH.  This avoids the Ubuntu
    # "snap wrapper" that exits instantly and broke our previous attempt.
    launch_script = rf"""
        set -eo pipefail
        CHROME=""
        # 1) Prefer the browser that Playwright pre‑installs
        for C in /ms-playwright/chromium-*/chrome-linux/chrome; do
          [ -x "$C" ] && CHROME="$C" && break
        done
        # 2) Last‑ditch fall‑back: anything on $PATH that *actually* runs
        if [ -z "$CHROME" ]; then
          for BIN in chromium chromium-browser google-chrome google-chrome-stable; do
            if command -v "$BIN" >/dev/null 2>&1; then
              # Weed‑out Ubuntu's snap stub (it prints and exits with code 10)
              if "$BIN" --version >/dev/null 2>&1; then CHROME="$BIN"; break; fi
            fi
          done
        fi

        [ -n "$CHROME" ] || {{ echo '❌  No usable Chrome binary found.' >&2; exit 1; }}

        exec "$CHROME" \
          --headless \
          --remote-debugging-host=0.0.0.0 \
          --remote-debugging-address=0.0.0.0 \
          --remote-debugging-port={_REMOTE_PORT} \
          --disable-gpu \
          --disable-dev-shm-usage \
          --no-sandbox \
          about:blank
    """

    # The Playwright base images ship with Bash; we therefore stick to it so
    # `set -eo pipefail` works as intended.
    docker_cmd = ["bash", "-c", launch_script]
    container = client.containers.run(
        _IMAGE,
        docker_cmd,
        detach=True,
        ports={f"{_REMOTE_PORT}/tcp": host_port},
        auto_remove=True,
    )

    # Docker might have had to re-assign the host port (rootless or if the
    # chosen port got occupied in the meantime).  Pick the one Docker really
    # gave us.
    try:
        container.reload()
        port_info = container.attrs["NetworkSettings"]["Ports"]
        real_port = int(port_info[f"{_REMOTE_PORT}/tcp"][0]["HostPort"])
        host_port = real_port
    except Exception:
        # fall back to the port we requested – old Docker (<20.10) does not
        # populate `Ports` until the container is running a little while.
        pass

    # wait for endpoint
    endpoint = f"http://127.0.0.1:{host_port}/json/version"
    import urllib.request, json, time

    # Disable proxies *just* for the CDP health-check – otherwise we will try
    # to send 127.0.0.1 through the corporate proxy and time-out.
    _no_proxy_opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({})
    )

    # Allow overriding startup timeout via SDL_DOCKER_TIMEOUT (in seconds)
    timeout = int(os.environ.get("SDL_DOCKER_TIMEOUT", _STARTUP_TIMEOUT))
    t0 = time.time()
    ws: str | None = None
    while time.time() - t0 < timeout:
        try:
            with _no_proxy_opener.open(endpoint, timeout=1) as r:
                ws = json.load(r)["webSocketDebuggerUrl"]
                break
        except Exception:
            time.sleep(0.25)

    if ws is None:
        # Grab what the browser wrote to the console – that normally
        # contains the root-cause (missing library, flag not recognised,
        # etc.).  We still kill the container so we do not leak it.
        logs = ""
        with contextlib.suppress(Exception):
            logs = container.logs(stdout=True, stderr=True, tail=200).decode()
        _safe_kill(container)
        raise RuntimeError(
            "Chrome did not expose CDP within "
            f"{timeout}s\n\n--- container log tail ---\n{logs}"
        )

    try:
        yield {"wsEndpoint": ws}
    finally:
        _safe_kill(container) 