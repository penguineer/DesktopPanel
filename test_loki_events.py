"""Tests for Loki transport normalization and synchronization."""

import pytest

from loki_events import (
    LokiClient,
    LokiHistoryIncompleteError,
    LokiProtocolError,
    LokiSync,
    TailBatch,
    _tail_url,
    parse_query_range_response,
    parse_tail_response,
)
from operational_events import LokiEntry, OperationalEventStore


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
    @pytest.mark.asyncio
    async def test_saturated_interval_is_split_and_deduplicated(self):
        duplicate = _loki_entry(5, "duplicate")
        left = _loki_entry(2, "left")
        right = _loki_entry(8, "right")

        client = _SubdivisionClient({
            (0, 10, 2): ([duplicate, right], True),
            (0, 5, 2): ([left, duplicate], False),
            (5, 10, 2): ([duplicate, right], False),
        })

        entries = await client.query_range(0, 10)

        assert [e.line for e in entries] == ["left", "duplicate", "right"]
        assert (0, 5, 2) in client.calls
        assert (5, 10, 2) in client.calls

    @pytest.mark.asyncio
    async def test_single_nanosecond_interval_increases_limit(self):
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

        entries = await client.query_range(5, 6)

        assert {e.line for e in entries} == {"a", "b", "c"}
        assert client.calls == [(5, 6, 2), (5, 6, 4)]

    @pytest.mark.asyncio
    async def test_unpageable_saturated_timestamp_fails_explicitly(self):
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
            await client.query_range(5, 6)


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
    @pytest.mark.asyncio
    async def test_successful_history_sync_advances_checkpoint(self):
        store = OperationalEventStore(history_duration="PT10S")
        sync = LokiSync(store)
        client = _HistoryClient([_loki_entry(95_000_000_000)])

        added = await sync.sync_history(
            client,
            100_000_000_000,
            initial=True,
        )

        assert len(added) == 1
        assert sync.history_covered_through_ns == 100_000_000_000
        assert client.calls == [(90_000_000_000, 100_000_000_001)]

    @pytest.mark.asyncio
    async def test_failed_history_sync_does_not_advance_checkpoint(self):
        class FailingClient:
            async def query_range(self, _start_ns, _end_ns):
                raise RuntimeError("history failed")

        sync = LokiSync(OperationalEventStore())

        with pytest.raises(RuntimeError):
            await sync.sync_history(FailingClient(), 100, initial=True)

        assert sync.history_covered_through_ns is None
