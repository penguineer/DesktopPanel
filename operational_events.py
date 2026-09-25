"""Operational event models and source-specific in-memory stores.

Network I/O and widget rendering deliberately stay out of this module. Kivy
properties make each source store observable without coupling source
reconciliation semantics to the presentation layer.
"""

from dataclasses import dataclass, replace
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


class OperationalEventCapacityError(RuntimeError):
    """Raised when a defensive in-memory event ceiling would be exceeded."""


@dataclass(frozen=True)
class LokiEntry:
    """One Loki log entry flattened out of a stream response."""

    timestamp_ns: int
    labels: Mapping[str, str]
    line: str

    @property
    def source(self) -> Optional[str]:
        return self.labels.get("source")

    def _identity_labels(self):
        """Return source-specific labels that define event identity.

        Loki may expose auxiliary or structured-metadata labels differently
        between query_range and tail. Those labels are useful for display but
        must not make the same source event acquire a different stable ID.
        """
        if self.source == "syslog":
            keys = ("source", "host", "application", "severity", "facility")
            return {key: self.labels.get(key, "") for key in keys}

        # Future source adapters should define their own stable identity label
        # set before they are enabled for display.
        return dict(self.labels)

    @property
    def stable_id(self) -> str:
        """Return a deterministic ID shared by history and tail responses."""

        labels_json = json.dumps(
            self._identity_labels(),
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
class JarvisAlertEvent(OperationalEvent):
    """One visible occurrence of a Jarvis alert.

    Identity deliberately contains only the logical alert identity and the
    Alertmanager occurrence start instant. Mutable labels, annotations,
    severity, lifecycle state, and resolution time are payload, not identity.
    """

    cluster_name: str
    fingerprint: str
    starts_at: str
    starts_at_ns: int
    resolved_at: Optional[str]
    status: str
    severity: str
    labels: Mapping[str, str]
    annotations: Mapping[str, str]
    stale: bool = False

    @property
    def needs_attention(self):
        return self.status in ("active", "unprocessed")


@dataclass(frozen=True)
class SourceStateEvent(OperationalEvent):
    """Synthetic event describing a current degraded source state."""

    state: str


def jarvis_occurrence_id(cluster_name, fingerprint, starts_at_ns):
    """Return the stable ID for one Jarvis alert occurrence."""

    payload = json.dumps(
        [cluster_name, fingerprint, int(starts_at_ns)],
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return "jarvis:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def operational_event_from_loki(entry: LokiEntry) -> Optional[OperationalEvent]:
    """Dispatch a Loki entry to its source-specific event parser."""

    if entry.source == "syslog":
        return SyslogEvent.from_loki(entry)
    return None


class OperationalEventStore(EventDispatcher):
    """Observable Loki-side operational event collection."""

    events = ListProperty([])
    history_duration = StringProperty("PT24H")
    history_seconds = NumericProperty(24 * 60 * 60)

    def __init__(
        self,
        *,
        history_duration="PT24H",
        source_order: Sequence[str] = ("loki",),
        max_events=20000,
        **kwargs,
    ):
        if max_events <= 0:
            raise ValueError("max_events must be greater than zero")
        super().__init__(**kwargs)
        self.max_events = max_events
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

        incoming = list(incoming)
        for event in incoming:
            if isinstance(event, SourceStateEvent):
                raise TypeError("SourceStateEvent must be managed with set_source_state()")

        new_ids = {
            event.event_id
            for event in incoming
            if event.event_id not in self._normal_events
        }
        if len(self._normal_events) + len(new_ids) > self.max_events:
            raise OperationalEventCapacityError(
                "Operational event store exceeds the defensive in-memory entry limit"
            )

        added = []
        seen = set()
        for event in incoming:
            if event.event_id in self._normal_events or event.event_id in seen:
                continue
            seen.add(event.event_id)
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


class JarvisEventStore(EventDispatcher):
    """Observable Jarvis alert-occurrence store with authoritative reconciliation."""

    events = ListProperty([])
    history_duration = StringProperty("PT24H")
    history_seconds = NumericProperty(24 * 60 * 60)

    def __init__(self, *, history_duration="PT24H", max_events=20000, **kwargs):
        if max_events <= 0:
            raise ValueError("max_events must be greater than zero")
        super().__init__(**kwargs)
        self.max_events = max_events
        self._alerts = {}
        self._source_states = {}
        self._expanded_ids = set()
        self.history_duration = history_duration

    def on_history_duration(self, _instance, value):
        seconds = parse_iso8601_duration(value)
        if seconds <= 0:
            raise ValueError("Operational event history duration must be greater than zero")
        self.history_seconds = seconds

    def reconcile(self, incoming):
        """Replace the authoritative visible Jarvis snapshot.

        Returns occurrences that represent a newly visible occurrence or a
        lifecycle transition. Pure payload refreshes (including clearing stale)
        are intentionally quiet.
        """

        incoming_by_id = {}
        for event in incoming:
            if not isinstance(event, JarvisAlertEvent):
                raise TypeError("JarvisEventStore only accepts JarvisAlertEvent")
            if event.status == "suppressed":
                continue
            incoming_by_id[event.event_id] = event

        if len(incoming_by_id) > self.max_events:
            raise OperationalEventCapacityError(
                "Jarvis event store exceeds the defensive in-memory entry limit"
            )

        changed = []
        for event_id, event in incoming_by_id.items():
            previous = self._alerts.get(event_id)
            if previous is None or previous.status != event.status:
                changed.append(event)

        removed_ids = set(self._alerts) - set(incoming_by_id)
        self._alerts = incoming_by_id
        self._expanded_ids.difference_update(removed_ids)
        self._refresh()
        return changed

    def mark_stale(self):
        changed = False
        stale = {}
        for event_id, event in self._alerts.items():
            if event.stale:
                stale[event_id] = event
            else:
                stale[event_id] = replace(event, stale=True)
                changed = True
        if changed:
            self._alerts = stale
            self._refresh()
        return changed

    def set_source_state(self, source, state, message, *, timestamp_ns):
        if source != "jarvis":
            raise ValueError("JarvisEventStore only owns the jarvis source state")

        previous = self._source_states.get(source)
        is_new_transition = previous is None or previous.state != state
        effective_timestamp = timestamp_ns if is_new_transition else previous.timestamp_ns
        event = SourceStateEvent(
            event_id="source-state:jarvis",
            timestamp_ns=effective_timestamp,
            source="jarvis",
            source_annotation="jarvis",
            summary=message,
            state=state,
        )
        if previous != event:
            self._source_states[source] = event
            self._refresh()
        return is_new_transition

    def clear_source_state(self, source):
        if source != "jarvis":
            return False
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
            key=lambda event: (event.source, event.event_id),
        )
        active = sorted(
            (event for event in self._alerts.values() if event.needs_attention),
            key=lambda event: (-event.starts_at_ns, event.event_id),
        )
        timeline = sorted(
            (event for event in self._alerts.values() if not event.needs_attention),
            key=lambda event: (-event.timestamp_ns, event.event_id),
        )
        self.events = source_states + active + timeline
