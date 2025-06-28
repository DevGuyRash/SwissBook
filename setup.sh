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
INVOKED_FROM="$PWD"

DEV=0
PROD=0
DRY_RUN=0
ALL_EXTRAS=0
EXTRAS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    -d|--dev)        DEV=1 ;;
    -p|--prod)       PROD=1 ;;
    -n|--dry-run)    DRY_RUN=1 ;;
    -A|--all-extras) ALL_EXTRAS=1 ;;
    -e|--extra)      shift; IFS=',' read -ra EXTRAS <<<"$1" ;;
    -h|--help)
      cat <<'EOF'
Usage: ./setup.sh  [--dev | --prod]  [--dry-run]
                   [--all-extras]  [--extra foo,bar]

  -d, --dev          editable + dev dependency groups
  -p, --prod         runtime-only (no dev groups, non-editable)
  -n, --dry-run      show commands instead of running them
  -A, --all-extras   install every optional-dependency table
  -e, --extra LIST   install specific extras (comma-separated)
EOF
      exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
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
  if [[ $DRY_RUN -eq 0 ]]; then
    curl -LsSf https://astral.sh/uv/install.sh | bash
    export PATH="$HOME/.cargo/bin:$PATH"
  fi
fi

if [[ ! -d .venv ]]; then
  echo "📦  Creating virtualenv (.venv)…"
  if [[ $DRY_RUN -eq 0 ]]; then
    uv venv .venv --seed
  fi
fi
# shellcheck source=/dev/null
[[ -d .venv ]] && source .venv/bin/activate || true

# ------------------- Fast-path uv sync if project root ------------------
if [[ -f pyproject.toml ]]; then
  CMD=(uv sync)
  grep -qE '^\s*\[(workspace|tool\.poetry\.workspace)' pyproject.toml && CMD+=(--all-packages)
  (( DEV )) && CMD+=(--dev) || CMD+=(--no-dev)
  (( PROD )) && CMD+=(--no-dev --no-editable)
  (( ALL_EXTRAS )) && CMD+=(--all-extras)
  for ex in "${EXTRAS[@]}"; do CMD+=(--extra "$ex"); done
  echo "🚀  ${CMD[*]}"
  [[ $DRY_RUN -eq 0 ]] && "${CMD[@]}"
  exit
fi

# ---------------- discover packages (fallback) --------------------------
mapfile -t ALL_PKG_DIRS < <(
  [[ -d packages ]] &&
  find packages -mindepth 2 -maxdepth 2 -name pyproject.toml -printf '%h\n' | sort -u
)

# figure out if we're inside one of those package dirs
CALLED_FROM="$INVOKED_FROM"
CUR_PKG=""
for p in "${ALL_PKG_DIRS[@]}"; do
  case "$CALLED_FROM/" in
    "$p/"*) CUR_PKG="$p"; break ;;
  esac
done

# decide what to install:
if [[ -n "$CUR_PKG" ]]; then
  PKGS=("$CUR_PKG")
  echo "📚  Installing **current** package: $(basename "$CUR_PKG")"
elif (( ${#ALL_PKG_DIRS[@]} )); then
  PKGS=("${ALL_PKG_DIRS[@]}")
  echo "📚  Installing **all** packages:$(printf ' %s' "${PKGS[@]##*/}")"
elif [[ -f pyproject.toml ]]; then
  # no packages/* but root defines a package
  PKGS=("$REPO_ROOT")
  echo "📚  Installing root package (no /packages layout)"
else
  # nothing at all
  echo "⚠️  No Python packages found - nothing to install."
  PKGS=()
fi

has_extras() { [[ -f "$1/pyproject.toml" ]] && grep -qE '^\s*\[project\.optional-dependencies' "$1/pyproject.toml"; }

for pkg_path in "${PKGS[@]}"; do
  spec="$pkg_path"
  if ((${#EXTRAS[@]})); then
    spec+="[${EXTRAS[*]}]"
    spec="${spec// /,}"
  fi

  if [[ $DEV -eq 1 ]]; then
    if (( ALL_EXTRAS )) && has_extras "$pkg_path"; then
      echo "  • $spec  [editable + all extras]"
      [[ $DRY_RUN -eq 0 ]] && uv pip install -e "$pkg_path" --all-extras
    else
      echo "  • $spec  [editable]"
      [[ $DRY_RUN -eq 0 ]] && uv pip install -e "$spec"
    fi

  elif [[ $PROD -eq 1 ]]; then
    echo "  • $pkg_path  [runtime only]"
    [[ $DRY_RUN -eq 0 ]] && uv pip install "$pkg_path"

  else
    echo "  • $spec  [editable]"
    [[ $DRY_RUN -eq 0 ]] && uv pip install -e "$spec"

  fi
done

# ---------------- optional Playwright browsers --------------------------
if [[ "${SKIP_PLAYWRIGHT:-0}" == "1" ]]; then
  echo "⏭  Skipping Playwright browser install (SKIP_PLAYWRIGHT=1)"
elif [[ $DRY_RUN -eq 1 ]]; then
  echo "⏭  Dry-run: skipping Playwright browser install"
else
  python - <<'PY'
import importlib.util, subprocess, sys
if importlib.util.find_spec("playwright"):
    print("🎭  Installing Playwright browsers (≈200 MB, one-off)…")
    subprocess.run([sys.executable, "-m", "playwright", "install", "--with-deps"], check=False)
else:
    print("ℹ️  No Playwright package detected - skipping browser download.")
PY
fi

echo
echo "✅  Environment ready - activate later with:"
echo "     source \"$REPO_ROOT/.venv/bin/activate\""
