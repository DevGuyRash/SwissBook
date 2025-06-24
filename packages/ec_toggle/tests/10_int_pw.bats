#!/usr/bin/env bats
assert_success() { [ "$status" -eq 0 ]; }

@test "enable succeeds and EchoCancelled node appears (PipeWire)" {
  run ec-toggle enable --dry-run
  assert_success
  wpctl status | grep -q "EchoCancelled Mic"
}
