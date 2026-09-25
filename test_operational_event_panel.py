""" Pytest tests for the operational event panel helpers """

from operational_event_panel import (
    Colors,
    _combined_operational_events,
    _entry_height,
    _event_color,
)
from operational_events import (
    JarvisAlertEvent,
    LokiEntry,
    SourceStateEvent,
    SyslogEvent,
)


def _jarvis(
    event_id,
    starts_ns,
    *,
    status="active",
    timestamp_ns=None,
    severity="warning",
):
    return JarvisAlertEvent(
        event_id=event_id,
        timestamp_ns=starts_ns if timestamp_ns is None else timestamp_ns,
        source="jarvis",
        source_annotation="host-a",
        summary=event_id,
        cluster_name="example",
        fingerprint=event_id,
        starts_at="2026-09-25T22:00:00Z",
        starts_at_ns=starts_ns,
        resolved_at=None if status != "resolved" else "2026-09-25T22:05:00Z",
        status=status,
        severity=severity,
        labels={},
        annotations={},
    )


class TestOperationalEventPanelLayout:
    def test_expanded_row_is_taller_than_collapsed_row(self):
        collapsed = _entry_height("A warning message")
        expanded = _entry_height(
            "A warning message",
            '{"host": "host-a", "severity": "warning"}',
            True,
        )

        assert expanded > collapsed

    def test_multiline_details_increase_expanded_height(self):
        short = _entry_height("message", "one", True)
        multiline = _entry_height("message", "one\ntwo\nthree", True)

        assert multiline > short


class TestOperationalEventColors:
    def test_warning_remains_white(self):
        warning = SyslogEvent.from_loki(LokiEntry(
            timestamp_ns=1,
            labels={
                "source": "syslog",
                "host": "host-a",
                "application": "test",
                "severity": "warning",
                "facility": "user",
            },
            line="warning",
        ))

        assert _event_color(warning) == Colors.COLOR_WHITE
        assert _event_color(_jarvis("warning", 1)) == Colors.COLOR_WHITE

    def test_error_is_yellow_and_critical_is_red(self):
        assert _event_color(
            _jarvis("error", 1, severity="error")
        ) == Colors.COLOR_YELLOW
        assert _event_color(
            _jarvis("critical", 1, severity="critical")
        ) == Colors.COLOR_RED

    def test_resolved_jarvis_warning_is_grey(self):
        assert _event_color(
            _jarvis("resolved", 1, status="resolved")
        ) == Colors.COLOR_GREY


class TestOperationalEventOrdering:
    def test_health_then_actionable_jarvis_then_shared_timeline(self):
        loki_state = SourceStateEvent(
            event_id="source-state:loki",
            timestamp_ns=1,
            source="loki",
            source_annotation="loki",
            summary="down",
            state="disconnected",
        )
        jarvis_state = SourceStateEvent(
            event_id="source-state:jarvis",
            timestamp_ns=2,
            source="jarvis",
            source_annotation="jarvis",
            summary="down",
            state="unreachable",
        )
        loki = SyslogEvent.from_loki(LokiEntry(
            timestamp_ns=300,
            labels={
                "source": "syslog",
                "host": "host-a",
                "application": "test",
                "severity": "warning",
                "facility": "user",
            },
            line="loki",
        ))
        older_active = _jarvis("older-active", 100)
        newer_active = _jarvis("newer-active", 200)
        resolved_newer = _jarvis(
            "resolved-newer",
            50,
            status="resolved",
            timestamp_ns=400,
        )
        resolved_older = _jarvis(
            "resolved-older",
            40,
            status="resolved",
            timestamp_ns=250,
        )

        events = _combined_operational_events(
            [loki_state, loki],
            [jarvis_state, older_active, resolved_older, newer_active, resolved_newer],
        )

        assert events[:2] == [loki_state, jarvis_state]
        assert events[2:4] == [newer_active, older_active]
        assert events[4:] == [resolved_newer, loki, resolved_older]

    def test_late_jarvis_population_still_precedes_timeline(self):
        loki = SyslogEvent.from_loki(LokiEntry(
            timestamp_ns=300,
            labels={
                "source": "syslog",
                "host": "host-a",
                "application": "test",
                "severity": "warning",
                "facility": "user",
            },
            line="existing timeline event",
        ))

        before = _combined_operational_events([loki], [])
        assert before == [loki]

        active = _jarvis("late-active", 100)
        after = _combined_operational_events([loki], [active])

        assert after == [active, loki]

