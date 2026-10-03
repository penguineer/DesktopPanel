"""Regression tests for visible Loki history synchronization failures."""

import asyncio

import pytest

from loki_events import LokiEventSource, LokiHistoryIncompleteError
from operational_event_panel import Colors, _combined_operational_events, _event_color
from operational_events import LokiEntry, OperationalEventStore, SourceStateEvent, SyslogEvent


class _ClientContext:
    def __init__(self, client):
        self.client = client

    async def __aenter__(self):
        return self.client

    async def __aexit__(self, _exc_type, _exc, _tb):
        return False


class _HistoryFailureClient:
    async def query_range(self, _start_ns, _end_ns):
        raise LokiHistoryIncompleteError(
            "Loki history exceeds the defensive in-memory entry limit"
        )

    async def tail(self, *, connected_event=None):
        if connected_event is not None:
            connected_event.set()
        await asyncio.Event().wait()
        if False:
            yield None


class _StopAfterRetry(RuntimeError):
    pass


class TestLokiHistoryFailureState:
    def test_history_limit_failure_remains_visible_with_specific_reason(self):
        store = OperationalEventStore()
        client = _HistoryFailureClient()

        async def stop_after_retry(_delay):
            raise _StopAfterRetry()

        source = LokiEventSource(
            lambda: _ClientContext(client),
            store,
            reconnect_initial_seconds=1,
            reconnect_max_seconds=1,
            time_ns=lambda: 100_000_000_000,
            sleep=stop_after_retry,
        )

        with pytest.raises(_StopAfterRetry):
            asyncio.run(source.run())

        assert len(store.events) == 1
        state = store.events[0]
        assert isinstance(state, SourceStateEvent)
        assert state.event_id == "source-state:loki"
        assert state.state == "history-failed"
        assert state.summary == (
            "Loki event history synchronization failed: "
            "Loki history exceeds the defensive in-memory entry limit"
        )


class TestLokiHistoryFailurePresentation:
    def test_history_failure_is_prioritized_as_red_source_state(self):
        failure = SourceStateEvent(
            event_id="source-state:loki",
            timestamp_ns=100,
            source="loki",
            source_annotation="loki",
            summary=(
                "Loki event history synchronization failed: "
                "Loki history exceeds the defensive in-memory entry limit"
            ),
            state="history-failed",
        )
        timeline_event = SyslogEvent.from_loki(LokiEntry(
            timestamp_ns=200,
            labels={
                "source": "syslog",
                "host": "host-a",
                "application": "test",
                "severity": "warning",
                "facility": "user",
            },
            line="timeline event",
        ))

        combined = _combined_operational_events([timeline_event, failure], [])

        assert combined[0] == failure
        assert _event_color(failure) == Colors.COLOR_RED
        assert "in-memory entry limit" in failure.summary
