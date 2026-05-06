# Desktop Panel

> Desktop control panel with Raspberry Pi and RPi Touch Screen

Similar to the 
[SmartBedroomPanel](https://github.com/penguineer/SmartBedroomPanel),
but with improved structure.

[![CodeQL](https://github.com/penguineer/DesktopPanel/actions/workflows/codeql-analysis.yml/badge.svg)](https://github.com/penguineer/DesktopPanel/actions/workflows/codeql-analysis.yml)

## Setup

### Using the backlight control

To allow backlight control as non-root user, this rule must be added to udev:
```
SUBSYSTEM=="backlight",RUN+="/bin/chmod 666 /sys/class/backlight/%k/brightness /sys/class/backlight/%k/bl_power"
```
e.g. with this command:
```bash
echo 'SUBSYSTEM=="backlight",RUN+="/bin/chmod 666 /sys/class/backlight/%k/brightness /sys/class/backlight/%k/bl_power"' | sudo tee -a /etc/udev/rules.d/backlight-permissions.rules
```

If no known board is detected the backlight sysfs environment is faked in a temp dir.

## Run with Docker

Because access to several system resources is needed, the container must be started with elevated access rights. In addition, configuration files need to be made available.

The below example shows how to run the container on the command line.
Please do not forget to set the variables accordingly and make sure you provide a valid absolute path to the configuration files.

```bash
VERSION=latest
CFGPATH=/path/to/desktop-panel-config.json
ISSUELISTPATH=/path/to/issuelist.json

docker run -d -it \
           --name desktop-panel \
           --restart always \
           --privileged \
           --mount "type=bind,source=${CFGPATH},target=/app/desktop-panel-config.json,readonly" \
           --mount "type=bind,source=${ISSUELISTPATH},target=/app/issuelist.json,readonly" \
           -e "TZ=Europe/Berlin" \
           mrtux/desktop-panel:$VERSION
```

Note that with these mounts the application will still react to changes to the JSON files.

## API

## AMQP

### Configuration

Access and credentials are configured with `amqp.host`, `amqp.user` and `amqp.passwd` in the DesktopPanel's configuration file. 

AMQP resource will be declared if `amqp.declare` is set to true, otherwise setup must be done externally. 
This way specific setups can be achieved without changing code in the DesktopPanel.

### Command Channel

The DesktopPanel listens for commands on the channel defined in `amqp.command_channel`, defaulting to `command.DesktopPanel`.

Each command has the following form:

```json
{
  "command": "command identifier",
  "arguments": {
    "arg1 key": "arg1 value"
  }
}
```

In the current implementation commands are Request-only, i.e. there is no generic (RPC) mechanism to respond to a command.
This may change in future versions.

### Known Commands

* `screenshot` Takes a screenshot and stores in the working directory. This command has no arguments.
* `show page` Toggles to the page given in the `page` argument. In addition, specify `go_back_if_current` to pop the navigation stack if the page is already active.

### Syslog Channel

The DesktopPanel can display critical syslog messages on the System page.
Messages are consumed from the queue defined in `amqp.syslog_channel` (no default; omit the key to disable this feature).

#### Message Format

Messages must originate from **syslog-ng's AMQP destination**.
All relevant information is carried in the AMQP message **properties headers** — the message body is empty.
The following headers are used:

| Header | Description |
|--------|-------------|
| `DATE` | Original event timestamp (e.g. `Apr 30 19:37:03`) |
| `FACILITY` | syslog facility (e.g. `auth`, `kern`) |
| `HOST` / `HOST_FROM` | Originating host name |
| `MESSAGE` | The log message text |
| `PRIORITY` | syslog priority string (e.g. `error`, `crit`) |
| `PROGRAM` | The program that generated the message |

Only messages with `error`/`err` or higher severity (`crit`, `critical`, `alert`, `emerg`, `panic`) are meaningful to display.
Use syslog-ng filters or RabbitMQ bindings to route only these severities to the DesktopPanel queue.

#### RabbitMQ Setup

A dedicated queue for DesktopPanel syslog display is recommended so that messages can also be consumed by other services independently.

Example RabbitMQ setup (adjust names to your environment):

1. **Exchange**: Use the exchange created by syslog-ng (typically a `topic` exchange, e.g. `syslog`).
2. **Queue**: Create a durable queue, e.g. `syslog.DesktopPanel`.
3. **Binding**: Bind the queue to the syslog exchange.
   If syslog-ng uses the host name as part of the routing key, a wildcard binding such as `#` or `*.error` can be used depending on your routing key scheme.
4. **Configure DesktopPanel**: Set `amqp.syslog_channel` to the queue name (e.g. `syslog.DesktopPanel`) and optionally set `amqp.declare` to `false` if the queue is managed externally.

Example `desktop-panel-config.json` snippet:
```json
"amqp": {
  "host": "rabbitmq.example.com",
  "user": "desktop",
  "passwd": "secret",
  "declare": "false",
  "command_channel": "command.DesktopPanel",
  "syslog_channel": "syslog.DesktopPanel"
}
```

#### Notification behaviour

When a new syslog message is received while the System page is **not** active, the System page tab button lights up:
* **Red / Critical** — for priorities `crit`, `critical`, `alert`, `emerg`, `panic`
* **Yellow / Warning** — for priorities `error` / `err`

The notification clears automatically when the System page is opened.

## MQTT

### Status update

If an MQTT topic is provided in `mqtt.presence-topic` the presence status will be sent as raw status text.

## Resources

Uses [Free Icons from the Streamline Icons Pack](https://streamlineicons.com/).

## License

[MIT](LICENSE.txt) © 2021 Stefan Haun and contributors
