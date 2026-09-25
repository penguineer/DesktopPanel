"""Operational event model and Loki event normalization.

This module deliberately keeps network I/O and widget rendering out of the core
event model. Kivy properties are used on the store so UI code can observe
changes without coupling event semantics to widgets.
"""

from dataclasses import dataclass
import hashlib
import json
from typing import Mapping, Optional, Sequence

from kivy.event import EventDispatcher
from kivy.properties import ListProperty, NumericProperty, StringProperty

from timewidget import parse_iso8601_duration


_SYSLOG_SEVERITIES = {
    "emergency": 0,
    "emerg": 0,
    "alert": 1,
    "critical": 2,
    "crit": 2,
    "error": 3,
    "err": 3,
    "warning": 4,
    "warn": 4,
    "notice": 5,
    "informational": 6,
    "info": 6,
    "debug": 7,
}


@dataclass(frozen=True)
class LokiEntry:
    """One Loki log entry flattened out of a stream response."""

    timestamp_ns: int
    labels: Mapping[str, str]
    line: str

    @property
    def source(self) -> Optional[str]:
        return self.labels.get("source")

    @property
    def stable_id(self) -> str:
        """Return a deterministic ID shared by history and tail responses."""

        labels_json = json.dumps(
            dict(self.labels),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        digest = hashlib.sha256()
        digest.update(str(self.timestamp_ns).encode("ascii"))
        digest.update(b"\0")
        digest.update(labels_json.encode("utf-8"))
        digest.update(b"\0")
        digest.update(self.line.encode("utf-8"))
        return digest.hexdigest()


@dataclass(frozen=True)
class OperationalEvent:
    """Common presentation contract for operational events."""

    event_id: str
    timestamp_ns: int
    source: str
    source_annotation: str
    summary: str


@dataclass(frozen=True)
class SyslogEvent(OperationalEvent):
    """Operational event derived from one normalized syslog Loki entry."""

    host: str
    application: str
    severity: str
    facility: str
    labels: Mapping[str, str]

    @classmethod
    def from_loki(cls, entry: LokiEntry) -> Optional["SyslogEvent"]:
        labels = entry.labels
        if labels.get("source") != "syslog":
            return None

        if labels.get("alert_suppressed", "").lower() == "true":
            return None

        severity = labels.get("severity", "").lower()
        level = _SYSLOG_SEVERITIES.get(severity)
        if level is None or level > _SYSLOG_SEVERITIES["warning"]:
            return None

        host = labels.get("host", "")
        application = labels.get("application", "")
        facility = labels.get("facility", "")

        return cls(
            event_id=entry.stable_id,
            timestamp_ns=entry.timestamp_ns,
            source="syslog",
            source_annotation=host,
            summary=entry.line,
            host=host,
            application=application,
            severity=severity,
            facility=facility,
            labels=dict(labels),
        )


@dataclass(frozen=True)
class SourceStateEvent(OperationalEvent):
    """Synthetic event describing a current degraded source state."""

    state: str


def operational_event_from_loki(entry: LokiEntry) -> Optional[OperationalEvent]:
    """Dispatch a Loki entry to its source-specific event parser."""

    if entry.source == "syslog":
        return SyslogEvent.from_loki(entry)
    return None


class OperationalEventStore(EventDispatcher):
    """Observable, widget-independent operational event collection."""

    events = ListProperty([])
    history_duration = StringProperty("PT24H")
    history_seconds = NumericProperty(24 * 60 * 60)

    def __init__(self, *, history_duration="PT24H", source_order: Sequence[str] = ("loki",), **kwargs):
        super().__init__(**kwargs)
        self._normal_events = {}
        self._source_states = {}
        self._expanded_ids = set()
        self._source_order = {name: index for index, name in enumerate(source_order)}
        self.history_duration = history_duration

    def on_history_duration(self, _instance, value):
        seconds = parse_iso8601_duration(value)
        if seconds <= 0:
            raise ValueError("Operational event history duration must be greater than zero")
        self.history_seconds = seconds

    def merge(self, incoming):
        """Add unseen events and return the events that were newly inserted."""

        added = []
        for event in incoming:
            if isinstance(event, SourceStateEvent):
                raise TypeError("SourceStateEvent must be managed with set_source_state()")
            if event.event_id in self._normal_events:
                continue
            self._normal_events[event.event_id] = event
            added.append(event)

        if added:
            self._refresh()
        return added

    def prune_before(self, cutoff_ns):
        """Drop normal events older than cutoff_ns."""

        removed = {
            event_id
            for event_id, event in self._normal_events.items()
            if event.timestamp_ns < cutoff_ns
        }
        if not removed:
            return 0

        for event_id in removed:
            del self._normal_events[event_id]
        self._expanded_ids.difference_update(removed)
        self._refresh()
        return len(removed)

    def set_source_state(self, source, state, message, *, timestamp_ns):
        """Insert or update one synthetic state row for source.

        Returns True only for a new source-state transition. Repeated retries in
        the same state may update the message without becoming a new attention
        event.
        """

        previous = self._source_states.get(source)
        is_new_transition = previous is None or previous.state != state
        effective_timestamp = timestamp_ns if is_new_transition else previous.timestamp_ns

        event = SourceStateEvent(
            event_id=f"source-state:{source}",
            timestamp_ns=effective_timestamp,
            source=source,
            source_annotation=source,
            summary=message,
            state=state,
        )
        if previous != event:
            self._source_states[source] = event
            self._refresh()
        return is_new_transition

    def clear_source_state(self, source):
        event = self._source_states.pop(source, None)
        if event is None:
            return False
        self._expanded_ids.discard(event.event_id)
        self._refresh()
        return True

    def toggle_expanded(self, event_id):
        if event_id in self._expanded_ids:
            self._expanded_ids.remove(event_id)
            return False
        self._expanded_ids.add(event_id)
        return True

    def is_expanded(self, event_id):
        return event_id in self._expanded_ids

    def _refresh(self):
        source_states = sorted(
            self._source_states.values(),
            key=lambda event: (
                self._source_order.get(event.source, len(self._source_order)),
                event.source,
                event.event_id,
            ),
        )
        normal_events = sorted(
            self._normal_events.values(),
            key=lambda event: (-event.timestamp_ns, event.event_id),
        )
        self.events = source_states + normal_events
