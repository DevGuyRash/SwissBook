#!/usr/bin/env bats

load '00_helpers.bash'

@test "help flag prints usage and exits 0" {
  run bash -c './ec-toggle --help >/dev/null'
  assert_success
}

@test "--version prints semantic version" {
  run ./ec-toggle --version
  assert_success
  [[ "$output" =~ ^ec-toggle\ [0-9]+\.[0-9]+ ]]
}

@test "unknown flag returns error" {
  run ./ec-toggle --no-such-flag
  assert_failure
  [[ "$output" == *"Unknown option"* ]]
}
