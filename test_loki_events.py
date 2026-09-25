"""Tests for Loki transport normalization and synchronization."""

import asyncio

import pytest

from loki_events import (
    LokiClient,
    LokiEventSource,
    LokiHistoryIncompleteError,
    LokiProtocolError,
    LokiSync,
    TailBatch,
    _tail_url,
    parse_query_range_response,
    parse_tail_response,
)
from operational_events import LokiEntry, OperationalEventStore, operational_event_from_loki


def _loki_entry(ts, line="event", severity="warning"):
    return LokiEntry(
        timestamp_ns=ts,
        labels={
            "source": "syslog",
            "host": "wostok",
            "application": "test",
            "severity": severity,
            "facility": "user",
        },
        line=line,
    )


class TestResponseParsing:
    def test_query_range_flattens_streams(self):
        payload = {
            "status": "success",
            "data": {
                "resultType": "streams",
                "result": [
                    {
                        "stream": {
                            "source": "syslog",
                            "host": "wostok",
                            "severity": "warning",
                        },
                        "values": [
                            ["100", "first"],
                            ["101", "second"],
                        ],
                    }
                ],
            },
        }

        entries = parse_query_range_response(payload)

        assert [(e.timestamp_ns, e.line) for e in entries] == [
            (100, "first"),
            (101, "second"),
        ]
        assert entries[0].labels["host"] == "wostok"

    def test_tail_uses_same_entry_shape_and_keeps_dropped_entries(self):
        payload = {
            "streams": [
                {
                    "stream": {
                        "source": "syslog",
                        "host": "wostok",
                        "severity": "warning",
                    },
                    "values": [["200", "live"]],
                }
            ],
            "dropped_entries": [{"timestamp": "199"}],
        }

        batch = parse_tail_response(payload)

        assert batch.entries == (
            LokiEntry(
                timestamp_ns=200,
                labels={
                    "source": "syslog",
                    "host": "wostok",
                    "severity": "warning",
                },
                line="live",
            ),
        )
        assert batch.dropped_entries == [{"timestamp": "199"}]

    def test_structured_metadata_returned_as_labels_is_preserved(self):
        payload = {
            "streams": [
                {
                    "stream": {
                        "source": "syslog",
                        "alert_suppressed": "true",
                        "suppression_matches": "rule_a",
                    },
                    "values": [["300", "suppressed"]],
                }
            ]
        }

        batch = parse_tail_response(payload)

        assert batch.entries[0].labels["suppression_matches"] == "rule_a"

    def test_invalid_value_tuple_is_rejected(self):
        payload = {
            "status": "success",
            "data": {
                "resultType": "streams",
                "result": [{"stream": {}, "values": [["100"]]}],
            },
        }

        with pytest.raises(LokiProtocolError):
            parse_query_range_response(payload)

    def test_tail_url_switches_https_to_wss(self):
        assert _tail_url("https://loki.example") == (
            "wss://loki.example/loki/api/v1/tail"
        )


class _SubdivisionClient(LokiClient):
    def __init__(self, responses, *, page_limit=2, max_page_limit=8):
        super().__init__(
            "https://loki.example",
            "user",
            "password",
            page_limit=page_limit,
            max_page_limit=max_page_limit,
            session=object(),
        )
        self.responses = responses
        self.calls = []

    async def _query_range_once(self, start_ns, end_ns, limit):
        self.calls.append((start_ns, end_ns, limit))
        response = self.responses[(start_ns, end_ns, limit)]
        return response


