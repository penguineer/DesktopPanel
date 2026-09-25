""" Pytest tests for the System page operational-event policy """

from operational_events import LokiEntry, SyslogEvent
from page_system import _higher_notification, _notification_for_operational_events


def _event(severity):
    return SyslogEvent.from_loki(
        LokiEntry(
            timestamp_ns=1,
            labels={
                "source": "syslog",
                "host": "host-a",
                "application": "test",
                "severity": severity,
                "facility": "user",
            },
            line="message",
        )
    )


class TestSystemPageOperationalNotifications:
    def test_warning_event_maps_to_info(self):
        assert _notification_for_operational_events([_event("warning")]) == "Info"

    def test_error_event_maps_to_warning(self):
        assert _notification_for_operational_events([_event("error")]) == "Warning"

    def test_critical_event_maps_to_critical(self):
        assert _notification_for_operational_events([_event("critical")]) == "Critical"

    def test_strongest_event_wins(self):
        events = [_event("warning"), _event("error"), _event("critical")]
        assert _notification_for_operational_events(events) == "Critical"

    def test_notification_does_not_downgrade(self):
        assert _higher_notification("Critical", "Warning") == "Critical"

    def test_notification_escalates(self):
        assert _higher_notification("Info", "Warning") == "Warning"
