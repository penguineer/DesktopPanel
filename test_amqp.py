""" Pytest tests for the amqp module """

import pytest

from amqp import AmqpAccessConfiguration, AmqpResourceConfiguration, AmqpCommandDispatch


class TestAmqpAccessConfig:
    def test_no_config(self):
        assert AmqpAccessConfiguration.from_json_cfg(None) is None

    def test_empty_config(self):
        assert AmqpAccessConfiguration.from_json_cfg(dict()) is None

    def test_no_host_config(self):
        cfg = {
            "amqp": {}
        }
        with pytest.raises(ValueError) as e:
            AmqpAccessConfiguration.from_json_cfg(cfg)

        assert "Host configuration must be provided!" in str(e.value)

    def test_no_user_config(self):
        cfg = {
            "amqp": {
                "host": "localhost"
            }
        }
        with pytest.raises(ValueError) as e:
            AmqpAccessConfiguration.from_json_cfg(cfg)

        assert "User configuration must be provided!" in str(e.value)

    def test_default_config(self):
        cfg = {
            "amqp": {
                "host": "localhost",
                "user": "user"
            }
        }

        amqp_cfg = AmqpAccessConfiguration.from_json_cfg(cfg)

        # These two came from the environment
        assert amqp_cfg.host() == "localhost"
        assert amqp_cfg.user() == "user"

        # These come from the defaults
        assert amqp_cfg.connection_parameters().credentials.password is None

    def test_all_config(self):
        cfg = {
            "amqp": {
                "host": "localhost",
                "user": "user",
                "passwd": "pass"
            }
        }

        amqp_cfg = AmqpAccessConfiguration.from_json_cfg(cfg)

        assert amqp_cfg.host() == "localhost"
        assert amqp_cfg.user() == "user"
        assert amqp_cfg.connection_parameters().credentials.password == "pass"


class TestAmqpResourceConfig:
    def test_no_config(self):
        assert AmqpResourceConfiguration.from_json_cfg(None) is None

    def test_empty_config(self):
        assert AmqpResourceConfiguration.from_json_cfg(dict()) is None

    def test_default_config(self):
        cfg = {
            "amqp": {
            }
        }

        amqp_cfg = AmqpResourceConfiguration.from_json_cfg(cfg)

        # These come from the defaults
        assert amqp_cfg.declare() is False
        assert amqp_cfg.command_channel() == "command.DesktopPanel"

    def test_declare_false_config(self):
        cfg = {
            "amqp": {
                "declare": "false"
            }
        }

        amqp_cfg = AmqpResourceConfiguration.from_json_cfg(cfg)

        assert amqp_cfg.declare() is False

    def test_declare_true_config(self):
        cfg = {
            "amqp": {
                "declare": "true"
            }
        }

        amqp_cfg = AmqpResourceConfiguration.from_json_cfg(cfg)

        assert amqp_cfg.declare() is True

    def test_channel_config(self):

        cfg = {
            "amqp": {
                "command_channel": "channel"
            }
        }

        amqp_cfg = AmqpResourceConfiguration.from_json_cfg(cfg)

        assert amqp_cfg.command_channel() == "channel"
        assert amqp_cfg.declare() is False

    def test_all_config(self):

        cfg = {
            "amqp": {
                "declare": "true",
                "command_channel": "channel"
            }
        }

        amqp_cfg = AmqpResourceConfiguration.from_json_cfg(cfg)

        assert amqp_cfg.declare() is True
        assert amqp_cfg.command_channel() == "channel"


class TestAmqpDispatch:
    class TestHandler(object):
        def __init__(self):
            self.called = False
            self.cmd = None
            self.arg = None

        def handle(self, cmd, args):
            self.called = True
            self.cmd = cmd
            self.arg = args["arg"] if args else None

    def test_empty(self):
        dispatch = AmqpCommandDispatch()

        # Should start with empty handlers
        assert len(dispatch._handlers) == 0

    def test_add_handler(self):
        dispatch = AmqpCommandDispatch()
        hnd = TestAmqpDispatch.TestHandler()

        dispatch.add_command_handler("test", hnd.handle)
        assert len(dispatch._handlers) == 1

        # do not call registered handler on unknown command
        # and return False because dispatch was not possible
        assert not dispatch.dispatch_command("unknown", None)
        assert not hnd.called
        assert hnd.arg is None

        # call known handler
        # and return successful dispatch
        assert dispatch.dispatch_command("test", {"arg": "unicorn"})
        assert hnd.called
        assert hnd.cmd == "test"
        assert hnd.arg == "unicorn"

    def test_remove_handler(self):
        dispatch = AmqpCommandDispatch()
        hnd = TestAmqpDispatch.TestHandler()

        # Add handler and check dispatch
        dispatch.add_command_handler("test", hnd.handle)
        assert len(dispatch._handlers) == 1
        assert dispatch.dispatch_command("test", None)

        # Remove handler
        dispatch.add_command_handler("test", None)
        assert len(dispatch._handlers) == 0
        # Dispatch must return False
        assert not dispatch.dispatch_command("test", None)

# TODO How to test the AmqpConnector?
#   Async tests
#   Use mock objects for the AMQP server / pika functions
