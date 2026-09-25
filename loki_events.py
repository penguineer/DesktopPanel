"""Async Loki transport and history/tail synchronization helpers."""

import asyncio
from dataclasses import dataclass
import json
import time
from typing import Iterable, Optional
from urllib.parse import urlsplit, urlunsplit

import aiohttp
from kivy import Logger

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
        max_history_entries=20000,
        session=None,
    ):
        if page_limit <= 0 or max_page_limit < page_limit:
            raise ValueError("Invalid Loki history limits")
        if max_history_entries <= 0:
            raise ValueError("max_history_entries must be greater than zero")

        self.base_url = base_url.rstrip("/")
        self.query = query
        self.page_limit = page_limit
        self.max_page_limit = max_page_limit
        self.max_history_entries = max_history_entries
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
            if len(collected) > self.max_history_entries:
                raise LokiHistoryIncompleteError(
                    "Loki history exceeds the defensive in-memory entry limit"
                )

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



class LokiEventSource:
    """Long-running tail-first Loki source with reconnect and catch-up."""

    def __init__(
        self,
        client_factory,
        store: OperationalEventStore,
        *,
        on_new_events=None,
        on_failure=None,
        recovery_after_ns=None,
        overlap_seconds=5,
        reconnect_initial_seconds=1,
        reconnect_max_seconds=30,
        time_ns=time.time_ns,
        sleep=asyncio.sleep,
    ):
        if reconnect_initial_seconds <= 0:
            raise ValueError("reconnect_initial_seconds must be greater than zero")
        if reconnect_max_seconds < reconnect_initial_seconds:
            raise ValueError("reconnect_max_seconds must not be smaller than initial")

        self.client_factory = client_factory
        self.store = store
        self.sync = LokiSync(store, overlap_seconds=overlap_seconds)
        self.on_new_events = on_new_events
        self.on_failure = on_failure
        self.recovery_after_ns = recovery_after_ns
        self.reconnect_initial_seconds = reconnect_initial_seconds
        self.reconnect_max_seconds = reconnect_max_seconds
        self._time_ns = time_ns
        self._sleep = sleep
        self._task = None
        self._failure_active = False
        self._started_once = False
        self._session_became_healthy = False

    @property
    def running(self):
        return self._task is not None and not self._task.done()

    @property
    def history_covered_through_ns(self):
        return self.sync.history_covered_through_ns

    def start(self):
        """Start the source on the current asyncio event loop."""

        if self.running:
            return self._task
        self._task = asyncio.create_task(self.run())
        return self._task

    def teardown(self):
        """Cancel the source task without requiring an async Kivy on_stop."""

        if self._task is not None and not self._task.done():
            self._task.cancel()

    async def wait_stopped(self):
        """Wait for a started source to finish cancellation."""

        if self._task is None:
            return
        try:
            await self._task
        except asyncio.CancelledError:
            pass

    def _set_degraded(self, state, message):
        timestamp_ns = self._time_ns()
        self.store.set_source_state(
            "loki",
            state,
            message,
            timestamp_ns=timestamp_ns,
        )
        if not self._failure_active:
            self._failure_active = True
            if self.on_failure is not None:
                self.on_failure(state, message)

    def _set_healthy(self):
        self.store.clear_source_state("loki")
        self._failure_active = False
        self._session_became_healthy = True

    def _notify_events(self, events):
        if events and self.on_new_events is not None:
            self.on_new_events(events)

    async def _pump_tail(self, client, queue, connected):
        try:
            async for batch in client.tail(connected_event=connected):
                await queue.put(batch)
        finally:
            await queue.put(None)

    async def _wait_for_connection(self, connected, tail_task):
        connected_wait = asyncio.create_task(connected.wait())
        try:
            done, _pending = await asyncio.wait(
                (connected_wait, tail_task),
                return_when=asyncio.FIRST_COMPLETED,
            )
            if connected_wait in done and connected.is_set():
                return
            await tail_task
            raise LokiError("Loki tail closed before the WebSocket connected")
        finally:
            if not connected_wait.done():
                connected_wait.cancel()

    async def _catch_up(
        self,
        client,
        boundary_ns,
        *,
        initial,
        notify=True,
        notify_after_ns=None,
    ):
        if not initial:
            self._set_degraded("catching-up", "Loki event source is catching up")

        added = await self.sync.sync_history(
            client,
            boundary_ns,
            initial=initial,
        )
        if notify:
            if notify_after_ns is not None:
                added = [
                    event
                    for event in added
                    if event.timestamp_ns > notify_after_ns
                ]
            self._notify_events(added)

    async def _drain_buffered_tail(self, queue, *, notify):
        while True:
            try:
                batch = queue.get_nowait()
            except asyncio.QueueEmpty:
                return True

            if batch is None:
                return False

            boundary_ns = self._time_ns()
            added, catchup_required = self.sync.merge_tail_batch(
                batch,
                boundary_ns=boundary_ns,
            )
            if notify:
                self._notify_events(added)
            if catchup_required:
                return "catchup"

    async def _recover_dropped_entries(self, client, queue):
        """Catch up until buffered tail data no longer reports another drop."""

        while True:
            catchup_boundary = self._time_ns()
            try:
                await self._catch_up(
                    client,
                    catchup_boundary,
                    initial=False,
                    notify=True,
                )
            except Exception:
                self._set_degraded(
                    "history-failed",
                    "Loki event catch-up failed",
                )
                raise

            buffered_result = await self._drain_buffered_tail(
                queue,
                notify=True,
            )
            if buffered_result is False:
                raise LokiError("Loki tail connection closed")
            if buffered_result != "catchup":
                return

    async def _connected_session(self, client, *, initial):
        queue = asyncio.Queue()
        connected = asyncio.Event()
        tail_task = asyncio.create_task(self._pump_tail(client, queue, connected))

        try:
            await self._wait_for_connection(connected, tail_task)
            boundary_ns = self._time_ns()

            recovery_after_ns = self.recovery_after_ns if initial else None
            notify_initial = initial and recovery_after_ns is not None

            try:
                await self._catch_up(
                    client,
                    boundary_ns,
                    initial=initial,
                    notify=(not initial or notify_initial),
                    notify_after_ns=recovery_after_ns,
                )
            except Exception:
                self._set_degraded(
                    "history-failed",
                    "Loki event history synchronization failed",
                )
                raise

            drain_result = await self._drain_buffered_tail(
                queue,
                notify=(not initial or notify_initial),
            )
            if drain_result is False:
                raise LokiError("Loki tail connection closed")
            if drain_result == "catchup":
                await self._recover_dropped_entries(client, queue)

            self._set_healthy()
            self._started_once = True

            while True:
                batch = await queue.get()
                if batch is None:
                    raise LokiError("Loki tail connection closed")

                batch_boundary = self._time_ns()
                added, catchup_required = self.sync.merge_tail_batch(
                    batch,
                    boundary_ns=batch_boundary,
                )
                self._notify_events(added)

                if catchup_required:
                    await self._recover_dropped_entries(client, queue)
                    self._set_healthy()
        finally:
            tail_task.cancel()
            try:
                await tail_task
            except (asyncio.CancelledError, Exception):
                pass

    async def run(self):
        """Run until cancelled, reconnecting after transport/history failures."""

        delay = self.reconnect_initial_seconds

        while True:
            self._session_became_healthy = False
            try:
                async with self.client_factory() as client:
                    await self._connected_session(
                        client,
                        initial=not self._started_once,
                    )
            except asyncio.CancelledError:
                raise
            except LokiError as exc:
                Logger.warning("OperationalEvents: Loki source failure: %s", exc)
                self._set_degraded(
                    "disconnected",
                    "Loki event source is disconnected",
                )
            except Exception as exc:
                Logger.exception(
                    "OperationalEvents: unexpected Loki source failure: %s",
                    exc,
                )
                self._set_degraded(
                    "disconnected",
                    "Loki event source is disconnected",
                )

            if self._session_became_healthy:
                delay = self.reconnect_initial_seconds

            await self._sleep(delay)
            delay = min(delay * 2, self.reconnect_max_seconds)
