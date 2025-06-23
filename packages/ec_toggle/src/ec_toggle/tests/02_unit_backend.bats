#!/usr/bin/env bats

load '00_helpers.bash'

@test "detects PulseAudio when pactl exists" {
  stub_command wpctl  # simulate absence
  echo '#!/bin/sh' > pactl; chmod +x pactl; PATH=".:$PATH"

  BACKEND=""
  is_pipewire && false
  is_pulseaudio && BACKEND="pulseaudio"

  [ "$BACKEND" = "pulseaudio" ]
}
