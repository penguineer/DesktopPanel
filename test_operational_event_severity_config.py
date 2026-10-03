"""Tests for configurable Loki operational-event severity thresholds."""

import pytest

import operational_event_controller
from loki_events import LokiSync, TailBatch
from operational_event_controller import OperationalEventController, _build_syslog_query
from operational_events import LokiEntry, OperationalEventStore, SyslogEvent


class _FakeSource:
    instances = []

    def __init__(
        self,
        client_factory,
        store,
        on_new_events=None,
        on_failure=None,
        recovery_after_ns=None,
        min_severity=None,
    ):
        self.client_factory = client_factory
        self.store = store
        self.on_new_events = on_new_events
        self.on_failure = on_failure
        self.recovery_after_ns = recovery_after_ns
        self.min_severity = store.min_severity if min_severity is None else min_severity
        self.history_covered_through_ns = recovery_after_ns
        self.started = False
        self.torn_down = False
        self.__class__.instances.append(self)

    def start(self):
        self.started = True

    def teardown(self):
        self.torn_down = True


@pytest.fixture(autouse=True)
def reset_fake_sources():
    _FakeSource.instances = []


def _config(min_severity=None):
    loki = {
        "url": "https://loki.example",
        "user": "desktop-panel",
        "password": "secret",
    }
    if min_severity is not None:
        loki["min_severity"] = min_severity
    return {"loki": loki}


def _entry(severity, line=None, timestamp_ns=100):
    return LokiEntry(
        timestamp_ns=timestamp_ns,
        labels={
            "source": "syslog",
            "host": "host-a",
            "application": "test",
            "severity": severity,
            "facility": "user",
        },
        line=line or severity,
    )


def _event(severity, line=None, timestamp_ns=100, min_severity="debug"):
    return SyslogEvent.from_loki(
        _entry(severity, line=line, timestamp_ns=timestamp_ns),
        min_severity=min_severity,
    )


def test_default_query_preserves_existing_warning_threshold():
    query, normalized = _build_syslog_query()

    assert normalized == "warning"
    assert query == (
        '{source="syslog",alert_suppressed!="true",'
        'severity=~"warning|warn|error|err|critical|crit|alert|emergency|emerg"}'
    )


@pytest.mark.parametrize(
    ("configured", "normalized", "pattern"),
    [
        (
            "debug",
            "debug",
            "debug|info|informational|notice|warning|warn|error|err|critical|crit|alert|emergency|emerg",
        ),
        (
            "info",
            "info",
            "info|informational|notice|warning|warn|error|err|critical|crit|alert|emergency|emerg",
        ),
        (
            "informational",
            "info",
            "info|informational|notice|warning|warn|error|err|critical|crit|alert|emergency|emerg",
        ),
        (
            "notice",
            "notice",
            "notice|warning|warn|error|err|critical|crit|alert|emergency|emerg",
        ),
        (
            "warning",
            "warning",
            "warning|warn|error|err|critical|crit|alert|emergency|emerg",
        ),
        (
            "warn",
            "warning",
            "warning|warn|error|err|critical|crit|alert|emergency|emerg",
        ),
        ("error", "error", "error|err|critical|crit|alert|emergency|emerg"),
        ("err", "error", "error|err|critical|crit|alert|emergency|emerg"),
        ("critical", "critical", "critical|crit|alert|emergency|emerg"),
        ("crit", "critical", "critical|crit|alert|emergency|emerg"),
        ("alert", "alert", "alert|emergency|emerg"),
        ("emergency", "emergency", "emergency|emerg"),
        ("emerg", "emergency", "emergency|emerg"),
    ],
)
def test_query_builder_supports_thresholds_and_aliases(configured, normalized, pattern):
    query, actual_normalized = _build_syslog_query(configured)

    assert actual_normalized == normalized
    assert f'severity=~"{pattern}"' in query


def test_query_builder_rejects_unknown_severity():
    with pytest.raises(ValueError, match="Unsupported syslog severity"):
        _build_syslog_query("verbose")


def test_syslog_parser_defaults_to_warning():
    assert SyslogEvent.from_loki(_entry("warning")) is not None
    assert SyslogEvent.from_loki(_entry("info")) is None


def test_syslog_parser_accepts_info_when_configured():
    event = SyslogEvent.from_loki(_entry("informational"), min_severity="info")

    assert event is not None
    assert event.severity == "informational"


