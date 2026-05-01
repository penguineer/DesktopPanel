""" Pytest tests for the syslog_messages module """

import datetime

import pytest

from syslog_messages import (SyslogMessage, Colors,
                             _msg_lines, _entry_height, _passes_filter,
                             _ENTRY_CHARS_PER_LINE, _ENTRY_LINE_HEIGHT,
                             _ENTRY_MIN_HEIGHT,
                             _ENTRY_META_HEIGHT, _ENTRY_SPACING, _ENTRY_PADDING_V)


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
        # Non-error / non-critical priorities display in white (standard text colour).
        msg = self._make('info')
        assert msg.entry_color() == Colors.COLOR_WHITE


class TestSyslogMessageFormattedTime:
    def _make_with_offset(self, days=0, seconds=0):
        msg = SyslogMessage(
            priority='error',
            facility='auth',
            host='host',
            program='prog',
            message='msg',
            date_str='',
        )
        msg._received_at = datetime.datetime.now() - datetime.timedelta(days=days, seconds=seconds)
        return msg

    def test_today_shows_time_only(self):
        msg = self._make_with_offset(seconds=30)
        result = msg.formatted_time()
        # Expected format: HH:MM
        assert len(result) == 5
        assert result[2] == ':'

    def test_yesterday_shows_date_and_time(self):
        msg = self._make_with_offset(days=1)
        result = msg.formatted_time()
        # Expected format: DD.MM HH:MM
        assert len(result) == 11
        assert result[2] == '.'
        assert result[5] == ' '
        assert result[8] == ':'


class TestEntryHeightHelpers:
    def test_empty_message_is_one_line(self):
        assert _msg_lines('') == 1

    def test_short_message_is_one_line(self):
        assert _msg_lines('short') == 1

    def test_exact_one_line_boundary(self):
        assert _msg_lines('x' * _ENTRY_CHARS_PER_LINE) == 1

    def test_one_char_over_boundary_is_two_lines(self):
        assert _msg_lines('x' * (_ENTRY_CHARS_PER_LINE + 1)) == 2

    def test_long_message_capped_at_three_lines(self):
        assert _msg_lines('x' * (_ENTRY_CHARS_PER_LINE * 10)) == 3

    def test_entry_height_one_line(self):
        expected = _ENTRY_MIN_HEIGHT
        assert _entry_height('short') == expected

    def test_entry_height_three_lines(self):
        expected = 2 * _ENTRY_PADDING_V + _ENTRY_META_HEIGHT + _ENTRY_SPACING + 3 * _ENTRY_LINE_HEIGHT
        assert _entry_height('x' * (_ENTRY_CHARS_PER_LINE * 10)) == expected


class TestPassesFilter:
    def test_critical_passes_error_filter(self):
        assert _passes_filter('crit', 'error')

    def test_error_passes_error_filter(self):
        assert _passes_filter('error', 'error')

    def test_err_alias_passes_error_filter(self):
        assert _passes_filter('err', 'error')

    def test_warning_blocked_by_error_filter(self):
        assert not _passes_filter('warning', 'error')

    def test_info_blocked_by_error_filter(self):
        assert not _passes_filter('info', 'error')

    def test_debug_blocked_by_error_filter(self):
        assert not _passes_filter('debug', 'error')

    def test_unknown_priority_blocked_by_error_filter(self):
        assert not _passes_filter('unknown_level', 'error')

    def test_critical_passes_warning_filter(self):
        assert _passes_filter('crit', 'warning')

    def test_warning_passes_warning_filter(self):
        assert _passes_filter('warning', 'warning')

    def test_info_blocked_by_warning_filter(self):
        assert not _passes_filter('info', 'warning')

    def test_info_passes_info_filter(self):
        assert _passes_filter('info', 'info')

    def test_debug_blocked_by_info_filter(self):
        assert not _passes_filter('debug', 'info')

    def test_emerg_passes_crit_filter(self):
        assert _passes_filter('emerg', 'crit')

    def test_panic_alias_passes_crit_filter(self):
        assert _passes_filter('panic', 'crit')

    def test_filter_with_unknown_min_priority(self):
        # An unrecognized min_priority string maps to _SEVERITY_UNKNOWN (8),
        # which is numerically below all known severity levels, so all known
        # priorities pass through (fail-open: misconfiguration shows messages).
        assert _passes_filter('info', 'not_a_level')
        assert _passes_filter('debug', 'not_a_level')


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
