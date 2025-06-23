#!/usr/bin/env bats

@test "enable succeeds and EchoCancelled node appears (PipeWire)" {
  run ec-toggle enable
  assert_success
  wpctl status | grep -q "EchoCancelled Mic"
}
