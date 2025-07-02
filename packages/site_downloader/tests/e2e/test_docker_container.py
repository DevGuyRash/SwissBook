"""
Full end‑to‑end validation of the **Docker‑based Playwright** flow.

The test is automatically **skipped** when:
* the Docker daemon is not reachable, or
* Playwright (or its browser binaries) is missing.

It is tagged with the existing `e2e` marker, so regular CI runs (`pytest -q`)
remain fast; invoke with `pytest -m e2e` (or set `CI_E2E=1`) to execute.
"""

import importlib.util
import pathlib

import pytest

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.serial,         # avoid concurrent containers on the CI runner
]

# --------------------------------------------------------------------------- #
#  Fast bail‑out when prerequisites are missing                               #
# --------------------------------------------------------------------------- #

# 1 ) Docker library
docker = pytest.importorskip("docker", reason="python‑docker not installed")


def _docker_available() -> bool:
    try:
        docker.from_env().ping()
        return True
    except Exception:
        return False


# skip if Docker dæmon is not available *or* Playwright PyPkg missing
if not _docker_available() or importlib.util.find_spec("playwright") is None:
    pytest.skip("Docker / Playwright not available", allow_module_level=True)

# --------------------------------------------------------------------------- #
#  Real rendering                                                             #
# --------------------------------------------------------------------------- #

from site_downloader.renderer import render_page


@pytest.mark.parametrize("fmt", ["png", "pdf"])
def test_docker_render(tmp_path: pathlib.Path, fmt: str) -> None:
    """Render *example.com* inside the Playwright Docker image."""

    out = tmp_path / f"example.{fmt}"
    render_page(
        "https://example.com",
        out,
        engine="chromium",
        use_docker=True,
    )

    if fmt == "png":
        assert out.exists() and out.stat().st_size > 0
    else:  # pdf
        assert out.with_suffix(".screen.pdf").exists()
        assert out.with_suffix(".print.pdf").exists() 