class TestHistorySubdivision:
    def test_saturated_interval_is_split_and_deduplicated(self):
        duplicate = _loki_entry(5, "duplicate")
        left = _loki_entry(2, "left")
        right = _loki_entry(8, "right")

        client = _SubdivisionClient({
            (0, 10, 2): ([duplicate, right], True),
            (0, 5, 2): ([left, duplicate], False),
            (5, 10, 2): ([duplicate, right], False),
        })

        entries = asyncio.run(client.query_range(0, 10))

        assert [e.line for e in entries] == ["left", "duplicate", "right"]
        assert (0, 5, 2) in client.calls
        assert (5, 10, 2) in client.calls

    def test_single_nanosecond_interval_increases_limit(self):
        a = _loki_entry(5, "a")
        b = _loki_entry(5, "b")
        c = _loki_entry(5, "c")

        client = _SubdivisionClient(
            {
                (5, 6, 2): ([a, b], True),
                (5, 6, 4): ([a, b, c], False),
            },
            page_limit=2,
            max_page_limit=4,
        )

        entries = asyncio.run(client.query_range(5, 6))

        assert {e.line for e in entries} == {"a", "b", "c"}
        assert client.calls == [(5, 6, 2), (5, 6, 4)]

    def test_unpageable_saturated_timestamp_fails_explicitly(self):
        a = _loki_entry(5, "a")
        b = _loki_entry(5, "b")

        client = _SubdivisionClient(
            {
                (5, 6, 2): ([a, b], True),
                (5, 6, 4): ([a, b], True),
            },
            page_limit=2,
            max_page_limit=4,
        )

        with pytest.raises(LokiHistoryIncompleteError):
            asyncio.run(client.query_range(5, 6))


class TestLokiSync:
    def test_startup_range_covers_window_through_boundary(self):
        sync = LokiSync(OperationalEventStore(history_duration="PT24H"))

        start, end = sync.startup_range(100_000_000_000_000)

        assert end == 100_000_000_000_001
        assert end - 1 - start == 24 * 60 * 60 * 1_000_000_000

    def test_catchup_uses_coverage_checkpoint_with_overlap(self):
        sync = LokiSync(
            OperationalEventStore(history_duration="PT24H"),
            overlap_seconds=5,
        )
        sync.mark_history_covered(100_000_000_000)

        start, end = sync.catchup_range(200_000_000_000)

        assert start == 95_000_000_000
        assert end == 200_000_000_001

    def test_catchup_is_bounded_by_visible_history_window(self):
        store = OperationalEventStore(history_duration="PT10S")
        sync = LokiSync(store, overlap_seconds=5)
        sync.mark_history_covered(1)

        start, _end = sync.catchup_range(100_000_000_000)

        assert start == 90_000_000_000

    def test_tail_merge_deduplicates_and_reports_drops(self):
        store = OperationalEventStore(history_duration="PT1H")
        sync = LokiSync(store)
        entry = _loki_entry(100)

        added, catchup = sync.merge_tail_batch(
            TailBatch(entries=(entry,), dropped_entries=None),
            boundary_ns=200,
        )
        assert len(added) == 1
        assert catchup is False

        added, catchup = sync.merge_tail_batch(
            TailBatch(entries=(entry,), dropped_entries=[{"timestamp": "100"}]),
            boundary_ns=200,
        )
        assert added == []
        assert catchup is True

    def test_tail_merge_filters_non_warning_syslog(self):
        store = OperationalEventStore()
        sync = LokiSync(store)

        added, _ = sync.merge_tail_batch(
            TailBatch(entries=(_loki_entry(100, severity="informational"),)),
            boundary_ns=200,
        )

        assert added == []
        assert store.events == []


class _HistoryClient:
    def __init__(self, entries):
        self.entries = entries
        self.calls = []

    async def query_range(self, start_ns, end_ns):
        self.calls.append((start_ns, end_ns))
        return self.entries


class TestHistorySync:
    def test_successful_history_sync_advances_checkpoint(self):
        store = OperationalEventStore(history_duration="PT10S")
        sync = LokiSync(store)
        client = _HistoryClient([_loki_entry(95_000_000_000)])

        added = asyncio.run(sync.sync_history(
            client,
            100_000_000_000,
            initial=True,
        ))

        assert len(added) == 1
        assert sync.history_covered_through_ns == 100_000_000_000
        assert client.calls == [(90_000_000_000, 100_000_000_001)]

    def test_failed_history_sync_does_not_advance_checkpoint(self):
        class FailingClient:
            async def query_range(self, _start_ns, _end_ns):
                raise RuntimeError("history failed")

        sync = LokiSync(OperationalEventStore())

        with pytest.raises(RuntimeError):
            asyncio.run(sync.sync_history(FailingClient(), 100, initial=True))

        assert sync.history_covered_through_ns is None



