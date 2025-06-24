#!/usr/bin/env bats
assert_success() { [ "$status" -eq 0 ]; }

@test "enable --dry-run works in minimal container (PulseAudio)" {
  run ec-toggle enable --dry-run \
       --source dummy_mic --sink dummy_spk
  assert_success
  pactl list short modules | grep -q module-echo-cancel
}
