# Site Downloader (`sdl`)

```
https://example.com  --- ▶  example.pdf  (screen + print)
                      --- ▶  example.md
                      --- ▶  example.png
                      --- ▶  example.epub
```

## Installation

> Requires Python >= 3.10. All commands below use **uv** but you can swap in plain `pip` if preferred.

```bash
# 1. create & activate an isolated env from the repo root
uv venv .venv
source .venv/bin/activate

# 2. editable install (dev mode)
uv pip install -e "packages/site_downloader[dev]"

# 3. install Playwright browsers once
python -m playwright install --with-deps
```

---

## Quick start

Fetch and convert a single URL:

```bash
# Clean HTML (default)
sdl grab https://example.com # → out/example.com.html

# Markdown
sdl grab https://example.com -f md # → out/example.com.md

# Dual PDF (screen & print) at 1.5x scale
sdl grab https://example.com -f pdf -q 1.5

# Full-page PNG (Firefox engine, dark mode)
sdl grab https://example.com -f png -e firefox --dark-mode
```

Batch mode (auto-detected when the first argument is a list file):

```bash
echo "https://example.com" > urls.txt
echo "https://python.org" >> urls.txt

# generates out/example.com.md & out/python.org.md with 4-way concurrency
sdl grab urls.txt -f md --jobs 4
```

You can still call the explicit sub-command if you prefer:

```bash
sdl batch urls.txt -f pdf -j 8
```

---

## Feature matrix

| Format         | Source          | Engine needed         | Notes                                            |
| -------------- | --------------- | --------------------- | ------------------------------------------------ |
| `html`         | remote / local  | _(none)_              | raw readability extraction                       |
| `md`, `txt`    | remote / local  | _(none)_              | converts with MarkItDown = fallback to html2text |
| `docx`, `epub` | remote / local  | _(none)_              | requires **pandoc** in `PATH`                    |
| `pdf`          | **remote** only | Playwright `chromium` | writes _screen_ + _print_ PDFs                   |
| `png`          | remote only     | any Playwright engine | PNG screenshot, full page                        |

## New in v0.2.0

- **User Agent Rotation**: Randomize user agents with browser/OS filtering
- **Proxy Support**: Rotate through multiple proxies from a list or file
- **Cookie Management**: Load cookies from JSON or perform interactive login
- **Custom Styling**: Inject additional CSS for better readability

## Common CLI options

### Network & Identity

- `--proxy http://host:port` - Use a single proxy
- `--proxies "http://p1:port,http://p2:port"` - Rotate through multiple proxies (comma-separated)
- `--proxy-file proxies.txt` - Load proxies from file (one per line)
- `--ua-browser chrome` - Filter user agents by browser (chrome/firefox/safari/edge)
- `--ua-os windows` - Filter user agents by OS (windows/linux/macos/android/ios)
- `--cookies-json '{"name":"value"}'` - Pass cookies as JSON string
- `--cookies-file cookies.json` - Load cookies from JSON file
- `--login https://example.com/login` - Interactive login to capture cookies
- `--headers '{"X-Foo":"1"}'` - Add custom HTTP headers (JSON)

### Output & Styling

- `--selector "main article"` - Override auto-detected article node
- `--extra-css styles1.css,styles2.css` - Inject additional CSS files
- `--dark-mode` - Enable dark color scheme
- `--viewport-width 1440` - Set viewport width in pixels
- `--quality 1.5` - PDF scale / device-pixel-ratio (default: 2.0)

---

## Development & tests

```bash
# run fast unit suite (Playwright stubbed)
pytest -q

# coverage
pytest --cov=site_downloader -q
```

The Playwright integration test (`-m e2e`) is skipped automatically when
browsers are unavailable.

- _Coding style_: **ruff** / **black**
- _Type-checking_: *optional* mypy (config in `pyproject.toml`)

---

## License

MIT © SwissBook contributors