class _FakeClientContext:
    def __init__(self, client):
        self.client = client

    async def __aenter__(self):
        return self.client

    async def __aexit__(self, _exc_type, _exc, _tb):
        return False


class _ScriptedClient:
    def __init__(self, history_entries, tail_batches, *, history_error=None):
        self.history_entries = history_entries
        self.tail_batches = tail_batches
        self.history_error = history_error
        self.history_calls = []

    async def query_range(self, start_ns, end_ns):
        self.history_calls.append((start_ns, end_ns))
        if self.history_error is not None:
            raise self.history_error
        return list(self.history_entries)

    async def tail(self, *, connected_event=None):
        if connected_event is not None:
            connected_event.set()
        for batch in self.tail_batches:
            if isinstance(batch, Exception):
                raise batch
            yield batch


class TestLokiEventSource:
    def test_initial_history_does_not_notify(self):
        store = OperationalEventStore(history_duration="PT10S")
        notifications = []
        client = _ScriptedClient(
            history_entries=[_loki_entry(95_000_000_000, "history")],
            tail_batches=[],
        )
        source = LokiEventSource(
            lambda: _FakeClientContext(client),
            store,
            on_new_events=lambda events: notifications.extend(events),
            reconnect_initial_seconds=1,
            reconnect_max_seconds=1,
            time_ns=lambda: 100_000_000_000,
        )

        async def exercise():
            with pytest.raises(Exception):
                await asyncio.wait_for(
                    source._connected_session(client, initial=True),
                    timeout=0.1,
                )

        asyncio.run(exercise())

        assert [event.summary for event in store.events] == ["history"]
        assert notifications == []

    def test_failure_attention_only_once_per_failure_epoch(self):
        store = OperationalEventStore()
        failures = []
        source = LokiEventSource(
            lambda: None,
            store,
            on_failure=lambda state, message: failures.append((state, message)),
            time_ns=iter([10, 20, 30, 40]).__next__,
        )

        source._set_degraded("disconnected", "down")
        source._set_degraded("catching-up", "recovering")
        source._set_degraded("history-failed", "still down")

        assert len(failures) == 1
        assert len(store.events) == 1
        assert store.events[0].event_id == "source-state:loki"
        assert store.events[0].state == "history-failed"

        source._set_healthy()
        source._set_degraded("disconnected", "down again")

        assert len(failures) == 2

    def test_reconnect_history_notifies_only_new_deduplicated_events(self):
        store = OperationalEventStore(history_duration="PT10S")
        sync = LokiSync(store)
        existing_entry = _loki_entry(95_000_000_000, "existing")
        existing_event = operational_event_from_loki(existing_entry)
        store.merge([existing_event])
        sync.mark_history_covered(90_000_000_000)

        notifications = []
        client = _HistoryClient([
            existing_entry,
            _loki_entry(96_000_000_000, "new"),
        ])
        source = LokiEventSource(
            lambda: None,
            store,
            on_new_events=lambda events: notifications.extend(events),
            time_ns=lambda: 100_000_000_000,
        )
        source.sync = sync

        asyncio.run(source._catch_up(client, 100_000_000_000, initial=False))

        assert [event.summary for event in notifications] == ["new"]

    def test_dropped_entries_require_catchup_without_duplicate_state_rows(self):
        store = OperationalEventStore(history_duration="PT10S")
        failures = []
        source = LokiEventSource(
            lambda: None,
            store,
            on_failure=lambda state, message: failures.append((state, message)),
            time_ns=lambda: 100_000_000_000,
        )

        source._set_degraded("catching-up", "first")
        source._set_degraded("catching-up", "retry")

        assert len(failures) == 1
        assert len(store.events) == 1
        assert store.events[0].summary == "retry"

    def test_teardown_cancels_running_task(self):
        store = OperationalEventStore()
        source = LokiEventSource(lambda: None, store)

        async def exercise():
            blocker = asyncio.Event()

            async def never_finishes():
                await blocker.wait()

            source._task = asyncio.create_task(never_finishes())
            assert source.running
            source.teardown()
            await source.wait_stopped()
            assert source._task.cancelled()

        asyncio.run(exercise())
