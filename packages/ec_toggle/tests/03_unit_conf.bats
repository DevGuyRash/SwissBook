#!/usr/bin/env bats

load '00_helpers.bash'

@test "generated PipeWire conf contains sink_master and source_master" {
  export SINK_OVERRIDE="mysink"
  export SOURCE_OVERRIDE="mymic"

  pw_make_conf
  run cat "$TMP_FILE"
  assert_success
  [[ "$output" == *'sink_master  = "mysink"'* ]]
  [[ "$output" == *'source_master= "mymic"'* ]]
}
