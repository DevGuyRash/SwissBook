#!/usr/bin/env bats
load '00_helpers.bash'

@test "detects PulseAudio when pactl exists" {
  stub pactl
  BACKEND=""
  is_pipewire   && BACKEND="pw"
  is_pulseaudio && BACKEND="pulseaudio"
  [ "$BACKEND" = "pulseaudio" ]
}
