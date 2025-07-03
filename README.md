# SwissBook Monorepo

A grab-bag of command-line utilities written in Python. Everything lives in a **single repo** so it's easy to version, share, and hack on-even when the utilities have nothing to do with one another.

---

## 🛠️ Available Tools

This repository currently contains the following standalone tools:

| Tool                | CLI             | Description                                                                                                                                   | Documentation                                                                  |
| :------------------ | :-------------- | :-------------------------------------------------------------------------------------------------------------------------------------------- | :----------------------------------------------------------------------------- |
| **Site Downloader** | `sdl`           | A versatile web page downloader and converter. It fetches, cleans, and converts pages to PDF, PNG, Markdown, DOCX, and more using Playwright. | [**`packages/site_downloader/README.md`**](packages/site_downloader/README.md) |
| **YouTube Bulk CC** | `yt_bulk_cc.py` | A script to bulk-download YouTube transcripts for single videos, playlists, or entire channels—no API key required.                           | [**`packages/yt_bulk_cc/README.md`**](packages/yt_bulk_cc/README.md)           |

---

## 📁 Directory layout

| Folder      | Purpose                                                                                                                                       | Typical contents                  |
| :---------- | :-------------------------------------------------------------------------------------------------------------------------------------------- | :-------------------------------- |
| `packages/` | **Source code lives here.** Each sub-dir is an _independent_ package with its own manifest (`pyproject.toml`, etc.) and detailed `README.md`. | `site_downloader/`, `yt_bulk_cc/` |

---

## 🚀 Quick start

### 1. Clone the repository

```bash
git clone https://github.com/devguyrash/SwissBook.git
cd SwissBook
```

### 2. Run the setup script

This one-time command creates a shared virtual environment (`.venv`), installs all tools with their development dependencies, and downloads the necessary Playwright browser binaries.

```bash
./setup.sh --dev
```

### 3. Activate the environment

You only need to do this once per shell session.

```bash
source .venv/bin/activate
```

### 4. Use the tools

Once the environment is active, you can invoke the tools from anywhere in the repository.

#### Site Downloader (`sdl`)

```bash
# Convert a URL to a dual-media PDF (screen + print)
sdl grab https://example.com -f pdf

# Fetch an article-only version as Markdown
sdl grab https://some.blog/article -f md
```

> See the [**`site-downloader` README**](packages/site_downloader/README.md) for all options.

#### YouTube Bulk CC (`yt_bulk_cc.py`)

```bash
# Get transcripts for a whole playlist as individual JSON files
python -m yt_bulk_cc.yt_bulk_cc "https://www.youtube.com/playlist?list=YOUR_PLAYLIST_ID" -f json

# Combine all transcripts from a channel into a single file
python -m yt_bulk_cc.yt_bulk_cc "https://www.youtube.com/channel/YOUR_CHANNEL_ID" -f text -C combined_transcripts
```

> See the [**`yt_bulk_cc` README**](packages/yt_bulk_cc/README.md) for all options.

---

## ✍️ Adding a new tool

1.  `mkdir packages/my_tool && cd packages/my_tool`
2.  Scaffold language-specific files (`pyproject.toml`, `src/my_tool/__init__.py`, or `package.json`, etc.).
3.  Add a `README.md` inside `packages/my_tool/` explaining its purpose and usage.
4.  Update the `## Available Tools` table in this main `README.md`.

---

## 🤝 Contributing

- Fork → branch → PR.
- Keep utilities self-contained and avoid cross-package imports unless there's a good reason.
- Run any relevant test commands before pushing.

---

## 📝 License

MIT - see [LICENSE](LICENSE) for details.