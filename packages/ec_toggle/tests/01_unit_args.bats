#!/usr/bin/env bats

load '00_helpers.bash'

# absolute path regardless of where Bats is run from
script="$BATS_TEST_DIRNAME/../src/ec_toggle/ec-toggle"

@test "help flag prints usage and exits 0" {
  run env -u EC_TOGGLE_LIB_ONLY bash -c "$script --help >/dev/null"
  assert_success
}

@test "--version prints semantic version" {
  run env -u EC_TOGGLE_LIB_ONLY "$script" --version
  assert_success
  [[ "$output" =~ ^ec-toggle\ [0-9]+\.[0-9]+ ]]
}

@test "unknown flag returns error" {
  run env -u EC_TOGGLE_LIB_ONLY "$script" --no-such-flag
  assert_failure
  [[ $output == *Unknown\ option* ]]
}
