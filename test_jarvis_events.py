"""Tests for Jarvis alert normalization and reconciliation."""

import asyncio

import pytest

from jarvis_events import (
    JarvisBudgetError,
    JarvisEventSource,
    JarvisSync,
    _iso_to_ns,
)
from operational_events import JarvisAlertEvent, JarvisEventStore


def _alert(
    fingerprint="abc",
    cluster="example",
    state="active",
    starts_at="2026-09-25T22:41:11.997Z",
    ends_at=None,
    severity="warning",
    summary="Example alert",
):
    return {
        "fingerprint": fingerprint,
        "clusterName": cluster,
        "status": {
            "inhibitedBy": [],
            "silencedBy": [],
            "state": state,
        },
        "startsAt": starts_at,
        "endsAt": ends_at,
        "updatedAt": starts_at,
        "labels": {
            "alertname": "ExampleAlert",
            "host": "host-a",
            "severity": severity,
        },
        "annotations": {
            "summary": summary,
            "description": "Example description",
        },
        "activeClaim": None,
    }


def _history(
    event_id,
    status,
    *,
    fingerprint="abc",
    cluster="example",
    starts_at="2026-09-25T22:41:11.997Z",
    recorded_at="2026-09-25T22:41:23.162686Z",
    summary="Example alert",
):
    return {
        "id": event_id,
        "fingerprint": fingerprint,
        "clusterName": cluster,
        "alertmanagerUrl": "http://alertmanager.example:9093",
        "status": status,
        "startsAt": starts_at,
        "endsAt": None,
        "annotations": (
            '{"description":"Example description","summary":"%s"}' % summary
        ),
        "recordedAt": recorded_at,
    }


class _FakeClient:
    def __init__(self, current, resolved, histories):
        self.current = current
        self.resolved = resolved
        self.histories = histories
        self.history_calls = []

    async def get_alerts(self, *, state=None):
        return self.resolved if state == "resolved" else self.current

    async def get_history(
        self,
        fingerprint,
        cluster_name,
        *,
        cutoff_ns,
        budget=None,
    ):
        self.history_calls.append((cluster_name, fingerprint, cutoff_ns))
        history = self.histories[(cluster_name, fingerprint)]
        if budget is not None:
            budget.consume_page(len(history))
        return history


