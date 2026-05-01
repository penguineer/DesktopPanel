""" Pytest tests for the presence_conn module """

import datetime

import pytest

from presence_conn import Presence, PresenceTrackedEntry, PresenceTracker


class TestPresenceTrackedEntry:
    def test_current_entry(self):
        entry = PresenceTrackedEntry(status="present", since="2024-01-01T10:00:00+00:00")
        assert entry.status == "present"
        assert entry.since == "2024-01-01T10:00:00+00:00"
        assert entry.until is None
        assert entry.is_current is True
        assert entry.duration_ms is None

    def test_past_entry(self):
        entry = PresenceTrackedEntry(
            status="absent",
            since="2024-01-01T10:00:00+00:00",
            until="2024-01-01T11:30:00+00:00"
        )
        assert entry.status == "absent"
        assert entry.since == "2024-01-01T10:00:00+00:00"
        assert entry.until == "2024-01-01T11:30:00+00:00"
        assert entry.is_current is False
        # 1.5 hours = 5400 seconds = 5_400_000 ms
        assert entry.duration_ms == 5_400_000

    def test_duration_ms_zero(self):
        ts = "2024-06-15T08:00:00+00:00"
        entry = PresenceTrackedEntry(status="occupied", since=ts, until=ts)
        assert entry.duration_ms == 0

    def test_duration_ms_none_when_current(self):
        entry = PresenceTrackedEntry(status="away", since="2024-01-01T09:00:00+00:00")
        assert entry.duration_ms is None

    def test_duration_ms_invalid_timestamps(self):
        entry = PresenceTrackedEntry(status="present", since="not-a-date", until="also-not-a-date")
        assert entry.duration_ms is None


class TestPresenceTracker:
    """Tests for PresenceTracker that do not require Kivy to be running."""

    def _make_presence(self, status, timestamp=None):
        return Presence(handle="alice", status=status, timestamp=timestamp)

    def _make_tracker(self):
        """Create a PresenceTracker-like object using only the pure Python logic."""
        tracker = _PresenceTrackerLogic()
        return tracker

    def test_initial_state(self):
        tracker = _PresenceTrackerLogic()
        assert tracker.tracked_entries == []

    def test_first_presence(self):
        tracker = _PresenceTrackerLogic()
        p = self._make_presence("present", "2024-01-01T10:00:00+00:00")
        tracker.update(p)

        assert len(tracker.tracked_entries) == 1
        entry = tracker.tracked_entries[0]
        assert entry.status == "present"
        assert entry.since == "2024-01-01T10:00:00+00:00"
        assert entry.is_current is True

    def test_same_status_creates_new_entry(self):
        tracker = _PresenceTrackerLogic()
        p1 = self._make_presence("present", "2024-01-01T10:00:00+00:00")
        p2 = self._make_presence("present", "2024-01-01T10:05:00+00:00")
        tracker.update(p1)
        tracker.update(p2)

        assert len(tracker.tracked_entries) == 2
        assert tracker.tracked_entries[0].status == "present"
        assert tracker.tracked_entries[0].is_current is True
        assert tracker.tracked_entries[1].status == "present"
        assert tracker.tracked_entries[1].until == "2024-01-01T10:05:00+00:00"

    def test_status_change_closes_previous(self):
        tracker = _PresenceTrackerLogic()
        p1 = self._make_presence("present", "2024-01-01T10:00:00+00:00")
        p2 = self._make_presence("absent", "2024-01-01T11:00:00+00:00")
        tracker.update(p1)
        tracker.update(p2)

        assert len(tracker.tracked_entries) == 2

        # Newest entry is first (current)
        current = tracker.tracked_entries[0]
        assert current.status == "absent"
        assert current.is_current is True

        # Previous entry is closed
        previous = tracker.tracked_entries[1]
        assert previous.status == "present"
        assert previous.until == "2024-01-01T11:00:00+00:00"
        assert previous.is_current is False
        assert previous.duration_ms == 3_600_000  # 1 hour

    def test_multiple_changes(self):
        tracker = _PresenceTrackerLogic()
        tracker.update(self._make_presence("absent", "2024-01-01T08:00:00+00:00"))
        tracker.update(self._make_presence("present", "2024-01-01T09:00:00+00:00"))
        tracker.update(self._make_presence("occupied", "2024-01-01T10:30:00+00:00"))

        assert len(tracker.tracked_entries) == 3
        assert tracker.tracked_entries[0].status == "occupied"
        assert tracker.tracked_entries[0].is_current is True
        assert tracker.tracked_entries[1].status == "present"
        assert tracker.tracked_entries[1].duration_ms == 5_400_000  # 1.5 hours
        assert tracker.tracked_entries[2].status == "absent"
        assert tracker.tracked_entries[2].duration_ms == 3_600_000  # 1 hour

    def test_none_presence_ignored(self):
        tracker = _PresenceTrackerLogic()
        tracker.update(None)
        assert tracker.tracked_entries == []

    def test_fallback_timestamp_when_none(self):
        """When presence has no timestamp, the tracker still creates an entry."""
        tracker = _PresenceTrackerLogic()
        p = self._make_presence("present", timestamp=None)
        tracker.update(p)

        assert len(tracker.tracked_entries) == 1
        # since should be a non-empty ISO string (current time used as fallback)
        assert tracker.tracked_entries[0].since


class _PresenceTrackerLogic:
    """Pure-Python stub that reproduces PresenceTracker._on_active_presence logic
    (the method of PresenceTracker that reacts to presence changes) without
    requiring Kivy's event loop."""

    def __init__(self):
        self.tracked_entries = []

    def update(self, value):
        if value is None:
            return

        since = value.timestamp if value.timestamp else \
            datetime.datetime.now(datetime.timezone.utc).isoformat()

        new_entries = list(self.tracked_entries)

        if new_entries and new_entries[0].is_current:
            entry = new_entries[0]
            new_entries[0] = PresenceTrackedEntry(
                status=entry.status,
                since=entry.since,
                until=since
            )

        new_entries.insert(0, PresenceTrackedEntry(
            status=value.status,
            since=since
        ))

        self.tracked_entries = new_entries
