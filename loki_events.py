"""Async Loki transport and history/tail synchronization helpers."""

from dataclasses import dataclass
import json
from typing import Iterable, Optional
from urllib.parse import urlsplit, urlunsplit

import aiohttp

from operational_events import LokiEntry, OperationalEventStore, operational_event_from_loki


SYSLOG_QUERY = (
    '{source="syslog",alert_suppressed!="true",'
    'severity=~"warning|warn|err|error|crit|critical|alert|emerg|emergency"}'
)


class LokiError(RuntimeError):
    """Base class for Loki transport failures."""


class LokiProtocolError(LokiError):
    """Raised when Loki returns an unexpected response shape."""


class LokiHistoryIncompleteError(LokiError):
    """Raised when a saturated history interval cannot be subdivided further."""


@dataclass(frozen=True)
class TailBatch:
    """One Loki tail frame."""

    entries: tuple[LokiEntry, ...]
    dropped_entries: object = None


def _entries_from_streams(streams: Iterable[dict]) -> list[LokiEntry]:
    entries = []
    for result in streams:
        labels = result.get("stream")
        values = result.get("values")
        if not isinstance(labels, dict) or not isinstance(values, list):
            raise LokiProtocolError("Loki stream result is missing stream/values")

        for value in values:
            if not isinstance(value, list) or len(value) < 2:
                raise LokiProtocolError("Loki value tuple must contain timestamp and line")
            try:
                timestamp_ns = int(value[0])
            except (TypeError, ValueError) as exc:
                raise LokiProtocolError("Loki timestamp is not an integer") from exc
            line = value[1]
            if not isinstance(line, str):
                raise LokiProtocolError("Loki log line is not a string")
            entries.append(
                LokiEntry(timestamp_ns=timestamp_ns, labels=dict(labels), line=line)
            )
    return entries


def parse_query_range_response(payload: dict) -> list[LokiEntry]:
    """Flatten a Loki query_range response."""

    if payload.get("status") != "success":
        raise LokiProtocolError("Loki query_range response is not successful")

    data = payload.get("data")
    if not isinstance(data, dict) or data.get("resultType") != "streams":
        raise LokiProtocolError("Loki query_range resultType is not streams")

    result = data.get("result")
    if not isinstance(result, list):
        raise LokiProtocolError("Loki query_range result is not a list")
    return _entries_from_streams(result)


def parse_tail_response(payload: dict) -> TailBatch:
    """Flatten one Loki tail WebSocket frame."""

    streams = payload.get("streams", [])
    if not isinstance(streams, list):
        raise LokiProtocolError("Loki tail streams is not a list")
    return TailBatch(
        entries=tuple(_entries_from_streams(streams)),
        dropped_entries=payload.get("dropped_entries"),
    )


def _tail_url(base_url: str) -> str:
    parts = urlsplit(base_url)
    if parts.scheme == "https":
        scheme = "wss"
    elif parts.scheme == "http":
        scheme = "ws"
    else:
        raise ValueError(f"Unsupported Loki URL scheme: {parts.scheme!r}")
    path = parts.path.rstrip("/") + "/loki/api/v1/tail"
    return urlunsplit((scheme, parts.netloc, path, "", ""))


