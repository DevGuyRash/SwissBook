# 📺 YouTube Bulk CC Downloader (`yt-bulk-cc`)

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

The command line interface installs as `yt-bulk-cc`. You can also run it via
`python -m yt_bulk_cc`.

### Quick Examples

```bash
# 1. Download a single video's transcript as an SRT file
yt-bulk-cc "https://youtu.be/dQw4w9WgXcQ" -f srt

# 2. Download an entire playlist as individual JSON files
yt-bulk-cc "https://youtube.com/playlist?list=PLxyz123" -f json

# 3. Download all transcripts from a channel using its handle
yt-bulk-cc "https://www.youtube.com/@Recipe4Porkchops"
```

The command produces a detailed summary and lists files that were successfully downloaded or skipped.

![Example Run](assets/yt_bulk_cc-example_01.png)

To combine these downloaded files, you can run the same command with the `--concat` flag. The script will find the existing files, skip the download process, and create a single combined file.

```bash
# 4. Concatenate the transcripts from the previous step
yt-bulk-cc "https://www.youtube.com/@Recipe4Porkchops" --concat
```

![Example Concatenation Run](assets/yt_bulk_cc-example_02.png)

```bash
# 5. Concatenate all transcripts from a different channel into a single text file
yt-bulk-cc "https://www.youtube.com/@CrashCourse" -f text --concat channel_output

# 6. Convert an existing directory of JSON files to SRT
yt-bulk-cc --convert ./out -f srt -o ./out_srt
```

### Command-Line Options

| Option                                 | Argument               | Description                                                                                                                      |
| :------------------------------------- | :--------------------- | :------------------------------------------------------------------------------------------------------------------------------- |
| **Core Options**                       |                        |                                                                                                                                  |
| `LINK`                                 | _(url)_                | The positional argument for the video, playlist, or channel URL.                                                                 |
| `-o`, `--folder`                       | _(path)_               | Destination directory for output files. Default: `.`                                                                             |
| `-l`, `--language`                     | _(code)_               | Preferred language code (e.g., `en`, `es`). Can be repeated for fallback priority.                                               |
| `-f`, `--format`                       | _(name)_               | Output format: `json`, `srt`, `webvtt`, `text`, `pretty`. Default: `json`.                                                       |
| `-n`, `--limit`                        | _(int)_                | Stop after processing N videos from a playlist or channel.                                                                       |
| `-j`, `--jobs`                         | _(int)_                | Number of concurrent transcript downloads. Default: `1`.                                                                         |
| **Output & Formatting**                |                        |                                                                                                                                  |
| `-t`, `--timestamps`                   |                        | Adds `[hh:mm:ss.mmm]` timestamps to `text` format.                                                                               |
| `--no-seq-prefix`                      |                        | Disables the `00001-` numeric prefix on filenames.                                                                               |
| `--stats`<br>`--no-stats`              |                        | Enable or disable statistics headers in output files. Stats are on by default; use `--no-stats` to turn them off or `--stats` to override a disabled configuration. |
| `-C`, `--concat`                       |                        | Concatenate all results into a single file.                                                                                      |
| `--basename`                           | _(name)_               | Base filename for concatenated output. Default: `combined`.                                                                      |
| `--split`                              | _(e.g. 10000c)_        | With `--concat`, splits the output into new files when a size threshold is met.<br>Units: `w` (words), `l` (lines), `c` (chars). |
| `--stats-top`                          | _N_                    | Limit file statistics in the final summary to the top N entries.                                                                 |
| **Network & Authentication**           |                        |                                                                                                                                  |
| `-p`, `--proxy`                        | _(url)_                | Single proxy URL or comma-separated list to rotate through. Use `ws://user:pass` for Webshare.                                   |
| `--proxy-file`                         | _(file)_               | Load additional proxies from a file (one URL per line).                                                                          |
| `--public-proxy [N]`                   |                        | Fetch N free proxies (default 5) using Swiftshadow or a SOCKS list.                                                              |
| `--public-proxy-country`               | _(CC[,CC])_            | Restrict public proxies to these country codes.                                                                                  |
| `--public-proxy-type`                  | _(http\|https\|socks)_ | Protocol for public proxies. Auto-selected if omitted.                                                                           |
| `-c`, `--cookie-json`, `--cookie-file` | _(file)_               | Cookies JSON exported with a browser extension (see below).                                                                      |
| `-s`, `--sleep`                        | _(float)_              | Seconds to wait between playlist requests and after each transcript. Default: `2`.                                               |
| `--check-ip`                           |                        | Preflight transcript fetch to detect IP bans before downloading.                                                                 |
| **Utilities**                          |                        |                                                                                                                                  |
| `--convert`                            | _(path)_               | Converts existing JSON transcripts from a file or directory to the specified `-f` format.                                        |
| `--overwrite`                          |                        | Re-download and overwrite files even if they already exist.                                                                      |
| `-v`, `--verbose`                      |                        | Increase console log verbosity (`-v` for INFO, `-vv` for DEBUG).                                                                 |
| `-L`, `--log-file`                     | _(file)_               | Write a detailed run log to a specific file.                                                                                     |
| `--no-log`                             |                        | Disable file logging entirely.                                                                                                   |
| `-F`, `--formats-help`                 |                        | Show examples of each output format and exit.
                                     |

> **Note**
> The table above reflects the current command-line options. If you notice discrepancies in older docs or screenshots, this README is authoritative.

### Proxy usage

Use `-p`/`--proxy` and `--proxy-file` to provide a single proxy or a rotation list. Each URL may include credentials, for example `http://user:pass@host:port`. To use Webshare residential proxies pass `ws://USER:PASS` as the proxy URL. With `--public-proxy` the tool fetches a small pool of free proxies; you can pass a number as `--public-proxy N` or `--public-proxy=N` (default 5). These are retrieved one-by-one via Swiftshadow's `QuickProxy` helper so the tool never downloads more proxies than requested. Use `--public-proxy-country` and `--public-proxy-type` to refine the pool. User-supplied proxies always take precedence, with public ones used as a fallback. At startup the tool logs how many proxies came from the CLI and how many were loaded from a file. With `-v` you'll see which proxy is used for each request and when one gets banned. The logfile (created automatically unless `--no-log` is used) always records the full `-vv` debug output, so detailed retry information is preserved even if the console is less verbose.

### Checking for IP bans

Use `--check-ip` to run a quick probe before downloading. The script fetches the first video's transcript with your selected proxy settings and exits early if it detects an IP ban. Because this extra request adds a small startup delay, it is opt-in rather than the default.

### Exporting cookies

Use a browser extension like **Get cookies.txt** for Chrome or Firefox:

1. Log into YouTube in your browser.
2. Choose **Export as JSON** for `youtube.com` in the extension menu.
3. Save the file (e.g. `cookies.json`) and pass it with `-c cookies.json`.

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
