#!/usr/bin/env bash
# =======================================================================
#  Universal bootstrap for any Python repo
#  - monorepos (packages/<name>) or single-package roots
#
#  ▸ Installs uv if missing
#  ▸ Creates/uses a shared .venv at repo root
#  ▸ Installs either one or *all* packages
#
#  Usage:
#     ./setup.sh             # editable install (single or all, auto-detect)
#     ./setup.sh --dev       # editable + all extras
#     ./setup.sh --prod      # runtime-only, non-editable, no extras
#
#  Idempotent - re-running upgrades deps.
# =======================================================================
set -euo pipefail
IFS=$'\n\t'

# ---------------- CLI flags --------------------------------------------
DEV=0
PROD=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    -d|--dev)  DEV=1 ;;
    -p|--prod) PROD=1 ;;
    -h|--help)
      echo "Usage: $0 [--dev|--prod]" ; exit 0 ;;
    *) echo "Unknown option: $1" ; exit 1 ;;
  esac
  shift
done

if [[ $DEV -eq 1 && $PROD -eq 1 ]]; then
  echo "❌  --dev and --prod are mutually exclusive" >&2
  exit 1
fi

# ---------------- locate REPO_ROOT --------------------------------------
search="$PWD"
while [[ "$search" != "/" ]]; do
  if [[ -d "$search/packages" ]]; then
    REPO_ROOT="$search"
    break
  fi
  search="$(dirname "$search")"
done
REPO_ROOT="${REPO_ROOT:-$PWD}"
cd "$REPO_ROOT"

# ---------------- uv & venv ---------------------------------------------
if ! command -v uv >/dev/null 2>&1; then
  echo "🔧  Installing uv package manager…"
  curl -LsSf https://astral.sh/uv/install.sh | bash
  export PATH="$HOME/.cargo/bin:$PATH"
fi

if [[ ! -d .venv ]]; then
  echo "📦  Creating virtualenv (.venv)…"
  uv venv .venv --seed
fi
# shellcheck source=/dev/null
source .venv/bin/activate

# ---------------- discover packages -------------------------------------
mapfile -t ALL_PKG_DIRS < <(
  [[ -d packages ]] &&
  find packages -mindepth 2 -maxdepth 2 -name pyproject.toml -printf '%h\n' | sort -u
)

CALLED_FROM="$PWD"
CUR_PKG=""
for p in "${ALL_PKG_DIRS[@]}"; do
  case "$CALLED_FROM/" in
    "$p/"*) CUR_PKG="$p" ; break ;;
  esac
done

if [[ -n "$CUR_PKG" ]]; then
  PKGS=("$CUR_PKG")
  echo "📚  Installing **current** package: $(basename "$CUR_PKG")"
elif (( ${#ALL_PKG_DIRS[@]} )); then
  PKGS=("${ALL_PKG_DIRS[@]}")
  echo "📚  Installing **all** packages:$(printf ' %s' "${PKGS[@]##*/}")"
else
  if [[ -f pyproject.toml ]]; then
    PKGS=("$REPO_ROOT")
    echo "📚  Installing root package (no /packages layout)"
  else
    echo "⚠️  No Python packages found - nothing to install."
    PKGS=()
  fi
fi

# ---------------- install ------------------------------------------------
for pkg_path in "${PKGS[@]}"; do
  if [[ $DEV -eq 1 ]]; then
    echo "  • $pkg_path  [editable + all extras]"
    uv pip install -e "$pkg_path" --all-extras
  elif [[ $PROD -eq 1 ]]; then
    echo "  • $pkg_path  [runtime only]"
    uv pip install "$pkg_path"
  else
    echo "  • $pkg_path  [editable]"
    uv pip install -e "$pkg_path"
  fi
done

# ---------------- optional Playwright browsers --------------------------
if [[ "${SKIP_PLAYWRIGHT:-0}" != "1" ]]; then
  python - <<'PY'
import importlib.util, subprocess, sys, json, os
if importlib.util.find_spec("playwright"):
    print("🎭  Installing Playwright browsers (≈200 MB, one-off)…")
    subprocess.run([sys.executable, "-m", "playwright", "install", "--with-deps"], check=False)
    # ignore failure - not all environments can pull deps
else:
    print("ℹ️  No Playwright package detected - skipping browser download.")
PY
else
  echo "⏭  Skipping Playwright browser install (SKIP_PLAYWRIGHT=1)"
fi

echo
echo "✅  Environment ready - activate later with:"
echo "     source \"$REPO_ROOT/.venv/bin/activate\""
