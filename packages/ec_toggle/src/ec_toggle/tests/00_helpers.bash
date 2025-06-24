# shellcheck shell=bash
load '../ec-toggle'  # make functions visible for unit tests

# stub system utilities unless explicitly asked not to
stub_command() {
  local cmd="$1"
  eval "
    ${cmd}() {
      echo 'STUB:${cmd}' \"\$@\"
      return 0
    }
  "
}

# minimal mktemp replacement for unit tests (no temp file needed)
stub_command mktemp
stub_command restorecon
