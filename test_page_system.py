""" Pytest tests for the System page operational-event integration """

from operational_events import LokiEntry, SyslogEvent
from page_system import SystemPage


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
    def test_warning_event_notifies_hidden_page_with_info(self):
        page = SystemPage()
        page.active = False

        page._on_operational_events([_event("warning")])

        assert page.notification == "Info"

    def test_error_event_notifies_hidden_page_with_warning(self):
        page = SystemPage()
        page.active = False

        page._on_operational_events([_event("error")])

        assert page.notification == "Warning"

    def test_critical_event_notifies_hidden_page_with_critical(self):
        page = SystemPage()
        page.active = False

        page._on_operational_events([_event("critical")])

        assert page.notification == "Critical"

    def test_notification_does_not_downgrade(self):
        page = SystemPage()
        page.active = False
        page.notification = "Critical"

        page._on_operational_events([_event("error")])

        assert page.notification == "Critical"

    def test_visible_page_does_not_notify(self):
        page = SystemPage()
        page.active = True

        page._on_operational_events([_event("critical")])

        assert page.notification == "None"

    def test_source_failure_notifies_hidden_page(self):
        page = SystemPage()
        page.active = False

        page._on_operational_failure("disconnected", "Loki disconnected")

        assert page.notification == "Warning"

    def test_opening_page_clears_notification(self):
        page = SystemPage()
        page.notification = "Critical"

        page.active = True

        assert page.notification == "None"
