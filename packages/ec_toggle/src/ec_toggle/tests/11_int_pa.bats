#!/usr/bin/env bats

@test "enable loads module-echo-cancel and default source is set" {
  run ec-toggle enable
  assert_success
  pactl list short modules | grep -q module-echo-cancel
}
