# mqtt2cmd

Execute commands based on MQTT messages. Subscribe to MQTT topics and automatically run configured commands when messages arrive, with support for argument substitution from JSON payloads.

## Features

- Subscribe to multiple MQTT topics and execute different commands for each
- Argument substitution from JSON array payloads (`$1`, `$2`, etc.)
- Automatic reconnection to MQTT broker
- Systemd service support for running as a daemon
- Full logging of connections, messages, and command execution

## Installation

This project uses [uv](https://docs.astral.sh/uv/) for package management. Install `uv` first:

```shell
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then install the project:

```shell
# Clone the repository
git clone https://github.com/paranoidi/mqtt2cmd.git
cd mqtt2cmd

# Install dependencies
uv sync --all-extras

# Install mqtt2cmd
uv tool install .
```

## Configuration

Create a `config.yml` file (or copy `config.yml.example`):

```yaml
broker:
  host: localhost
  port: 1883
  username: your_username  # Optional
  password: your_password  # Optional

commands:
  - topic: "desktop/notify"
    cmd: notify-send
    args: ["-t", "4000", "$1", "$2"]
  - topic: "desktop/mute"
    cmd: wpctl
    args: ["set-mute", "@DEFAULT_AUDIO_SINK@", "1"]
```

### Configuration Format

- **broker**: MQTT broker connection settings
  - `host` (required): Broker hostname or IP address
  - `port` (optional): Broker port (default: 1883)
  - `username` (optional): MQTT username
  - `password` (optional): MQTT password

- **commands**: List of command configurations
  - `topic` (required): MQTT topic to subscribe to
  - `cmd` (required): Command to execute
  - `args` (optional): List of command arguments

### Argument Substitution

Command arguments can include placeholders (`$1`, `$2`, etc.) that are substituted with values from the MQTT message payload. The payload must be a JSON array.

**Example:**

If you send a message to topic `desktop/notify` with payload:
```json
["Hello", "This is a notification"]
```

And your config has:
```yaml
- topic: "desktop/notify"
  cmd: notify-send
  args: ["-t", "4000", "$1", "$2"]
```

The executed command will be:
```shell
notify-send -t 4000 "Hello" "This is a notification"
```

Placeholders reference array indices: `$1` = first element, `$2` = second element, etc.

## Usage

### Run Directly

```shell
mqtt2cmd run --config config.yml
```

### Install as Systemd Service

Generate a systemd user service file:

```shell
mqtt2cmd install-service --config config.yml
```

This creates a service file at `~/.config/systemd/user/mqtt2cmd.service`. Then enable and start it:

```shell
systemctl --user enable mqtt2cmd.service
systemctl --user start mqtt2cmd.service
```

Check status:
```shell
systemctl --user status mqtt2cmd.service
```

View logs:
```shell
journalctl --user -u mqtt2cmd.service -f
```

## Examples

### Desktop Notifications

Send notifications from Home Assistant or other MQTT clients:

```yaml
commands:
  - topic: "desktop/notify"
    cmd: notify-send
    args: ["-t", "4000", "$1", "$2"]
  - topic: "desktop/notify-sticky"
    cmd: notify-send
    args: ["-w", "$1", "$2"]
```

Publish message:
```shell
mosquitto_pub -h localhost -t "desktop/notify" -m '["Alert", "Something happened!"]'
```

### Audio Control

Control audio devices with wpctl:

```yaml
commands:
  - topic: "desktop/mute"
    cmd: wpctl
    args: ["set-mute", "@DEFAULT_AUDIO_SINK@", "1"]
  - topic: "desktop/volume"
    cmd: wpctl
    args: ["set-volume", "@DEFAULT_AUDIO_SINK@", "$1"]
```

### System Control

Control system functions like shutdown and screen lock:

```yaml
commands:
  - topic: "desktop/shutdown"
    cmd: shutdown
    args: ["-h", "now"]
  - topic: "desktop/lock"
    cmd: cinnamon-screensaver-command
    args: ["--lock"]
```

### Display Settings

Control display settings like night light:

```yaml
commands:
  - topic: "desktop/night-light-enable"
    cmd: gsettings
    args: ["set", "org.cinnamon.settings-daemon.plugins.color", "night-light-enabled", "$1"]
  - topic: "desktop/night-light-value"
    cmd: gsettings
    args: ["set", "org.cinnamon.settings-daemon.plugins.color", "night-light-temperature", "$1"]
```

## Development

Install development dependencies:

```shell
make install
```

Run linting and type checking:

```shell
make lint
```

Run tests:

```shell
make test
```

Run everything (install, lint, test):

```shell
make
```

## License

MIT
