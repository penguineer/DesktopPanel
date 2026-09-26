"""Tests for the operational event core."""

import pytest

from operational_events import (
    JarvisAlertEvent,
    LokiEntry,
    OperationalEvent,
    OperationalEventCapacityError,
    OperationalEventStore,
    SourceStateEvent,
    SyslogEvent,
    operational_event_from_loki,
)
from timewidget import parse_iso8601_duration


def _entry(timestamp=100, line="message", **labels):
    base = {
        "source": "syslog",
        "host": "host-a",
        "application": "test",
        "severity": "warning",
        "facility": "user",
    }
    base.update(labels)
    return LokiEntry(timestamp_ns=timestamp, labels=base, line=line)


class TestLokiEntryIdentity:
    def test_id_is_independent_of_label_order(self):
        first = LokiEntry(
            timestamp_ns=123,
            labels={"source": "syslog", "host": "host-a", "severity": "warning"},
            line="same",
        )
        second = LokiEntry(
            timestamp_ns=123,
            labels={"severity": "warning", "host": "host-a", "source": "syslog"},
            line="same",
        )
        assert first.stable_id == second.stable_id

    def test_id_changes_with_line(self):
        assert _entry(line="a").stable_id != _entry(line="b").stable_id

    def test_id_changes_with_labels(self):
        assert _entry(host="host-a").stable_id != _entry(host="host-b").stable_id


    def test_syslog_id_ignores_auxiliary_loki_labels(self):
        history = _entry(
            detected_level="warn",
            service_name="desktop-panel-test",
        )
        tail = _entry(
            detected_level="warn",
            service_name="desktop-panel-test",
            suppression_matches="",
            stream_extra="tail-only",
        )

        assert history.stable_id == tail.stable_id

    def test_syslog_id_changes_when_identity_label_changes(self):
        assert _entry(application="first").stable_id != _entry(
            application="second"
        ).stable_id


class TestOperationalEventGlyphs:
    def test_generic_glyph_is_default_for_unspecialized_events(self):
        assert OperationalEvent.glyph == "assets/opevt_generic.png"
        assert SyslogEvent.glyph == OperationalEvent.glyph
        assert SourceStateEvent.glyph == OperationalEvent.glyph

    def test_jarvis_alert_has_specialized_glyph(self):
        assert JarvisAlertEvent.glyph == "assets/opevt_jarvis.png"


class TestSyslogEvent:
    def test_warning_is_accepted(self):
        event = SyslogEvent.from_loki(_entry())
        assert event is not None
        assert event.source_annotation == "host-a"
        assert event.severity == "warning"
        assert event.summary == "message"

    @pytest.mark.parametrize("severity", [
        "warning", "warn", "error", "err", "critical", "crit", "alert", "emergency", "emerg",
    ])
    def test_warning_and_more_severe_are_accepted(self, severity):
        assert SyslogEvent.from_loki(_entry(severity=severity)) is not None

    @pytest.mark.parametrize("severity", ["notice", "informational", "info", "debug"])
    def test_less_severe_events_are_filtered(self, severity):
        assert SyslogEvent.from_loki(_entry(severity=severity)) is None

    def test_unknown_severity_is_filtered(self):
        assert SyslogEvent.from_loki(_entry(severity="mystery")) is None

    def test_suppressed_event_is_filtered(self):
        assert SyslogEvent.from_loki(
            _entry(alert_suppressed="true", suppression_matches="example")
        ) is None

    def test_source_dispatch_is_extensible(self):
        assert isinstance(operational_event_from_loki(_entry()), SyslogEvent)

        pod = LokiEntry(
            timestamp_ns=1,
            labels={"source": "kubernetes-pod", "container": "example"},
            line="pod output",
        )
        assert operational_event_from_loki(pod) is None


