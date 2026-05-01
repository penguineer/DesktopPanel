"""AMQP (RabbitMQ) module"""

import json
import distutils.util
from typing import Optional, Callable

import asyncio
import pika
import pika.exchange_type
from pika.adapters.asyncio_connection import AsyncioConnection

from kivy import Logger
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import DictProperty

from statusbar import TrayIcon
from syslog_messages import SyslogMessage


class AmqpAccessConfiguration(object):
    """Configuration data for the AMQP access"""

    DECLARE_DEFAULT = "false"

    @staticmethod
    def from_json_cfg(config: Optional[dict]):
        if config is None:
            return None

        cfg_amqp = config.get("amqp", None)
        if cfg_amqp is None:
            return None

        return AmqpAccessConfiguration(
            amqp_host=cfg_amqp.get("host", None),
            amqp_user=cfg_amqp.get("user", None),
            amqp_passwd=cfg_amqp.get("passwd", None)
        )

    def __init__(self,
                 amqp_host: str,
                 amqp_user: str,
                 amqp_passwd: str):

        if not amqp_host:
            raise ValueError("Host configuration must be provided!")
        if not amqp_user:
            raise ValueError("User configuration must be provided!")

        self._credentials = pika.credentials.PlainCredentials(amqp_user, amqp_passwd)
        self._params = pika.ConnectionParameters(host=amqp_host,
                                                 credentials=self._credentials)

    def host(self) -> str:
        return self._params.host

    def user(self) -> str:
        return self._credentials.username

    def connection_parameters(self) -> pika.ConnectionParameters:
        return self._params


class AmqpResourceConfiguration(object):
    """Configuration for AMQP resources"""

    COMMAND_CHANNEL_DEFAULT = "command.DesktopPanel"

    @staticmethod
    def from_json_cfg(config: Optional[dict]):
        if config is None:
            return None

        cfg_amqp = config.get("amqp", None)
        if cfg_amqp is None:
            return None

        declare_cfg = cfg_amqp.get("declare", AmqpAccessConfiguration.DECLARE_DEFAULT)
        declare = bool(distutils.util.strtobool(declare_cfg))

        return AmqpResourceConfiguration(
            declare=declare,
            command_channel=cfg_amqp.get("command_channel", AmqpResourceConfiguration.COMMAND_CHANNEL_DEFAULT),
            syslog_channel=cfg_amqp.get("syslog_channel", None)
        )

    def __init__(self,
                 declare: bool = False,
                 command_channel: str = COMMAND_CHANNEL_DEFAULT,
                 syslog_channel: Optional[str] = None):
        self._declare = declare

        if not command_channel:
            raise ValueError("Command channel must be declared!")

        self._command_channel = command_channel
        self._syslog_channel = syslog_channel if syslog_channel else None

    def declare(self) -> bool:
        return self._declare

    def command_channel(self) -> str:
        return self._command_channel

    def syslog_channel(self) -> Optional[str]:
        """Optional AMQP queue name for incoming syslog messages, or None if not configured."""
        return self._syslog_channel


class AmqpCommandDispatch(object):
    @staticmethod
    def parse_command_json(cmd: json):
        if cmd is None:
            raise ValueError("JSON object must be provided!")

        command = cmd.get("command", None)
        if command is None:
            raise ValueError("Command identifier was not specified!")

        arguments = cmd.get("arguments", dict())

        return command, arguments

    def __init__(self):
        self._handlers = dict()

    def add_command_handler(self, command: str, hnd: Optional[Callable[[str, dict], None]]) -> None:
        """ Add a command handler

            :param command: The command this handler is responsible for
            :param hnd: The handler callback or None to remove the handler for this command

            The callback receives the command name as string and a dict of arguments.
        """
        if command is None:
            raise ValueError("Command must be provided!")

        if hnd is None and command in self._handlers:
            del self._handlers[command]
        else:
            self._handlers[command] = hnd

    def dispatch_command(self, cmd: str, args: Optional[dict]) -> bool:
        """ Dispatch a command

        :param cmd: The command identifier
        :param args: The command arguments
        :return True if a handler was found
        """
        hnd = self._handlers.get(cmd, None)
        if hnd:
            hnd(cmd, args if args else dict())

        return hnd is not None


