"""Tests for Jarvis alert normalization and reconciliation."""

import asyncio

from jarvis_events import JarvisEventSource, JarvisSync, _iso_to_ns
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

    async def get_history(self, fingerprint, cluster_name, *, cutoff_ns):
        self.history_calls.append((cluster_name, fingerprint, cutoff_ns))
        return self.histories[(cluster_name, fingerprint)]


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
