""" Pytest tests for the operational event panel module """

from operational_event_panel import OperationalEventPanel
from operational_events import LokiEntry, OperationalEventStore, SyslogEvent


def _event():
    return SyslogEvent.from_loki(
        LokiEntry(
            timestamp_ns=1,
            labels={
                "source": "syslog",
                "host": "wostok",
                "application": "test",
                "severity": "warning",
                "facility": "user",
            },
            line="A warning message",
        )
    )


class TestOperationalEventPanel:
    def test_expansion_changes_rendered_row_height(self):
        store = OperationalEventStore()
        event = _event()
        store.merge([event])

        panel = OperationalEventPanel(store=store)
        panel._refresh_entries()
        collapsed_height = panel.entries[0]["height"]

        panel.entries[0]["tap_callback"]()
        panel._refresh_entries()

        assert store.is_expanded(event.event_id)
        assert panel.entries[0]["expanded"] is True
        assert panel.entries[0]["height"] > collapsed_height
        assert panel.entries[0]["details_height"] > 0
