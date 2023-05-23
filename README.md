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
* `presence popup` Toggles the presence dialog. This command has no arguments.

## MQTT

### Status update

If an MQTT topic is provided in `mqtt.presence-topic` the presence status will be sent as raw status text.

## Resources

Uses [Free Icons from the Streamline Icons Pack](https://streamlineicons.com/).
