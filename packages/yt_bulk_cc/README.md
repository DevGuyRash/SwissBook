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

This package is part of the SwissBook monorepo. From the repository root, run:

```bash
# Create and activate a virtual environment (if not already done)
uv venv .venv
source .venv/bin/activate

# Install the script and its dependencies in editable mode
uv pip install -e "packages/yt_bulk_cc"
```

---

## Usage

The script is invoked via `python -m yt_bulk_cc.yt_bulk_cc`.

#### Quick Examples

```bash
# 1. Download a single video's transcript as an SRT file
python -m yt_bulk_cc.yt_bulk_cc "https://youtu.be/dQw4w9WgXcQ" -f srt

# 2. Download an entire playlist as individual JSON files
python -m yt_bulk_cc.yt_bulk_cc "https://youtube.com/playlist?list=PLxyz123" -f json

# 3. Concatenate all transcripts from a channel into a single text file
python -m yt_bulk_cc.yt_bulk_cc "https://www.youtube.com/@CrashCourse/videos" -f text --concat channel_output

# 4. Convert an existing directory of JSON files to SRT
python -m yt_bulk_cc.yt_bulk_cc --convert ./out -f srt -o ./out_srt
```

#### Command-Line Options

| Option | Argument | Description |
| :--- | :--- | :--- |
| **Core Options** | | |
| `LINK` | _(url)_ | The positional argument for the video, playlist, or channel URL. |
| `-o`, `--folder` | _(path)_ | Destination directory for output files. Default: `.` |
| `-l`, `--language` | _(code)_ | Preferred language code (e.g., `en`, `es`). Can be repeated for fallback priority. |
| `-f`, `--format` | _(name)_ | Output format: `json`, `srt`, `webvtt`, `text`, `pretty`. Default: `json`. |
| `-n`, `--limit` | _(int)_ | Stop after processing N videos from a playlist or channel. |
| `-j`, `--jobs` | _(int)_ | Number of concurrent transcript downloads. Default: `2`. |
| **Output & Formatting** | | |
| `-t`, `--timestamps` | | Adds `[hh:mm:ss.mmm]` timestamps to `text` format. |
| `--no-seq-prefix` | | Disables the `00001-` numeric prefix on filenames. |
| `--stats`<br>`--no-stats` | | Toggles the inclusion of statistics headers in output files. (Default: on) |
| `-C`, `--concat` | _[basename]_ | Concatenate all results into a single file with an optional basename. |
| `--split` | _(e.g. 10000c)_ | With `--concat`, splits the output into new files when a size threshold is met.<br>Units: `w` (words), `l` (lines), `c` (chars). |
| **Network & Authentication** | | |
| `-p`, `--proxy` | _(url)_ | A single proxy URL or a comma-separated list to rotate through. |
| `-c`, `--cookie-json` | _(file)_ | Path to a cookies JSON file for accessing private/members-only content. |
| `-s`, `--sleep` | _(int)_ | Seconds to wait between pagination requests when scraping. Default: `2`. |
| **Utilities** | | |
| `--convert` | _(path)_ | Converts existing JSON transcripts from a file or directory to the specified `-f` format. |
| `--overwrite` | | Re-download and overwrite files even if they already exist. |
| `-v`, `--verbose` | | Increase console log verbosity (`-v` for INFO, `-vv` for DEBUG). |
| `-L`, `--log-file` | _(file)_ | Write a detailed run log to a specific file. |
| `--no-log` | | Disable file logging entirely. |
| `-F`, `--formats-help` | | Show examples of each output format and exit. |

---

## License

MIT © SwissBook contributors