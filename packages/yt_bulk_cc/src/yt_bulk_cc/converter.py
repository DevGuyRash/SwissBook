"""yt_bulk_cc.converter
Expose the `convert_existing` helper so callers don't have to reach into
private modules.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable

from .formatters import FMT, EXT
from .utils import stats, detect, coerce_attr  # re-exported for convenience

__all__ = [
    "convert_existing",
    "iter_json_files",
    "coerce_attr",
    "extract_cues",
]

# ---------------------------------------------------------------------------
# Helper generators / transformers
# ---------------------------------------------------------------------------

def iter_json_files(path: Path | str) -> Iterable[Path]:
    """Yield every *.json* file under *path* (file or directory)."""
    p = Path(path).expanduser()
    if p.is_file() and p.suffix.lower() == ".json":
        yield p
    elif p.is_dir():
        yield from p.rglob("*.json")




# Recursive flatten helper ----------------------------------------------------

def extract_cues(blob):
    """Return a flat list of cues from a single- or multi-video JSON object."""
    if "transcript" in blob:
        return blob["transcript"]
    if "items" in blob:
        cues: list = []
        for item in blob["items"]:
            cues.extend(extract_cues(item))
        return cues
    return []


# ---------------------------------------------------------------------------
# Public conversion API
# ---------------------------------------------------------------------------

def convert_existing(src: str | Path, dest_fmt: str, out_dir: Path, *, include_stats: bool = True) -> None:
    """Convert previously downloaded JSON transcript(s) to *dest_fmt*.

    Parameters
    ----------
    src
        Source file or directory containing one or more ``.json`` files.
    dest_fmt
        Target format key in ``FMT`` – e.g. ``"srt"``, ``"webvtt"``, ``"text"``.
    out_dir
        Destination directory for converted files (will be created).
    include_stats
        If *True* and the format supports it, prepend a stats header.
    """
    from .formatters import FMT, EXT
    from . import _stats as _legacy_stats, _fixup_loop, _single_file_header  # type: ignore

    out_dir.mkdir(parents=True, exist_ok=True)
    dest_ext = EXT[dest_fmt]

    for jfile in iter_json_files(src):
        try:
            data = json.loads(jfile.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover – corrupt file
            logging.warning("Skip unreadable JSON %s (%s)", jfile, exc)
            continue

        cues = extract_cues(data)
        if not cues:
            logging.warning("No cues in %s", jfile)
            continue

        if dest_fmt == "json":
            new_txt = json.dumps(data, ensure_ascii=False, indent=2)
            if not new_txt.endswith("\n"):
                new_txt += "\n"
        else:
            many_srt = dest_fmt == "srt" and "items" in data and len(data["items"]) > 2

            def _render_one(meta: dict, cue_list):
                txt = FMT[dest_fmt].format_transcript(coerce_attr(cue_list))
                if include_stats and not many_srt:
                    txt = _single_file_header(dest_fmt, txt, meta)
                return txt

            if "items" in data:  # concatenated JSON
                parts, meta_acc = [], []
                for item in data["items"]:
                    meta = {k: item[k] for k in ("video_id", "title", "url")}
                    if not many_srt:
                        parts.append("──── {video_id} ── {title}\n".format(**meta))
                    parts.append(_render_one(meta, item["transcript"]))
                    meta_acc.append((meta["video_id"], meta["title"]))
                body = "\n".join(parts)

                if include_stats and not many_srt:
                    hdr, *_ = _fixup_loop(stats(body), dest_fmt, meta_acc)  # type: ignore[arg-type]
                    new_txt = hdr + body
                else:
                    new_txt = body
            else:  # single-video JSON
                meta = {k: data[k] for k in ("video_id", "title", "url")}
                new_txt = _render_one(meta, cues)

        dst = out_dir / jfile.with_suffix(f".{dest_ext}").name
        dst.write_text(new_txt, encoding="utf-8")
        logging.info("✔ converted %s → %s", jfile.name, dst.name) 