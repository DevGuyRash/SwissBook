#!/usr/bin/env bats

# Ensures pa_disable --dry-run exits 0 and keeps the idx file
load '00_helpers.bash'

@test "pa_disable --dry-run keeps index file" {
  idx_file="$PA_IDX_FILE"
  mkdir -p "$(dirname "$idx_file")"
  echo 42 > "$idx_file"

  export DRY_RUN=1
  run pa_disable
  assert_success
  [ -f "$idx_file" ]
}
