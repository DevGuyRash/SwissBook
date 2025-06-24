# 🎙️ ec-toggle

_Advanced Echo & Noise Cancellation Manager for Linux Audio_

`ec-toggle` is a powerful command-line script for Linux that simplifies managing real-time echo cancellation and noise suppression for your microphone. It works out-of-the-box with both **PipeWire** and **PulseAudio**, creating a filtered virtual microphone that you can use in any application-like Zoom, Discord, or OBS-for crystal-clear audio.

It's designed to be a "set and forget" utility that gives you the audio quality of a dedicated hardware filter without the cost or complexity.

---

## ✨ Features

- **Dual Backend Support**: Works seamlessly with modern PipeWire/WirePlumber and legacy PulseAudio sound servers. The correct backend is detected automatically.
- **Powerful Audio Presets**: Comes with fine-tuned presets for different scenarios:
  - `default`: Balanced WebRTC-based echo cancellation and noise suppression for voice calls.
  - `gaming`: Low-latency, lighter suppression ideal for in-game voice chat.
  - `studio`: Stronger noise gate and lower noise floor for recording.
  - `rnnoise`: Superior, AI-based noise suppression with less emphasis on echo cancellation.
- **Device Pinning**: Explicitly bind the filter to a specific microphone (`--source`) and speaker (`--sink`) to avoid issues when default devices change.
- **"Set and Forget" Watch Mode**: An optional `watch` command keeps the filter active, automatically re-enabling it if a device hot-plug or system event disables it.
- **Systemd Integration**: Generate a systemd user service with one command to have `watch` mode run automatically on login.
- **Self-Contained & Simple**: A single Bash script with no complex dependencies besides the tools (`wpctl`, `pactl`) your audio server already provides.
- **Scriptable**: Includes JSON output for status checks (`--json`) and a `--dry-run` mode for safe testing.

---

## ⚙️ Prerequisites

- `bash`
- A working Linux audio setup with either:
  - **PipeWire** (with `wpctl` or `pw-cli`)
  - **PulseAudio** (with `pactl`)

---

## 💾 Installation

Since `ec-toggle` is a single, self-contained script, you can "install" it by simply making it accessible from your `$PATH`.

1. **Clone the Repository** (if you haven't already)

    ```bash
    git clone https://github.com/devguyrash/SwissBook.git
    cd SwissBook
    ```

2. **Make the Script Executable**

    ```bash
    chmod +x packages/ec_toggle/src/ec_toggle/ec-toggle
    ```

3. **Create a Symlink**

    Create a symbolic link to a directory in your user's `PATH`, like ``/.local/bin` (create it if it doesn't exist).

    ```bash
    # This is a common location for user-specific binaries
    mkdir -p `/.local/bin

    # Symlink the script
    ln -s "$(pwd)/packages/ec_toggle/src/ec_toggle/ec-toggle" `/.local/bin/ec-toggle
    ```

4. **Verify**

    Ensure your shell can find the script. You may need to restart your terminal session for the `PATH` change to take effect.

    ```bash
    ec-toggle --version
    ```

---

## 🕹️ Basic Usage

The core idea is to enable the filter, which creates a new virtual microphone named _"EchoCancelled Mic"_. You then select this new mic in your applications.

1. **List Your Devices**

    First, find the names of your real microphone (source) and speakers (sink).

    ```bash
    ec-toggle list
    ```

2. **Enable the Filter**

    Run the `enable` command, optionally specifying your devices to ensure stability.

    ```bash
    # Simple enable using default devices
    ec-toggle enable

    # Recommended: Pin to specific devices to prevent issues
    ec-toggle enable --source 'alsa_input.pci-0000_0b_00.4.analog-stereo' --sink 'alsa_output.pci-0000_0b_00.1.hdmi-stereo-extra2'
    ```

3. **Select the Virtual Mic**

    In your target application (Zoom, Discord, OBS, etc.), go to the audio settings and change your microphone to **`EchoCancelled Mic`**.

4. **Disable the Filter**

    When you're done, you can turn it off.

    ```bash
    ec-toggle disable
    ```

---

## 🎛️ Commands & Options

### Commands

| Command                   | Description                                                 |
| :------------------------ | :---------------------------------------------------------- |
| `enable` / `on`           | Enables the filter and creates virtual audio devices.       |
| `disable` / `off`         | Disables the filter and cleans up created devices/configs.  |
| `status`                  | Shows whether the echo cancellation is currently active.    |
| `list`                    | Lists available audio nodes (sinks and sources).            |
| `watch`                   | Runs in the background to ensure the filter stays enabled.  |
| `self-update`             | Updates the script to the latest version from git.          |
| `--generate-systemd-unit` | Prints a systemd user service file for the `watch` command. |

### Main Options

| Option              | Description                                                                |
| :------------------ | :------------------------------------------------------------------------- |
| `-s, --sink NAME`   | The name of the speaker/headphone device to use for echo cancellation.     |
| `-m, --source NAME` | The name of the real microphone you want to filter.                        |
| `-p, --preset NAME` | Use a specific audio profile: `default`, `gaming`, `studio`, or `rnnoise`. |
| `-l, --latency N/D` | Set a custom node latency (e.g., `128/48000`).                             |
| `-d, --dry-run`     | Print what commands would be run without actually changing anything.       |
| `-j, --json`        | Output status information in JSON format.                                  |
| `--force`           | Force enable/disable even if the script thinks it's already in that state. |

---

## 🤖 Automation with `watch` and systemd

For a truly hands-off experience, you can run `ec-toggle` as a background service. This will automatically keep the filter enabled across reboots and device changes.

1. **Generate the systemd Unit File**

    Run the generator and redirect the output to the correct location.

    ```bash
    ec-toggle --generate-systemd-unit > `/.config/systemd/user/ec-toggle.service
    ```

2. **Enable and Start the Service**

    Tell systemd to start the service now and also run it automatically every time you log in.

    ```bash
    systemctl --user enable --now ec-toggle.service
    ```

3. **Check the Service Status**

    ```bash
    systemctl --user status ec-toggle.service
    ```

The service will now run `ec-toggle watch` in the background, ensuring your virtual microphone is always available.