def test_loki_sync_uses_configured_threshold():
    store = OperationalEventStore(min_severity="info")
    sync = LokiSync(store)

    added, catchup = sync.merge_tail_batch(
        TailBatch(entries=(_entry("info"),), dropped_entries=None),
        boundary_ns=200,
    )

    assert catchup is False
    assert [event.severity for event in added] == ["info"]


def test_controller_passes_default_warning_query_and_threshold(monkeypatch):
    monkeypatch.setattr(operational_event_controller, "LokiEventSource", _FakeSource)
    controller = OperationalEventController()

    controller.update_config(_config())

    source = _FakeSource.instances[0]
    client = source.client_factory()
    assert client.query == _build_syslog_query("warning")[0]
    assert source.min_severity == "warning"


def test_controller_passes_configured_query_and_threshold(monkeypatch):
    monkeypatch.setattr(operational_event_controller, "LokiEventSource", _FakeSource)
    controller = OperationalEventController()

    controller.update_config(_config("info"))

    source = _FakeSource.instances[0]
    client = source.client_factory()
    assert client.query == _build_syslog_query("info")[0]
    assert source.min_severity == "info"
    assert controller.loki_store.min_severity == "info"


def test_tightening_threshold_prunes_retained_lower_severity_events(monkeypatch):
    monkeypatch.setattr(operational_event_controller, "LokiEventSource", _FakeSource)
    controller = OperationalEventController()
    controller.update_config(_config("warning"))
    warning = _event("warning", timestamp_ns=100)
    error = _event("error", timestamp_ns=101)
    controller.loki_store.merge([warning, error])

    first = _FakeSource.instances[0]
    controller.update_config(_config("error"))

    assert first.torn_down is True
    assert controller.loki_store.min_severity == "error"
    assert [event.severity for event in controller.loki_store.events] == ["error"]
    assert len(_FakeSource.instances) == 2
    assert _FakeSource.instances[1].min_severity == "error"


def test_tightening_threshold_preserves_source_state(monkeypatch):
    monkeypatch.setattr(operational_event_controller, "LokiEventSource", _FakeSource)
    controller = OperationalEventController()
    controller.update_config(_config("warning"))
    controller.loki_store.merge([
        _event("warning", timestamp_ns=100),
        _event("error", timestamp_ns=101),
    ])
    controller.loki_store.set_source_state(
        "loki",
        "disconnected",
        "down",
        timestamp_ns=102,
    )

    controller.update_config(_config("error"))

    assert len(controller.loki_store.events) == 2
    assert controller.loki_store.events[0].state == "disconnected"
    assert controller.loki_store.events[1].severity == "error"


def test_lowering_threshold_keeps_existing_events_and_accepts_new_history(monkeypatch):
    monkeypatch.setattr(operational_event_controller, "LokiEventSource", _FakeSource)
    controller = OperationalEventController()
    controller.update_config(_config("warning"))
    warning = _event("warning", timestamp_ns=100)
    controller.loki_store.merge([warning])

    controller.update_config(_config("info"))

    assert controller.loki_store.events == [warning]
    assert controller.loki_store.min_severity == "info"
    assert _FakeSource.instances[-1].min_severity == "info"

    sync = LokiSync(controller.loki_store)
    added, _ = sync.merge_tail_batch(
        TailBatch(entries=(_entry("info", timestamp_ns=101),)),
        boundary_ns=200,
    )
    assert [event.severity for event in added] == ["info"]
    assert [event.severity for event in controller.loki_store.events] == [
        "info",
        "warning",
    ]


def test_alias_change_does_not_restart_source(monkeypatch):
    monkeypatch.setattr(operational_event_controller, "LokiEventSource", _FakeSource)
    controller = OperationalEventController()

    controller.update_config(_config("warning"))
    first = _FakeSource.instances[0]
    controller.update_config(_config("warn"))

    assert len(_FakeSource.instances) == 1
    assert first.torn_down is False


def test_invalid_threshold_creates_configuration_error(monkeypatch):
    monkeypatch.setattr(operational_event_controller, "LokiEventSource", _FakeSource)
    failures = []
    controller = OperationalEventController(
        on_failure=lambda state, message: failures.append((state, message))
    )

    controller.update_config(_config("verbose"))

    assert _FakeSource.instances == []
    assert len(controller.store.events) == 1
    assert controller.store.events[0].state == "configuration-error"
    assert failures == [
        ("configuration-error", "Invalid Loki operational event minimum severity")
    ]