class TestJarvisSync:
    def test_persistent_history_wins_for_resolution_timestamp(self):
        current = [_alert(
            state="resolved",
            ends_at="2026-09-25T22:45:11.997Z",
        )]
        resolved = [_alert(
            state="resolved",
            ends_at="2026-09-25T22:43:23.104058Z",
        )]
        history = [
            _history(
                41,
                "resolved",
                recorded_at="2026-09-25T22:43:23.104058Z",
            ),
            _history(40, "firing"),
        ]
        client = _FakeClient(
            current,
            resolved,
            {("example", "abc"): history},
        )
        store = JarvisEventStore(history_duration="PT24H")
        sync = JarvisSync(store)

        events = asyncio.run(sync.snapshot(
            client,
            _iso_to_ns("2026-09-26T00:00:00Z"),
        ))

        assert len(events) == 1
        assert events[0].status == "resolved"
        assert events[0].resolved_at == "2026-09-25T22:43:23.104058Z"
        assert events[0].timestamp_ns == _iso_to_ns(
            "2026-09-25T22:43:23.104058Z"
        )

    def test_repeated_logical_alerts_are_distinct_occurrences(self):
        first_start = "2026-09-25T20:00:00Z"
        second_start = "2026-09-25T22:00:00Z"
        resolved = [_alert(
            starts_at=second_start,
            state="resolved",
            ends_at="2026-09-25T22:05:00Z",
        )]
        history = [
            _history(
                4,
                "resolved",
                starts_at=second_start,
                recorded_at="2026-09-25T22:05:00Z",
                summary="Second occurrence",
            ),
            _history(
                3,
                "firing",
                starts_at=second_start,
                recorded_at="2026-09-25T22:00:10Z",
                summary="Second occurrence",
            ),
            _history(
                2,
                "resolved",
                starts_at=first_start,
                recorded_at="2026-09-25T20:05:00Z",
                summary="First occurrence",
            ),
            _history(
                1,
                "firing",
                starts_at=first_start,
                recorded_at="2026-09-25T20:00:10Z",
                summary="First occurrence",
            ),
        ]
        client = _FakeClient(
            [],
            resolved,
            {("example", "abc"): history},
        )

        events = asyncio.run(JarvisSync(
            JarvisEventStore(history_duration="PT24H")
        ).snapshot(
            client,
            _iso_to_ns("2026-09-26T00:00:00Z"),
        ))

        assert len(events) == 2
        assert len({event.event_id for event in events}) == 2
        assert {event.starts_at for event in events} == {first_start, second_start}

    def test_suppressed_occurrence_does_not_reappear_when_resolved(self):
        resolved = [_alert(
            state="resolved",
            ends_at="2026-09-25T22:05:00Z",
        )]
        history = [
            _history(
                3,
                "resolved",
                recorded_at="2026-09-25T22:05:00Z",
            ),
            _history(
                2,
                "suppressed",
                recorded_at="2026-09-25T22:02:00Z",
            ),
            _history(
                1,
                "firing",
                recorded_at="2026-09-25T22:00:10Z",
            ),
        ]
        client = _FakeClient(
            [],
            resolved,
            {("example", "abc"): history},
        )

        events = asyncio.run(JarvisSync(
            JarvisEventStore(history_duration="PT24H")
        ).snapshot(
            client,
            _iso_to_ns("2026-09-26T00:00:00Z"),
        ))

        assert events == []

    def test_reconciliation_history_budget_is_global(self):
        first = _alert(
            fingerprint="first",
            starts_at="2026-09-25T20:00:00Z",
            state="resolved",
            ends_at="2026-09-25T20:05:00Z",
        )
        second = _alert(
            fingerprint="second",
            starts_at="2026-09-25T21:00:00Z",
            state="resolved",
            ends_at="2026-09-25T21:05:00Z",
        )
        client = _FakeClient(
            [],
            [first, second],
            {
                ("example", "first"): [
                    _history(
                        1,
                        "resolved",
                        fingerprint="first",
                        starts_at="2026-09-25T20:00:00Z",
                        recorded_at="2026-09-25T20:05:00Z",
                    ),
                ],
                ("example", "second"): [
                    _history(
                        2,
                        "resolved",
                        fingerprint="second",
                        starts_at="2026-09-25T21:00:00Z",
                        recorded_at="2026-09-25T21:05:00Z",
                    ),
                ],
            },
        )
        sync = JarvisSync(
            JarvisEventStore(history_duration="PT24H"),
            max_history_rows=1,
            max_history_pages=10,
        )

        with pytest.raises(JarvisBudgetError, match="history row"):
            asyncio.run(sync.snapshot(
                client,
                _iso_to_ns("2026-09-26T00:00:00Z"),
            ))

    def test_mutable_payload_does_not_change_occurrence_identity(self):
        store = JarvisEventStore()
        starts_ns = _iso_to_ns("2026-09-25T22:00:00Z")
        first = JarvisAlertEvent(
            event_id="stable",
            timestamp_ns=starts_ns,
            source="jarvis",
            source_annotation="host-a",
            summary="first summary",
            cluster_name="example",
            fingerprint="abc",
            starts_at="2026-09-25T22:00:00Z",
            starts_at_ns=starts_ns,
            resolved_at=None,
            status="active",
            severity="warning",
            labels={"severity": "warning"},
            annotations={"summary": "first summary"},
        )
        changed = JarvisAlertEvent(
            **{
                **first.__dict__,
                "summary": "changed summary",
                "severity": "critical",
                "labels": {"severity": "critical"},
                "annotations": {"summary": "changed summary"},
            }
        )

        assert store.reconcile([first]) == [first]
        assert store.reconcile([changed]) == []
        assert store.events == [changed]

    def test_suppressed_occurrence_is_not_stored(self):
        starts_ns = _iso_to_ns("2026-09-25T22:00:00Z")
        suppressed = JarvisAlertEvent(
            event_id="suppressed",
            timestamp_ns=starts_ns,
            source="jarvis",
            source_annotation="host-a",
            summary="suppressed",
            cluster_name="example",
            fingerprint="abc",
            starts_at="2026-09-25T22:00:00Z",
            starts_at_ns=starts_ns,
            resolved_at=None,
            status="suppressed",
            severity="warning",
            labels={},
            annotations={},
        )

        store = JarvisEventStore()
        assert store.reconcile([suppressed]) == []
        assert store.events == []

    def test_failure_marks_last_known_alert_stale_without_removing_it(self):
        starts_ns = _iso_to_ns("2026-09-25T22:00:00Z")
        event = JarvisAlertEvent(
            event_id="stable",
            timestamp_ns=starts_ns,
            source="jarvis",
            source_annotation="host-a",
            summary="active",
            cluster_name="example",
            fingerprint="abc",
            starts_at="2026-09-25T22:00:00Z",
            starts_at_ns=starts_ns,
            resolved_at=None,
            status="active",
            severity="warning",
            labels={},
            annotations={},
        )
        store = JarvisEventStore()
        store.reconcile([event])

        assert store.mark_stale() is True
        stale = next(item for item in store.events if isinstance(item, JarvisAlertEvent))
        assert stale.event_id == "stable"
        assert stale.stale is True


class _FakeSync:
    def __init__(self, snapshots):
        self.snapshots = list(snapshots)

    async def snapshot(self, _client, _boundary_ns):
        return self.snapshots.pop(0)


