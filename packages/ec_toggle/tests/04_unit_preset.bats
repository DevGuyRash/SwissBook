#!/usr/bin/env bats

# Verifies that --preset & --latency are written into the PipeWire config
load '00_helpers.bash'

@test "pw_make_conf reflects preset and latency" {
  export PRESET="gaming"
  export LATENCY="128/48000"
  export SINK_OVERRIDE="mysink"
  export SOURCE_OVERRIDE="mymic"

  pw_make_conf
  run cat "$TMP_FILE"
  assert_success
  [[ $output == *'aec.args = "noise_suppress=low"'* ]]
  [[ $output == *'node.latency = 128/48000'* ]]
}
