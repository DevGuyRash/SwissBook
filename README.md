# SwissBook Monorepo

A grab-bag of command-line utilities written in Python. Everything lives in a **single repo** so it's easy to version, share, and hack on-even when the utilities have nothing to do with one another.

---

## 🛠️ Available Tools

This repository currently contains the following standalone tools:

| Tool                | CLI             | Description                                                                                                                                   | Documentation                                                                  |
| :------------------ | :-------------- | :-------------------------------------------------------------------------------------------------------------------------------------------- | :----------------------------------------------------------------------------- |
| **Site Downloader** | `sdl`           | A versatile web page downloader and converter. It fetches, cleans, and converts pages to PDF, PNG, Markdown, DOCX, and more using Playwright. | [**`packages/site_downloader/README.md`**](packages/site_downloader/README.md) |
| **YouTube Bulk CC** | `yt_bulk_cc.py` | A script to bulk-download YouTube transcripts for single videos, playlists, or entire channels-no API key required.                           | See built-in help (`--help`)                                                   |

---

## 📁 Directory layout

.
+-- packages/ # One sub-folder per language-specific package or library
+-- README.md

| Folder      | Purpose                                                                                                                                       | Typical contents                  |
| :---------- | :-------------------------------------------------------------------------------------------------------------------------------------------- | :-------------------------------- |
| `packages/` | **Source code lives here.** Each sub-dir is an _independent_ package with its own manifest (`pyproject.toml`, etc.) and detailed `README.md`. | `site_downloader/`, `yt_bulk_cc/` |

---

## 🚀 Quick start

### 1. Clone & enter the repo

```bash
git clone https://github.com/devguyrash/SwissBook.git
cd SwissBook
```

### 2. Create a shared virtual environment

It's recommended to install all Python packages into a single environment.

```bash
# create & enter a virtual env (per shell)
uv venv .venv
source .venv/bin/activate
```

### 3. Install tools

Install each tool in editable mode.

```bash
# Install the Site Downloader and its dev dependencies
uv pip install -e "packages/site_downloader[dev]"

# Install Playwright's browser binaries (one-time setup)
python -m playwright install --with-deps

# Install the YouTube Bulk CC script and its dependencies
uv pip install -e "packages/yt_bulk_cc"
```

### 4. Basic usage

#### Site Downloader (`sdl`)

```bash
# Convert a URL to a dual-media PDF (screen + print)
sdl grab https://example.com -f pdf

# Fetch an article-only version as Markdown
sdl grab https://some.blog/article -f md

# Process a list of URLs from a file into PNGs with 4 concurrent jobs
sdl grab ./path/to/urls.txt -f png -j 4
```

> See the [**`site-downloader` README**](packages/site_downloader/README.md) for all options.

#### YouTube Bulk CC (`yt_bulk_cc.py`)

```bash
# Get transcripts for a whole playlist as individual JSON files
python -m yt_bulk_cc.yt_bulk_cc "https://youtube.com/playlist?list=PLxyz123" -f json

# Get a single video's transcript as plain text with timestamps
python -m yt_bulk_cc.yt_bulk_cc https://youtu.be/dQw4w9WgXcQ -f text -t

# Combine all transcripts from a channel into a single file
python -m yt_bulk_cc.yt_bulk_cc "https://www.youtube.com/@CrashCourse/videos" -f text -C combined_transcripts
```

> See the script's built-in help for all options: `python -m yt_bulk_cc.yt_bulk_cc --help`

## Installation

### Running with the Playwright Docker image

>If you'd rather avoid installing ~1 GB of browser binaries locally, you can
>run *sdl* in a container:
>
>```bash
>pip install "site_downloader[docker]"
>SDL_PLAYWRIGHT_DOCKER=1 sdl grab https://example.com -f pdf
>```

---

## ✍️ Adding a new tool

1. `mkdir packages/my_tool && cd packages/my_tool`
2. Scaffold language-specific files (`pyproject.toml`, `src/my_tool/__init__.py`, or `package.json`, etc.).
3. Add a `README.md` inside `packages/my_tool/` explaining its purpose and usage.
4. Update the `## Available Tools` table in this main `README.md`.

---

## 🤝 Contributing

- Fork → branch → PR.
- Keep utilities self-contained-avoid cross-package imports unless there's a good reason.
- Run any relevant test commands before pushing.

---

## 📝 License

MIT - see [LICENSE](LICENSE) for details.