class TestJarvisEventSource:
    def test_bootstrap_is_quiet_but_later_transition_notifies(self):
        starts_ns = _iso_to_ns("2026-09-25T22:00:00Z")
        active = JarvisAlertEvent(
            event_id="stable",
            timestamp_ns=starts_ns,
            source="jarvis",
            source_annotation="host-a",
            summary="active",
            cluster_name="example",
            fingerprint="abc",
            starts_at="2026-09-25T22:00:00Z",
            starts_at_ns=starts_ns,
            resolved_at=None,
            status="active",
            severity="warning",
            labels={},
            annotations={},
        )
        resolved = JarvisAlertEvent(
            **{
                **active.__dict__,
                "timestamp_ns": _iso_to_ns("2026-09-25T22:05:00Z"),
                "resolved_at": "2026-09-25T22:05:00Z",
                "status": "resolved",
            }
        )
        notifications = []
        source = JarvisEventSource(
            lambda: None,
            JarvisEventStore(),
            on_new_events=lambda events: notifications.append(list(events)),
            time_ns=lambda: _iso_to_ns("2026-09-25T23:00:00Z"),
        )
        source.sync = _FakeSync([[active], [resolved]])

        asyncio.run(source._reconcile(object()))
        assert notifications == []

        asyncio.run(source._reconcile(object()))
        assert notifications == [[resolved]]

    def test_recreated_source_marks_retained_state_stale_on_first_failure(self):
        starts_ns = _iso_to_ns("2026-09-25T22:00:00Z")
        event = JarvisAlertEvent(
            event_id="stable",
            timestamp_ns=starts_ns,
            source="jarvis",
            source_annotation="host-a",
            summary="active",
            cluster_name="example",
            fingerprint="abc",
            starts_at="2026-09-25T22:00:00Z",
            starts_at_ns=starts_ns,
            resolved_at=None,
            status="active",
            severity="warning",
            labels={},
            annotations={},
        )
        store = JarvisEventStore()
        store.reconcile([event])
        source = JarvisEventSource(
            lambda: None,
            store,
            has_previous_state=True,
            time_ns=lambda: 123,
        )

        source._set_degraded("unreachable", "Jarvis unavailable")

        retained = next(
            item for item in store.events
            if isinstance(item, JarvisAlertEvent)
        )
        assert retained.event_id == "stable"
        assert retained.stale is True

    def test_failure_before_first_success_does_not_invent_alerts(self):
        failures = []
        store = JarvisEventStore()
        source = JarvisEventSource(
            lambda: None,
            store,
            on_failure=lambda state, message: failures.append((state, message)),
            time_ns=lambda: 123,
        )

        source._set_degraded("unreachable", "Jarvis unavailable")

        assert not any(isinstance(item, JarvisAlertEvent) for item in store.events)
        assert failures == [("unreachable", "Jarvis unavailable")]


class _OneChangeClient:
    async def changes(self):
        yield {"type": "alerts_update"}


class _ContextClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, _exc_type, _exc, _tb):
        return False

    async def changes(self):
        while True:
            await asyncio.sleep(3600)
            yield {}


class _CountingSync:
    def __init__(self, snapshots_before_stop=2):
        self.calls = 0
        self.snapshots_before_stop = snapshots_before_stop

    async def snapshot(self, _client, _boundary_ns):
        self.calls += 1
        if self.calls > self.snapshots_before_stop:
            raise asyncio.CancelledError
        return []


class TestJarvisScheduling:
    def test_websocket_message_invalidates_http_snapshot(self):
        async def stop_sleep(_seconds):
            raise asyncio.CancelledError

        source = JarvisEventSource(
            lambda: None,
            JarvisEventStore(),
            sleep=stop_sleep,
        )

        async def run_watch():
            invalidated = asyncio.Event()
            try:
                await source._watch_changes(_OneChangeClient(), invalidated)
            except asyncio.CancelledError:
                pass
            return invalidated.is_set()

        assert asyncio.run(run_watch()) is True

    def test_websocket_invalidation_during_reconcile_is_not_lost(self):
        class RaceClient:
            def __init__(self):
                self.sync_started = asyncio.Event()
                self.ws_delivered = asyncio.Event()

            async def __aenter__(self):
                return self

            async def __aexit__(self, _exc_type, _exc, _tb):
                return False

            async def changes(self):
                await self.sync_started.wait()
                yield {"type": "alerts_update"}
                self.ws_delivered.set()
                while True:
                    await asyncio.sleep(3600)

        class RaceSync:
            def __init__(self):
                self.calls = 0

            async def snapshot(self, client, _boundary_ns):
                self.calls += 1
                if self.calls == 1:
                    client.sync_started.set()
                    await client.ws_delivered.wait()
                    return []
                raise asyncio.CancelledError

        client = RaceClient()
        source = JarvisEventSource(
            lambda: client,
            JarvisEventStore(),
            poll_seconds=10,
        )
        sync = RaceSync()
        source.sync = sync

        async def run_source():
            try:
                await asyncio.wait_for(source.run(), timeout=0.25)
            except asyncio.CancelledError:
                pass

        asyncio.run(run_source())

        assert sync.calls == 2

    def test_periodic_poll_reconciles_without_websocket_messages(self):
        source = JarvisEventSource(
            lambda: _ContextClient(),
            JarvisEventStore(),
            poll_seconds=0.001,
            disconnected_poll_seconds=0.001,
        )
        sync = _CountingSync(snapshots_before_stop=2)
        source.sync = sync

        try:
            asyncio.run(source.run())
        except asyncio.CancelledError:
            pass

        assert sync.calls == 3

