# Desktop Panel

> Desktop control panel with Raspberry Pi and RPi Touch Screen

Similar to the 
[SmartBedroomPanel](https://github.com/penguineer/SmartBedroomPanel),
but with with improved structure.

[![CodeQL](https://github.com/penguineer/DesktopPanel/actions/workflows/codeql-analysis.yml/badge.svg)](https://github.com/penguineer/DesktopPanel/actions/workflows/codeql-analysis.yml)

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

* `presence popup` Toggles the presence dialog. This command has no arguments.

## MQTT

### Status update

If an MQTT topic is provided in `mqtt.presence-topic` the presence status will be sent as raw status text.

## Resources

Uses [Free Icons from the Streamline Icons Pack](https://streamlineicons.com/).
