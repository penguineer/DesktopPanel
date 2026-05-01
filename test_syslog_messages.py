""" Pytest tests for the syslog_messages module """

import datetime

import pytest

from syslog_messages import SyslogMessage, Colors


class _FakeMethod:
    """Minimal stand-in for a pika Basic.Deliver method frame."""

    def __init__(self, routing_key=''):
        self.routing_key = routing_key


class _FakeProperties:
    """Minimal stand-in for pika BasicProperties."""

    def __init__(self, headers=None):
        self.headers = headers or {}


class TestSyslogMessageFromAmqp:
    def test_none_properties(self):
        assert SyslogMessage.from_amqp(None, None) is None

    def test_empty_headers(self):
        props = _FakeProperties(headers={})
        msg = SyslogMessage.from_amqp(None, props)
        assert msg is not None
        assert msg.priority == ''
        assert msg.host == ''
        assert msg.facility == ''
        assert msg.program == ''
        assert msg.message == ''
        assert msg.date_str == ''

    def test_full_headers(self):
        props = _FakeProperties(headers={
            'DATE': 'Apr 30 19:37:03',
            'FACILITY': 'auth',
            'HOST': 'wostok',
            'HOST_FROM': 'wostok',
            'MESSAGE': 'Timeout before authentication',
            'PRIORITY': 'info',
            'PROGRAM': 'sshd',
        })
        msg = SyslogMessage.from_amqp(None, props)
        assert msg.priority == 'info'
        assert msg.facility == 'auth'
        assert msg.host == 'wostok'
        assert msg.program == 'sshd'
        assert msg.message == 'Timeout before authentication'
        assert msg.date_str == 'Apr 30 19:37:03'

    def test_host_from_fallback(self):
        props = _FakeProperties(headers={
            'HOST_FROM': 'fallback-host',
            'PRIORITY': 'error',
        })
        msg = SyslogMessage.from_amqp(None, props)
        assert msg.host == 'fallback-host'

    def test_host_from_routing_key(self):
        props = _FakeProperties(headers={'PRIORITY': 'error'})
        method = _FakeMethod(routing_key='syslog.myhost')
        msg = SyslogMessage.from_amqp(method, props)
        assert msg.host == 'myhost'

    def test_host_header_preferred_over_routing_key(self):
        props = _FakeProperties(headers={
            'HOST': 'header-host',
            'PRIORITY': 'error',
        })
        method = _FakeMethod(routing_key='syslog.routing-host')
        msg = SyslogMessage.from_amqp(method, props)
        assert msg.host == 'header-host'

    def test_priority_lowercased(self):
        props = _FakeProperties(headers={'PRIORITY': 'ERROR'})
        msg = SyslogMessage.from_amqp(None, props)
        assert msg.priority == 'error'


class TestSyslogMessageSeverity:
    def _make(self, priority):
        props = _FakeProperties(headers={'PRIORITY': priority})
        return SyslogMessage.from_amqp(None, props)

    def test_error_not_critical(self):
        assert not self._make('error').is_critical()
        assert not self._make('err').is_critical()

    def test_critical_priorities(self):
        for prio in ('crit', 'critical', 'alert', 'emerg', 'panic'):
            assert self._make(prio).is_critical(), f"Expected {prio} to be critical"

    def test_info_not_critical(self):
        assert not self._make('info').is_critical()

    def test_entry_color_critical(self):
        msg = self._make('crit')
        assert msg.entry_color() == Colors.COLOR_RED

    def test_entry_color_error(self):
        msg = self._make('error')
        assert msg.entry_color() == Colors.COLOR_YELLOW

    def test_entry_color_info(self):
        msg = self._make('info')
        assert msg.entry_color() == Colors.COLOR_YELLOW


class TestSyslogMessageHumanizedAge:
    def _make_with_age(self, seconds):
        msg = SyslogMessage(
            priority='error',
            facility='auth',
            host='host',
            program='prog',
            message='msg',
            date_str='',
        )
        msg._received_at = datetime.datetime.now() - datetime.timedelta(seconds=seconds)
        return msg

    def test_seconds(self):
        msg = self._make_with_age(30)
        age = msg.humanized_age()
        assert age.endswith('s ago')

    def test_minutes(self):
        msg = self._make_with_age(90)
        age = msg.humanized_age()
        assert age.endswith('m ago')

    def test_hours(self):
        msg = self._make_with_age(7200)
        age = msg.humanized_age()
        assert age.endswith('h ago')

    def test_days(self):
        msg = self._make_with_age(90000)
        age = msg.humanized_age()
        assert age.endswith('d ago')


class TestAmqpResourceConfigSyslog:
    """Integration tests for syslog_channel in AmqpResourceConfiguration."""

    def test_no_syslog_channel_by_default(self):
        from amqp import AmqpResourceConfiguration
        cfg = {'amqp': {}}
        resource_cfg = AmqpResourceConfiguration.from_json_cfg(cfg)
        assert resource_cfg.syslog_channel() is None

    def test_syslog_channel_configured(self):
        from amqp import AmqpResourceConfiguration
        cfg = {'amqp': {'syslog_channel': 'syslog.DesktopPanel'}}
        resource_cfg = AmqpResourceConfiguration.from_json_cfg(cfg)
        assert resource_cfg.syslog_channel() == 'syslog.DesktopPanel'

    def test_empty_syslog_channel_treated_as_none(self):
        from amqp import AmqpResourceConfiguration
        cfg = {'amqp': {'syslog_channel': ''}}
        resource_cfg = AmqpResourceConfiguration.from_json_cfg(cfg)
        assert resource_cfg.syslog_channel() is None
