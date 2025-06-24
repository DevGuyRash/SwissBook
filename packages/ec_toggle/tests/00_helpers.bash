#!/usr/bin/env bash
# shellcheck shell=bash

# ------------------------------------------------------------------  CONFIG --
export EC_TOGGLE_LIB_ONLY=1                   # ec-toggle: defs only

# Provide a writable XDG_RUNTIME_DIR so the script's permission check passes
export XDG_RUNTIME_DIR="$(mktemp -d)"

# ---------------------------------------------------------------- STUB UTILS --
stub_bin_dir=$(mktemp -d)
stub() { printf '#!/usr/bin/env bash\nexit 0\n' >"$stub_bin_dir/$1"; chmod +x "$stub_bin_dir/$1"; }
for c in wpctl pw-cli pactl flock systemctl restorecon; do stub "$c"; done
PATH="$stub_bin_dir:$PATH"

# -------------------------------------------------------------------  IMPORT --
# pull in all functions for unit tests (path relative to repo root)
load '../src/ec_toggle/ec-toggle'

# ------------------------------------------------------------------ ASSERTS --
# ── tiny assert helpers (avoid external bats-assert) ────────────────────────
assert_success() { [ "$status" -eq 0 ] || { echo "expected success, got $status"; return 1; }; }
assert_failure() { [ "$status" -ne 0 ] || { echo "expected failure, got $status"; return 1; }; }

# -----------------------------------------------------------------  CLEANUP --
teardown() { rm -rf "$stub_bin_dir" "$XDG_RUNTIME_DIR"; }
