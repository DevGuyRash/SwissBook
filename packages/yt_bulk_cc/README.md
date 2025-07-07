# 📺 YouTube Bulk CC Downloader (`yt_bulk_cc.py`)

A powerful Python script to bulk-download YouTube captions/transcripts for single videos, playlists, or entire channels. It requires no API key and can scrape public, members-only, and private content (with cookies).

This tool is designed to be run as a standalone script from the monorepo root.

---

## Features

- **Multiple Sources**: Download from single videos, playlists, and entire channels.
- **Versatile Formats**: Output to `json`, `srt`, `webvtt`, or plain `text`.
- **Concatenation**: Combine all transcripts from a run into a single file.
- **File Splitting**: Automatically split large concatenated files by word, line, or character count.
- **Built-in Converter**: Convert previously downloaded JSON transcripts to any other supported format.
- **Rich Statistics**: Get detailed stats in file headers and a final run summary.
- **Network Control**: Use HTTP proxies and provide browser cookies for authenticated sessions.
- **No API Key Needed**: Relies on `scrapetube` and `youtube-transcript-api`.

---

## Installation

This package is part of the SwissBook monorepo. From the repository root, run the main setup script, which will install this tool and its dependencies:

```bash
# This handles virtualenv creation and all dependencies
./setup.sh --dev

# Activate the environment (once per shell session)
source .venv/bin/activate
```

> For more details, see the [**main project README**](../../README.md).

---

## Usage

The script is invoked via `python -m yt_bulk_cc.yt_bulk_cc`.

#### Quick Examples

```bash
# 1. Download a single video's transcript as an SRT file
python -m yt_bulk_cc.yt_bulk_cc "https://youtu.be/dQw4w9WgXcQ" -f srt

# 2. Download an entire playlist as individual JSON files
python -m yt_bulk_cc.yt_bulk_cc "https://youtube.com/playlist?list=PLxyz123" -f json

# 3. Download all transcripts from a channel using its handle
python -m yt_bulk_cc.yt_bulk_cc "https://www.youtube.com/@Recipe4Porkchops"
```

The command produces a detailed summary and lists files that were successfully downloaded or skipped.

![Example Run](assets/yt_bulk_cc-example_01.png)

To combine these downloaded files, you can run the same command with the `--concat` flag. The script will find the existing files, skip the download process, and create a single combined file.

```bash
# 4. Concatenate the transcripts from the previous step
python -m yt_bulk_cc.yt_bulk_cc "https://www.youtube.com/@Recipe4Porkchops" --concat
```
![Example Concatenation Run](assets/yt_bulk_cc-example_02.png)

```bash
# 5. Concatenate all transcripts from a different channel into a single text file
python -m yt_bulk_cc.yt_bulk_cc "https://www.youtube.com/@CrashCourse" -f text --concat channel_output

# 6. Convert an existing directory of JSON files to SRT
python -m yt_bulk_cc.yt_bulk_cc --convert ./out -f srt -o ./out_srt
```

#### Command-Line Options

| Option                       | Argument        | Description                                                                                                                      |
| :--------------------------- | :-------------- | :------------------------------------------------------------------------------------------------------------------------------- |
| **Core Options**             |                 |                                                                                                                                  |
| `LINK`                       | _(url)_         | The positional argument for the video, playlist, or channel URL.                                                                 |
| `-o`, `--folder`             | _(path)_        | Destination directory for output files. Default: `.`                                                                             |
| `-l`, `--language`           | _(code)_        | Preferred language code (e.g., `en`, `es`). Can be repeated for fallback priority.                                               |
| `-f`, `--format`             | _(name)_        | Output format: `json`, `srt`, `webvtt`, `text`, `pretty`. Default: `json`.                                                       |
| `-n`, `--limit`              | _(int)_         | Stop after processing N videos from a playlist or channel.                                                                       |
| `-j`, `--jobs`               | _(int)_         | Number of concurrent transcript downloads. Default: `1`.                                                                         |
| **Output & Formatting**      |                 |                                                                                                                                  |
| `-t`, `--timestamps`         |                 | Adds `[hh:mm:ss.mmm]` timestamps to `text` format.                                                                               |
| `--no-seq-prefix`            |                 | Disables the `00001-` numeric prefix on filenames.                                                                               |
| `--stats`<br>`--no-stats`    |                 | Toggles the inclusion of statistics headers in output files. (Default: on)                                                       |
| `-C`, `--concat`             | _[basename]_    | Concatenate all results into a single file with an optional basename.                                                            |
| `--split`                    | _(e.g. 10000c)_ | With `--concat`, splits the output into new files when a size threshold is met.<br>Units: `w` (words), `l` (lines), `c` (chars). |
| **Network & Authentication** |                 |                                                                                                                                  |
| `-p`, `--proxy`              | _(url)_         | A single proxy URL or a comma-separated list to rotate through.                                                                  |
| `--proxy-file`              | _(file)_        | Load proxies from a file (one URL per line). |
| `-c`, `--cookie-json`, `--cookie-file`        | _(file)_        | Cookies JSON exported by your browser. |
| `-s`, `--sleep`              | _(int)_         | Seconds to wait between pagination requests when scraping. Default: `2`.                                                         |
| `--delay`                    | _(float)_       | Seconds to wait after each transcript download. |
| `--check-ip`                |                 | Preflight transcript fetch to detect IP bans before downloading. |
| **Utilities**                |                 |                                                                                                                                  |
| `--convert`                  | _(path)_        | Converts existing JSON transcripts from a file or directory to the specified `-f` format.                                        |
| `--overwrite`                |                 | Re-download and overwrite files even if they already exist.                                                                      |
| `-v`, `--verbose`            |                 | Increase console log verbosity (`-v` for INFO, `-vv` for DEBUG).                                                                 |
| `-L`, `--log-file`           | _(file)_        | Write a detailed run log to a specific file.                                                                                     |
| `--no-log`                   |                 | Disable file logging entirely.                                                                                                   |
| `-F`, `--formats-help`       |                 | Show examples of each output format and exit.                                                                                    |

---

## License

MIT © SwissBook contributors

## 🐍 Programmatic usage

As of v1.1, `yt_bulk_cc` is a proper Python package.  Instead of importing
from the giant legacy script, you can interact with focused, documented
sub-modules:

| Module                | Purpose                                      |
| --------------------- | -------------------------------------------- |
| `yt_bulk_cc.utils`    | Slugging, path shortening, URL detection, `stats()` helper |
| `yt_bulk_cc.formatters` | `TimeStampedText` plus `FMT`/`EXT` registries |
| `yt_bulk_cc.converter` | Convert downloaded JSON → SRT/WebVTT/Text, etc. |
| `yt_bulk_cc.core`     | High-level async helpers: `grab()` and `video_iter()` |
| `yt_bulk_cc.errors`   | Safe re-exports of transcript-API exception types |

Backward-compatibility: `import yt_bulk_cc as ytb` still works and re-exports
all public symbols, so existing code and the test-suite continue to run
unchanged.