class LokiClient:
    """Small asyncio client for the externally exposed Loki API."""

    def __init__(
        self,
        base_url,
        username,
        password,
        *,
        query=SYSLOG_QUERY,
        page_limit=1000,
        max_page_limit=16000,
        session=None,
    ):
        if page_limit <= 0 or max_page_limit < page_limit:
            raise ValueError("Invalid Loki history limits")

        self.base_url = base_url.rstrip("/")
        self.query = query
        self.page_limit = page_limit
        self.max_page_limit = max_page_limit
        self._session = session
        self._owns_session = session is None
        self._auth = aiohttp.BasicAuth(username, password)

    async def __aenter__(self):
        if self._session is None:
            self._session = aiohttp.ClientSession(auth=self._auth)
        return self

    async def __aexit__(self, _exc_type, _exc, _tb):
        await self.close()

    async def close(self):
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    def _require_session(self):
        if self._session is None:
            raise RuntimeError("LokiClient must be entered before use")
        return self._session

    async def _query_range_once(self, start_ns, end_ns, limit):
        session = self._require_session()
        url = self.base_url + "/loki/api/v1/query_range"
        params = {
            "query": self.query,
            "start": str(start_ns),
            "end": str(end_ns),
            "limit": str(limit),
            "direction": "backward",
        }

        try:
            async with session.get(url, params=params, auth=self._auth) as response:
                if response.status != 200:
                    body = await response.text()
                    raise LokiError(
                        f"Loki query_range failed with HTTP {response.status}: {body[:200]}"
                    )
                payload = await response.json()
        except aiohttp.ClientError as exc:
            raise LokiError(f"Loki query_range request failed: {exc}") from exc

        entries = parse_query_range_response(payload)
        return entries, len(entries) >= limit

    async def query_range(self, start_ns, end_ns):
        """Fetch a complete half-open history interval [start_ns, end_ns).

        Saturated intervals are recursively subdivided. If one nanosecond still
        contains at least max_page_limit entries, completeness cannot be proven
        with query_range and the operation fails explicitly.
        """

        if end_ns <= start_ns:
            return []

        collected = {}
        stack = [(start_ns, end_ns, self.page_limit)]

        while stack:
            interval_start, interval_end, limit = stack.pop()
            entries, saturated = await self._query_range_once(
                interval_start, interval_end, limit
            )
            for entry in entries:
                collected[entry.stable_id] = entry

            if not saturated:
                continue

            span = interval_end - interval_start
            if span > 1:
                midpoint = interval_start + span // 2
                stack.append((midpoint, interval_end, self.page_limit))
                stack.append((interval_start, midpoint, self.page_limit))
                continue

            if limit < self.max_page_limit:
                next_limit = min(limit * 2, self.max_page_limit)
                stack.append((interval_start, interval_end, next_limit))
                continue

            raise LokiHistoryIncompleteError(
                "Loki history interval is saturated at the maximum limit"
            )

        return sorted(
            collected.values(),
            key=lambda entry: (entry.timestamp_ns, entry.stable_id),
        )

    async def tail(self, *, connected_event=None):
        """Yield parsed batches from Loki /tail until the WebSocket closes.

        If connected_event is provided, it is set immediately after the
        WebSocket handshake succeeds and before any frame is consumed. This
        lets callers establish the history/tail overlap boundary without
        waiting for the first log entry.
        """

        session = self._require_session()
        url = _tail_url(self.base_url)

        try:
            async with session.ws_connect(
                url,
                params={"query": self.query},
                auth=self._auth,
            ) as websocket:
                if connected_event is not None:
                    connected_event.set()
                async for message in websocket:
                    if message.type == aiohttp.WSMsgType.TEXT:
                        try:
                            payload = json.loads(message.data)
                        except json.JSONDecodeError as exc:
                            raise LokiProtocolError(
                                "Loki tail frame is not valid JSON"
                            ) from exc
                        yield parse_tail_response(payload)
                    elif message.type == aiohttp.WSMsgType.ERROR:
                        raise LokiError("Loki tail WebSocket reported an error")
                    elif message.type in (
                        aiohttp.WSMsgType.CLOSE,
                        aiohttp.WSMsgType.CLOSED,
                    ):
                        break
        except aiohttp.ClientError as exc:
            raise LokiError(f"Loki tail connection failed: {exc}") from exc


class LokiSync:
    """History-window and catch-up state for one Loki-backed event source."""

    def __init__(self, store: OperationalEventStore, *, overlap_seconds=5):
        if overlap_seconds < 0:
            raise ValueError("overlap_seconds must not be negative")
        self.store = store
        self.overlap_ns = int(overlap_seconds * 1_000_000_000)
        self.history_covered_through_ns: Optional[int] = None

    @property
    def history_window_ns(self):
        return int(self.store.history_seconds * 1_000_000_000)

    def startup_range(self, boundary_ns):
        return (
            boundary_ns - self.history_window_ns,
            boundary_ns + 1,
        )

    def catchup_range(self, boundary_ns):
        visible_start = boundary_ns - self.history_window_ns
        if self.history_covered_through_ns is None:
            start_ns = visible_start
        else:
            start_ns = max(
                visible_start,
                self.history_covered_through_ns - self.overlap_ns,
            )
        return start_ns, boundary_ns + 1

    def mark_history_covered(self, boundary_ns):
        if (
            self.history_covered_through_ns is None
            or boundary_ns > self.history_covered_through_ns
        ):
            self.history_covered_through_ns = boundary_ns

    def merge_entries(self, entries, *, boundary_ns):
        events = []
        for entry in entries:
            event = operational_event_from_loki(entry)
            if event is not None:
                events.append(event)

        added = self.store.merge(events)
        self.store.prune_before(boundary_ns - self.history_window_ns)
        return added

    async def sync_history(self, client: LokiClient, boundary_ns, *, initial=False):
        start_ns, end_ns = (
            self.startup_range(boundary_ns)
            if initial
            else self.catchup_range(boundary_ns)
        )
        entries = await client.query_range(start_ns, end_ns)
        added = self.merge_entries(entries, boundary_ns=boundary_ns)
        self.mark_history_covered(boundary_ns)
        return added

    def merge_tail_batch(self, batch: TailBatch, *, boundary_ns):
        """Merge one live batch and report whether a catch-up is required."""

        added = self.merge_entries(batch.entries, boundary_ns=boundary_ns)
        catchup_required = bool(batch.dropped_entries)
        return added, catchup_required
