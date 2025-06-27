#!/usr/bin/env bash
# setup.sh – one‑shot project bootstrapper
set -euo pipefail

# --- CLI --------------------------------------------------------------
DEV=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    -d|--dev) DEV=1 ;;          # install [dev] extra + --all-extras
    -h|--help)
      echo "Usage: $0 [--dev]"; exit 0 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
  shift
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# --- uv ---------------------------------------------------------------
if ! command -v uv >/dev/null 2>&1; then
  echo "⚙️  Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | bash   # installs to ~/.cargo/bin
  export PATH="$HOME/.cargo/bin:$PATH"
fi

# --- Python virtual env ----------------------------------------------
if [[ ! -d .venv ]]; then
  echo "📦  Creating virtualenv (.venv)..."
  uv venv .venv --seed            # includes pip for Playwright helper
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# --- Project installation --------------------------------------------
PKG="packages/site_downloader"
if [[ $DEV -eq 1 ]]; then
  echo "📚  Installing project in *dev* mode..."
  uv pip install -e "${PKG}[dev]" --all-extras
else
  echo "📚  Installing project..."
  uv pip install -e "$PKG"
fi

# --- Playwright browsers & system deps -------------------------------
echo "🎭  Installing Playwright browsers (≈ 200 MB)..."
python -m playwright install --with-deps            # idempotent

echo ""
echo "✅  Ready!  Activate later with:  source .venv/bin/activate"