class AmqpConnector(object):
    """AMQP Connector using the Kivy loop"""

    def __init__(self,
                 amqp_access_cfg: AmqpAccessConfiguration,
                 amqp_resource_cfg: AmqpResourceConfiguration,
                 dispatch: AmqpCommandDispatch):
        if amqp_access_cfg is None:
            raise ValueError("Access configuration must be provided!")
        self._access_cfg = amqp_access_cfg

        if amqp_resource_cfg is None:
            raise ValueError("Resource configuration must be provided!")
        self._resource_cfg = amqp_resource_cfg

        if dispatch is None:
            Logger.warn("AMQP: Initialized without command dispatcher, this will do nothing!")
        self._dispatch = dispatch

        self._terminating = False

        self._connection = None
        self._channel = None
        self._consumer_tag = None
        self._syslog_consumer_tag = None

        self._tray_icon = None
        self._syslog_callback = None

    def setup(self):
        self._reconnect()

    def stop(self):
        Logger.info("AMQP: Terminating consumer")
        self._terminating = True
        self._disconnect()

    def set_syslog_callback(self, callback: Optional[Callable[['SyslogMessage'], None]]) -> None:
        """Register a callback to receive parsed SyslogMessage objects.

        The callback is invoked on the Kivy main thread via Clock.schedule_once.

        :param callback: Callable accepting a single SyslogMessage argument, or None to remove.
        """
        self._syslog_callback = callback

    def update_tray_icon(self, tray_icon=None):
        if tray_icon:
            self._tray_icon = tray_icon

        if self._connection and self._channel:
            self._schedule_kivy_icon_color([0 / 256, 163 / 256, 86 / 256, 1])
        elif self._terminating:
            self._schedule_kivy_icon_color([77 / 256, 77 / 256, 76 / 256, 1])
        else:
            self._schedule_kivy_icon_color([228 / 256, 5 / 256, 41 / 256, 1])

    def _schedule_kivy_icon_color(self, color):
        if self._tray_icon:
            Clock.schedule_once(lambda dt: self._tray_icon.setter('icon_color')(self._tray_icon, color))

    def _on_cancel(self, _method_frame):
        if self._channel:
            self._channel.close()

    def _connect(self):
        pass
        Logger.info("AMQP: Connecting to %s@%s", self._access_cfg.user(), self._access_cfg.host())

        self._connection = AsyncioConnection(parameters=self._access_cfg.connection_parameters(),
                                             on_open_callback=self._on_connection_open,
                                             on_open_error_callback=self._on_connection_error,
                                             on_close_callback=None)
        self.update_tray_icon()

    def _reconnect(self):
        if not self._terminating:
            try:
                self._connect()
            except Exception as e:
                Logger.error("AMQP: Error when connecting to RabbitMQ (will try again in 5 seconds: %s", str(e))
                asyncio.get_running_loop().call_later(5, self._reconnect)

    def _disconnect(self):
        if self._connection \
                and not self._connection.is_closing \
                and not self._connection.is_closed:
            Logger.info("AMQP: Disconnecting.")
            self._connection.close()
            self._connection = None
            self.update_tray_icon()

    def _on_connection_error(self, _connection, e):
        Logger.error("AMQP: Connection error (trying again in 5 seconds): %s", str(e))
        asyncio.get_running_loop().call_later(5, self._reconnect)

    def _on_connection_open(self, _connection):
        Logger.info("AMQP: Connection to %s opened", self._access_cfg.host())
        self._connection.add_on_close_callback(self._on_connection_closed)

        self._connection.channel(on_open_callback=self._on_channel_open)

    def _on_connection_closed(self, _connection, reason):
        if not self._terminating:
            Logger.warning("AMQP: Connection closed unexpectedly, reopening in 5 seconds: %s", reason)
            self._channel = None
            asyncio.get_running_loop().call_later(5, self._reconnect)

    def _on_channel_open(self, channel):
        self._channel = channel
        channel.add_on_close_callback(self._on_channel_closed)
        channel.basic_qos(prefetch_count=1)

        Logger.info("AMQP: Channel established")

        # Verify that the queue exists
        if self._resource_cfg.declare():
            # Verify that the queue exists
            self._channel.queue_declare(queue=self._resource_cfg.command_channel(),
                                        durable=True,
                                        passive=not self._resource_cfg.declare(),
                                        callback=self._on_bind)
        else:
            # ... otherwise directly go to the next function
            self._on_bind(None)

    def _on_channel_closed(self, channel, reason):
        if not self._terminating:
            Logger.warning("AMQP: Channel %i has been closed unexpectedly: %s", channel.channel_number, reason)

        # Something went wrong.
        # Close the connection and let the connector rebuild
        self._channel = None
        self._disconnect()

    def _on_bind(self, _method_frame):
        Logger.info("AMQP: Starting to consume on queue %s", self._resource_cfg.command_channel())
        self._consumer_tag = self._channel.basic_consume(queue=self._resource_cfg.command_channel(),
                                                         on_message_callback=self._on_command_callback)

        if self._resource_cfg.syslog_channel():
            if self._resource_cfg.declare():
                self._channel.queue_declare(queue=self._resource_cfg.syslog_channel(),
                                            durable=True,
                                            callback=self._on_bind_syslog)
            else:
                self._on_bind_syslog(None)

        self.update_tray_icon()

    def _on_bind_syslog(self, _method_frame):
        Logger.info("AMQP: Starting to consume on syslog queue %s", self._resource_cfg.syslog_channel())
        self._syslog_consumer_tag = self._channel.basic_consume(
            queue=self._resource_cfg.syslog_channel(),
            on_message_callback=self._on_syslog_callback
        )

    def _on_command_callback(self, channel, method, _properties, body):
        try:
            cmd_json = json.loads(body.decode('utf-8'))
            cmd, args = AmqpCommandDispatch.parse_command_json(cmd_json)

            if not self._dispatch:
                Logger.error("AMQP: Command received but no dispatcher is given!")
            else:
                if not self._dispatch.dispatch_command(cmd, args):
                    Logger.warn("AMQP: No dispatcher for command %s!", cmd)
                # ACK dispatched
                channel.basic_ack(delivery_tag=method.delivery_tag)

        except (json.decoder.JSONDecodeError, ValueError) as e:
            Logger.error("AMQP: Could not decode command snippet: %s", str(e))
            # ACK faulty to get them out of the queue
            channel.basic_ack(delivery_tag=method.delivery_tag)

    def _on_syslog_callback(self, channel, method, properties, _body):
        try:
            msg = SyslogMessage.from_amqp(method, properties)
            if msg and self._syslog_callback:
                callback = self._syslog_callback
                Clock.schedule_once(lambda dt: callback(msg))
            channel.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            Logger.error("AMQP: Error processing syslog message: %s", str(e))
            channel.basic_ack(delivery_tag=method.delivery_tag)