class TestOperationalEventStore:
    def test_memory_ceiling_fails_explicitly(self):
        store = OperationalEventStore(max_events=2)
        first = SyslogEvent.from_loki(_entry(timestamp=1, line="first"))
        second = SyslogEvent.from_loki(_entry(timestamp=2, line="second"))
        third = SyslogEvent.from_loki(_entry(timestamp=3, line="third"))

        store.merge([first, second])

        with pytest.raises(OperationalEventCapacityError, match="in-memory"):
            store.merge([third])

        assert store.events == [second, first]

    def test_history_and_tail_overlap_deduplicates(self):
        store = OperationalEventStore()
        event = SyslogEvent.from_loki(_entry())

        assert store.merge([event]) == [event]
        assert store.merge([event]) == []
        assert store.events == [event]

    def test_newest_first_with_deterministic_tie_breaker(self):
        store = OperationalEventStore()
        older = SyslogEvent.from_loki(_entry(timestamp=10, line="older"))
        same_a = SyslogEvent.from_loki(_entry(timestamp=20, line="a"))
        same_b = SyslogEvent.from_loki(_entry(timestamp=20, line="b"))

        store.merge([same_b, older, same_a])

        assert store.events[0].timestamp_ns == 20
        assert store.events[1].timestamp_ns == 20
        assert store.events[2] == older
        assert [e.event_id for e in store.events[:2]] == sorted(
            [same_a.event_id, same_b.event_id]
        )

    def test_source_state_is_before_normal_events(self):
        store = OperationalEventStore()
        normal = SyslogEvent.from_loki(_entry(timestamp=999))
        store.merge([normal])
        store.set_source_state("loki", "disconnected", "Loki tail disconnected", timestamp_ns=1)

        assert isinstance(store.events[0], SourceStateEvent)
        assert store.events[1] == normal

    def test_source_state_updates_in_place_without_new_transition(self):
        store = OperationalEventStore()

        assert store.set_source_state(
            "loki", "disconnected", "first failure", timestamp_ns=10
        ) is True
        assert store.set_source_state(
            "loki", "disconnected", "retry failed", timestamp_ns=20
        ) is False

        assert len(store.events) == 1
        assert store.events[0].event_id == "source-state:loki"
        assert store.events[0].timestamp_ns == 10
        assert store.events[0].summary == "retry failed"

    def test_source_state_change_is_new_transition(self):
        store = OperationalEventStore()
        store.set_source_state("loki", "disconnected", "down", timestamp_ns=10)

        assert store.set_source_state(
            "loki", "catching-up", "recovering", timestamp_ns=20
        ) is True
        assert store.events[0].timestamp_ns == 20

    def test_source_state_can_be_removed(self):
        store = OperationalEventStore()
        store.set_source_state("loki", "disconnected", "down", timestamp_ns=10)

        assert store.clear_source_state("loki") is True
        assert store.clear_source_state("loki") is False
        assert store.events == []

    def test_pruning_uses_event_timestamp(self):
        store = OperationalEventStore()
        old = SyslogEvent.from_loki(_entry(timestamp=9, line="old"))
        boundary = SyslogEvent.from_loki(_entry(timestamp=10, line="boundary"))
        store.merge([old, boundary])

        assert store.prune_before(10) == 1
        assert store.events == [boundary]

    def test_expansion_state_toggles_and_is_pruned(self):
        store = OperationalEventStore()
        event = SyslogEvent.from_loki(_entry(timestamp=9))
        store.merge([event])

        assert store.toggle_expanded(event.event_id) is True
        assert store.is_expanded(event.event_id)
        assert store.toggle_expanded(event.event_id) is False
        assert not store.is_expanded(event.event_id)

        store.toggle_expanded(event.event_id)
        store.prune_before(10)
        assert not store.is_expanded(event.event_id)

    def test_events_property_is_observable(self):
        store = OperationalEventStore()
        notifications = []
        store.bind(events=lambda _instance, value: notifications.append(list(value)))

        event = SyslogEvent.from_loki(_entry())
        store.merge([event])

        assert notifications
        assert notifications[-1] == [event]

    def test_custom_history_duration_updates_seconds(self):
        store = OperationalEventStore(history_duration="PT1H30M")
        assert store.history_seconds == 5400


class TestIsoDuration:
    def test_iso_duration(self):
        assert parse_iso8601_duration("PT24H") == 86400

    def test_fractional_duration(self):
        assert parse_iso8601_duration("PT0.5H") == 1800

    def test_numeric_value_is_rejected(self):
        with pytest.raises(ValueError):
            parse_iso8601_duration(24)

    def test_invalid_duration_is_rejected(self):
        with pytest.raises(ValueError):
            parse_iso8601_duration("24h")

    def test_calendar_dependent_duration_is_rejected(self):
        with pytest.raises(ValueError):
            parse_iso8601_duration("P1M")
