# SwissBook Monorepo

A grab-bag of small command-line utilities written in Python, JavaScript, and Bash.
Everything lives in a **single repo** so it's easy to version, share, and hack on-even when the utilities have nothing to do with one another.

---

## 📁 Directory layout

```
.
+-- docs/ # Design notes, how-to guides, reference cheatsheets
+-- packages/ # One sub-folder per language-specific package or library
+-- scripts/ # Thin CLI wrappers that call code in ./packages
+-- README.md
```

| Folder | Purpose | Typical contents |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------- |
| `docs/` | Markdown or asciidoc explaining how tools work, API docs, ADRs, design sketches. | `architecture.md`, `youtube_tx_usage.md` |
| `packages/` | **Source code lives here.** Each sub-dir is an *independent* package with its own manifest (`pyproject.toml`, `package.json`, etc.). | `youtube_tx/`, `url_to_formats/`, `bash_utils/` |
| `scripts/` | Small executables (Bash, PowerShell, batch) that users actually invoke. They import or call logic from `packages/`. | `youtube-dl-tx`, `url-to-formats` |

---

## 🚀 Quick start

### 1. Clone & enter the repo

```bash
git clone https://github.com/devguyrash/SwissBook.git
cd SwissBook
````

### 2. Python packages with **uv**

```bash
# create & enter a virtual env (per shell)
uv venv .venv
source .venv/bin/activate

# install one package in editable/dev mode
cd packages/youtube_tx
uv pip install -e ".[dev]"
```

### 3. JavaScript packages

```bash
cd packages/url_to_formats
npm ci # uses committed lockfile
```

### 4. Bash helpers

Nothing to install-just make the scripts executable:

```bash
chmod +x scripts/*
export PATH="$PWD/scripts:$PATH"
```

---

## 🛠 Adding a new tool

1. `mkdir packages/my_tool && cd packages/my_tool`
2. Scaffold language files (`pyproject.toml`, `src/my_tool/__init__.py`, or `package.json`, etc.).
3. Create a wrapper in `scripts/` (optional but recommended).
4. Document usage in `docs/my_tool.md`.

---

## 🤝 Contributing

- Fork → branch → PR.
- Keep utilities self-contained-avoid cross-package imports unless there's a good reason.
- Run any relevant test commands before pushing (to be added once tests exist).

---

## 📝 License

MIT - see [`LICENSE`](LICENSE) for details.