Builder.load_string("""
<AmqpWidget>:
    label: 'AMQP'
    icon: 'assets/rabbitmq_icon_64px.png'
""")


class _Colors:
    COLOR_GREY = [77 / 256, 77 / 256, 76 / 256, 1]
    COLOR_GREEN = [0 / 256, 163 / 256, 86 / 256, 1]
    COLOR_RED = [228 / 256, 5 / 256, 41 / 256, 1]


class AmqpWidget(TrayIcon):
    """AMQP widget that manages the connector lifecycle and reacts to configuration changes"""

    conf = DictProperty(None, allownone=True)

    def __init__(self, **kwargs):
        self._connector = None
        self._cmd_dispatch = AmqpCommandDispatch()
        self._syslog_callback = None

        super(AmqpWidget, self).__init__(**kwargs)

        self.bind(conf=self._on_conf)

    def add_command_handler(self, command: str, handler: Optional[Callable[[str, dict], None]]) -> None:
        """Register a command handler on the internal dispatcher"""
        self._cmd_dispatch.add_command_handler(command, handler)

    def set_syslog_callback(self, callback: Optional[Callable[['SyslogMessage'], None]]) -> None:
        """Register a callback that receives SyslogMessage objects from the syslog queue.

        The callback is invoked on the Kivy main thread.

        :param callback: Callable accepting a SyslogMessage, or None to remove.
        """
        self._syslog_callback = callback
        if self._connector:
            self._connector.set_syslog_callback(callback)

    def _on_conf(self, _instance, conf):
        if self._connector:
            self._connector.stop()
            self._connector = None

        if not conf:
            self.icon_color = _Colors.COLOR_GREY
            return

        try:
            # conf is the amqp-specific section; wrap it for the existing factory methods
            cfg = {"amqp": conf}
            access_cfg = AmqpAccessConfiguration.from_json_cfg(cfg)
            resource_cfg = AmqpResourceConfiguration.from_json_cfg(cfg)

            if access_cfg is None or resource_cfg is None:
                Logger.warning("AMQP: Missing AMQP configuration, not connecting.")
                self.icon_color = _Colors.COLOR_GREY
                return

            connector = AmqpConnector(
                amqp_access_cfg=access_cfg,
                amqp_resource_cfg=resource_cfg,
                dispatch=self._cmd_dispatch
            )
            connector.set_syslog_callback(self._syslog_callback)
            connector.update_tray_icon(self)
            connector.setup()
            self._connector = connector

        except ValueError as e:
            Logger.error("AMQP: Configuration error: %s", str(e))
            self.icon_color = _Colors.COLOR_RED

    def teardown(self):
        """Stop the AMQP connector if active"""
        if self._connector:
            self._connector.stop()
            self._connector = None
