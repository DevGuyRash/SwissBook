import pathlib, shutil, subprocess, sys

import pytest

from ..conftest import run_cli, touch


@pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc required")
@pytest.mark.parametrize("fmt", ["docx", "epub"])
def test_html_to_binary(tmp_path: pathlib.Path, fmt):
    html = tmp_path / "page.html"
    html.write_text("<h2>Hello</h2>")
    out = tmp_path / f"out.{fmt}"
    run_cli("grab", str(html), "-f", fmt, "-o", str(out))
    assert out.exists() and out.stat().st_size > 20
