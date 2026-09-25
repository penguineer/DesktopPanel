""" Pytest tests for the System page operational-event policy """

from operational_events import JarvisAlertEvent, LokiEntry, SyslogEvent
from page_system import (
    _higher_notification,
    _notification_for_operational_events,
    _notification_for_operational_failure,
)


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


def _jarvis_event(severity, status="active"):
    return JarvisAlertEvent(
        event_id="jarvis",
        timestamp_ns=1,
        source="jarvis",
        source_annotation="host-a",
        summary="alert",
        cluster_name="example",
        fingerprint="abc",
        starts_at="2026-09-25T22:00:00Z",
        starts_at_ns=1,
        resolved_at=None if status != "resolved" else "2026-09-25T22:05:00Z",
        status=status,
        severity=severity,
        labels={"severity": severity},
        annotations={"summary": "alert"},
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

    def test_jarvis_warning_maps_to_warning(self):
        assert _notification_for_operational_events(
            [_jarvis_event("warning")]
        ) == "Warning"

    def test_jarvis_critical_maps_to_critical(self):
        assert _notification_for_operational_events(
            [_jarvis_event("critical")]
        ) == "Critical"

    def test_resolved_jarvis_transition_does_not_notify(self):
        assert _notification_for_operational_events(
            [_jarvis_event("warning", status="resolved")]
        ) == "None"

    def test_notification_does_not_downgrade(self):
        assert _higher_notification("Critical", "Warning") == "Critical"

    def test_notification_escalates(self):
        assert _higher_notification("Info", "Warning") == "Warning"


def test_operational_failure_maps_to_critical():
    assert _notification_for_operational_failure() == "Critical"
