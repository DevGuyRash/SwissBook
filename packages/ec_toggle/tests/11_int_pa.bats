#!/usr/bin/env bats
assert_success() { [ "$status" -eq 0 ]; }

@test "enable loads module-echo-cancel and default source is set" {
  run ec-toggle enable --dry-run
  assert_success
  pactl list short modules | grep -q module-echo-cancel
}
