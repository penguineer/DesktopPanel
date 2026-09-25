"""Async Jarvis transport and alert occurrence reconciliation."""

import asyncio
import json
import time
from collections import defaultdict
from typing import Optional
from urllib.parse import quote, urlsplit, urlunsplit

import aiohttp
import dateutil.parser
from kivy import Logger

from operational_events import (
    JarvisAlertEvent,
    JarvisEventStore,
    OperationalEventCapacityError,
    jarvis_occurrence_id,
)


class JarvisError(RuntimeError):
    """Base class for Jarvis transport/reconciliation failures."""


class JarvisProtocolError(JarvisError):
    """Raised when Jarvis returns an unexpected response shape."""


class JarvisBudgetError(JarvisError):
    """Raised when a defensive Jarvis reconciliation budget is exhausted."""


class _HistoryBudget:
    def __init__(self, *, max_rows, max_pages):
        self.remaining_rows = max_rows
        self.remaining_pages = max_pages

    def consume_page(self, row_count):
        if self.remaining_pages <= 0:
            raise JarvisBudgetError(
                "Jarvis reconciliation exceeds the defensive history page limit"
            )
        self.remaining_pages -= 1

        if row_count > self.remaining_rows:
            raise JarvisBudgetError(
                "Jarvis reconciliation exceeds the defensive history row limit"
            )
        self.remaining_rows -= row_count


def _iso_to_ns(value):
    if not isinstance(value, str) or not value:
        raise JarvisProtocolError("Jarvis timestamp is missing")
    try:
        dt = dateutil.parser.isoparse(value)
    except (TypeError, ValueError) as exc:
        raise JarvisProtocolError("Jarvis timestamp is invalid") from exc
    return int(dt.timestamp() * 1_000_000_000)


def _ws_url(base_url):
    parts = urlsplit(base_url)
    if parts.scheme == "https":
        scheme = "wss"
    elif parts.scheme == "http":
        scheme = "ws"
    else:
        raise ValueError(f"Unsupported Jarvis URL scheme: {parts.scheme!r}")
    return urlunsplit((scheme, parts.netloc, parts.path.rstrip("/") + "/ws", "", ""))


def _logical_key(alert):
    fingerprint = alert.get("fingerprint")
    cluster_name = alert.get("clusterName")
    if not isinstance(fingerprint, str) or not fingerprint:
        raise JarvisProtocolError("Jarvis alert is missing fingerprint")
    if not isinstance(cluster_name, str) or not cluster_name:
        raise JarvisProtocolError("Jarvis alert is missing clusterName")
    return cluster_name, fingerprint


def _state(alert):
    status = alert.get("status")
    if not isinstance(status, dict):
        raise JarvisProtocolError("Jarvis alert is missing status")
    state = status.get("state")
    if not isinstance(state, str) or not state:
        raise JarvisProtocolError("Jarvis alert status is missing state")
    return state


def _annotations(value):
    if value is None:
        return {}
    if isinstance(value, dict):
        return {str(key): str(item) for key, item in value.items()}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise JarvisProtocolError("Jarvis history annotations are invalid JSON") from exc
        if isinstance(parsed, dict):
            return {str(key): str(item) for key, item in parsed.items()}
    raise JarvisProtocolError("Jarvis annotations have an unexpected shape")


def _labels(alert):
    labels = alert.get("labels") or {}
    if not isinstance(labels, dict):
        raise JarvisProtocolError("Jarvis alert labels have an unexpected shape")
    return {str(key): str(value) for key, value in labels.items()}


def _summary(labels, annotations):
    return (
        annotations.get("summary")
        or labels.get("alertname")
        or "Jarvis alert"
    )


def _source_annotation(labels, cluster_name):
    return (
        labels.get("host")
        or labels.get("instance")
        or labels.get("node")
        or cluster_name
    )


class JarvisClient:
    """Small asyncio client for the Jarvis 1.12 HTTP and WebSocket APIs."""

    def __init__(
        self,
        base_url,
        *,
        history_page_size=100,
        max_history_events=20000,
        max_response_bytes=2 * 1024 * 1024,
        session=None,
    ):
        if history_page_size <= 0 or history_page_size > 100:
            raise ValueError("history_page_size must be between 1 and 100")
        if max_history_events <= 0:
            raise ValueError("max_history_events must be greater than zero")
        if max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be greater than zero")
        self.base_url = base_url.rstrip("/")
        self.history_page_size = history_page_size
        self.max_history_events = max_history_events
        self.max_response_bytes = max_response_bytes
        self._session = session
        self._owns_session = session is None

    async def __aenter__(self):
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, _exc_type, _exc, _tb):
        await self.close()

    async def close(self):
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    def _require_session(self):
        if self._session is None:
            raise RuntimeError("JarvisClient must be entered before use")
        return self._session

    async def _read_bounded_body(self, response):
        content_length = response.content_length
        if (
            content_length is not None
            and content_length > self.max_response_bytes
        ):
            raise JarvisBudgetError(
                "Jarvis response exceeds the defensive response-size limit"
            )

        chunks = []
        size = 0
        async for chunk in response.content.iter_chunked(64 * 1024):
            size += len(chunk)
            if size > self.max_response_bytes:
                raise JarvisBudgetError(
                    "Jarvis response exceeds the defensive response-size limit"
                )
            chunks.append(chunk)
        return b"".join(chunks)

    async def _get_json(self, path, *, params=None):
        session = self._require_session()
        try:
            async with session.get(self.base_url + path, params=params) as response:
                body = await self._read_bounded_body(response)
                if response.status != 200:
                    text = body[:200].decode("utf-8", errors="replace")
                    raise JarvisError(
                        f"Jarvis request failed with HTTP {response.status}: {text}"
                    )
                try:
                    payload = json.loads(body)
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise JarvisProtocolError(
                        "Jarvis response is not valid JSON"
                    ) from exc
        except aiohttp.ClientError as exc:
            raise JarvisError(f"Jarvis request failed: {exc}") from exc
        return payload

    async def get_alerts(self, *, state=None):
        params = {"state": state} if state is not None else None
        payload = await self._get_json("/api/v1/alerts", params=params)
        if not isinstance(payload, list):
            raise JarvisProtocolError("Jarvis alerts response is not a list")
        return payload

    async def get_history(
        self,
        fingerprint,
        cluster_name,
        *,
        cutoff_ns,
        budget=None,
    ):
        """Fetch newest history pages until the visible cutoff has been crossed."""

        offset = 0
        events = []
        quoted_fingerprint = quote(fingerprint, safe="")
        while True:
            payload = await self._get_json(
                f"/api/v1/alerts/{quoted_fingerprint}/history",
                params={
                    "cluster": cluster_name,
                    "limit": str(self.history_page_size),
                    "offset": str(offset),
                },
            )
            if not isinstance(payload, dict):
                raise JarvisProtocolError("Jarvis history response is not an object")
            page = payload.get("events")
            total = payload.get("total")
            if not isinstance(page, list) or not isinstance(total, int):
                raise JarvisProtocolError("Jarvis history response is missing events/total")

            if budget is not None:
                budget.consume_page(len(page))

            events.extend(page)
            if len(events) > self.max_history_events:
                raise JarvisBudgetError(
                    "Jarvis history exceeds the defensive per-alert event limit"
                )

            if not page or offset + len(page) >= total:
                break

            recorded = []
            for event in page:
                if not isinstance(event, dict):
                    raise JarvisProtocolError("Jarvis history event is not an object")
                recorded.append(_iso_to_ns(event.get("recordedAt")))
            if recorded and min(recorded) < cutoff_ns:
                break

            offset += len(page)

        return events

    async def changes(self):
        """Yield invalidation notifications from Jarvis /ws.

        Payload contents are intentionally ignored. HTTP reconciliation remains
        authoritative.
        """

        session = self._require_session()
        try:
            async with session.ws_connect(_ws_url(self.base_url)) as websocket:
                async for message in websocket:
                    if message.type == aiohttp.WSMsgType.TEXT:
                        try:
                            payload = json.loads(message.data)
                        except json.JSONDecodeError as exc:
                            raise JarvisProtocolError(
                                "Jarvis WebSocket frame is not valid JSON"
                            ) from exc
                        if isinstance(payload, dict):
                            yield payload
                    elif message.type == aiohttp.WSMsgType.ERROR:
                        raise JarvisError("Jarvis WebSocket reported an error")
                    elif message.type in (
                        aiohttp.WSMsgType.CLOSE,
                        aiohttp.WSMsgType.CLOSED,
                    ):
                        break
        except aiohttp.ClientError as exc:
            raise JarvisError(f"Jarvis WebSocket connection failed: {exc}") from exc


class JarvisSync:
    """Build an authoritative visible occurrence snapshot from Jarvis."""

    def __init__(
        self,
        store: JarvisEventStore,
        *,
        max_logical_alerts=1000,
        max_history_rows=20000,
        max_history_pages=200,
    ):
        if max_logical_alerts <= 0:
            raise ValueError("max_logical_alerts must be greater than zero")
        if max_history_rows <= 0:
            raise ValueError("max_history_rows must be greater than zero")
        if max_history_pages <= 0:
            raise ValueError("max_history_pages must be greater than zero")
        self.store = store
        self.max_logical_alerts = max_logical_alerts
        self.max_history_rows = max_history_rows
        self.max_history_pages = max_history_pages

    @property
    def history_window_ns(self):
        return int(self.store.history_seconds * 1_000_000_000)

    async def snapshot(self, client: JarvisClient, boundary_ns):
        cutoff_ns = boundary_ns - self.history_window_ns

        current = await client.get_alerts()
        resolved = await client.get_alerts(state="resolved")

        current_by_key = {}
        for alert in current:
            if not isinstance(alert, dict):
                raise JarvisProtocolError("Jarvis alert is not an object")
            state = _state(alert)
            if state != "resolved":
                current_by_key[_logical_key(alert)] = alert

        resolved_by_key = {}
        for alert in resolved:
            if not isinstance(alert, dict):
                raise JarvisProtocolError("Jarvis resolved alert is not an object")
            if _state(alert) != "resolved":
                continue
            ends_at = alert.get("endsAt")
            if ends_at is not None and _iso_to_ns(ends_at) >= cutoff_ns:
                resolved_by_key[_logical_key(alert)] = alert

        keys = set(current_by_key) | set(resolved_by_key)
        logical_limit = min(self.store.max_events, self.max_logical_alerts)
        if len(keys) > logical_limit:
            raise JarvisBudgetError(
                "Jarvis logical alert set exceeds the defensive reconciliation limit"
            )

        history_budget = _HistoryBudget(
            max_rows=self.max_history_rows,
            max_pages=self.max_history_pages,
        )
        visible = {}
        for key in sorted(keys):
            cluster_name, fingerprint = key
            base_alert = current_by_key.get(key) or resolved_by_key[key]
            history = await client.get_history(
                fingerprint,
                cluster_name,
                cutoff_ns=cutoff_ns,
                budget=history_budget,
            )
            for event in self._events_for_key(
                key,
                base_alert,
                current_by_key.get(key),
                history,
                cutoff_ns,
            ):
                visible[event.event_id] = event
                if len(visible) > self.store.max_events:
                    raise OperationalEventCapacityError(
                        "Jarvis occurrence set exceeds the defensive in-memory entry limit"
                    )

        return sorted(
            visible.values(),
            key=lambda event: (event.starts_at_ns, event.event_id),
        )

    def _events_for_key(self, key, base_alert, current_alert, history, cutoff_ns):
        cluster_name, fingerprint = key
        labels = _labels(base_alert)
        severity = labels.get("severity", "").lower()

        grouped = defaultdict(list)
        for row in history:
            if not isinstance(row, dict):
                raise JarvisProtocolError("Jarvis history event is not an object")
            if row.get("fingerprint") != fingerprint or row.get("clusterName") != cluster_name:
                raise JarvisProtocolError("Jarvis history event identity does not match request")
            starts_at = row.get("startsAt")
            starts_at_ns = _iso_to_ns(starts_at)
            grouped[starts_at_ns].append(row)

        current_start_ns = None
        if current_alert is not None:
            current_start_ns = _iso_to_ns(current_alert.get("startsAt"))

        result = []
        for starts_at_ns, rows in grouped.items():
            rows = sorted(rows, key=lambda row: _iso_to_ns(row.get("recordedAt")))
            starts_at = rows[0].get("startsAt")
            resolved_rows = [row for row in rows if row.get("status") == "resolved"]

            if resolved_rows:
                resolved_row = resolved_rows[-1]
                resolved_index = rows.index(resolved_row)
                prior_status = (
                    rows[resolved_index - 1].get("status")
                    if resolved_index > 0
                    else None
                )
                if prior_status == "suppressed":
                    continue

                resolved_at = resolved_row.get("recordedAt")
                resolved_ns = _iso_to_ns(resolved_at)
                if resolved_ns < cutoff_ns:
                    continue
                annotations = _annotations(resolved_row.get("annotations"))
                result.append(self._event(
                    cluster_name,
                    fingerprint,
                    starts_at,
                    starts_at_ns,
                    resolved_at,
                    resolved_ns,
                    "resolved",
                    labels,
                    annotations,
                    severity,
                ))
                continue

            if current_alert is not None and starts_at_ns == current_start_ns:
                state = _state(current_alert)
                if state == "suppressed":
                    continue
                annotations = _annotations(current_alert.get("annotations"))
                result.append(self._event(
                    cluster_name,
                    fingerprint,
                    starts_at,
                    starts_at_ns,
                    None,
                    starts_at_ns,
                    state,
                    labels,
                    annotations,
                    severity,
                ))

        if current_alert is not None and current_start_ns not in grouped:
            state = _state(current_alert)
            if state != "suppressed":
                starts_at = current_alert.get("startsAt")
                annotations = _annotations(current_alert.get("annotations"))
                result.append(self._event(
                    cluster_name,
                    fingerprint,
                    starts_at,
                    current_start_ns,
                    None,
                    current_start_ns,
                    state,
                    labels,
                    annotations,
                    severity,
                ))

        return result

    @staticmethod
    def _event(
        cluster_name,
        fingerprint,
        starts_at,
        starts_at_ns,
        resolved_at,
        timestamp_ns,
        status,
        labels,
        annotations,
        severity,
    ):
        return JarvisAlertEvent(
            event_id=jarvis_occurrence_id(cluster_name, fingerprint, starts_at_ns),
            timestamp_ns=timestamp_ns,
            source="jarvis",
            source_annotation=_source_annotation(labels, cluster_name),
            summary=_summary(labels, annotations),
            cluster_name=cluster_name,
            fingerprint=fingerprint,
            starts_at=starts_at,
            starts_at_ns=starts_at_ns,
            resolved_at=resolved_at,
            status=status,
            severity=severity,
            labels=dict(labels),
            annotations=dict(annotations),
            stale=False,
        )


class JarvisEventSource:
    """Jarvis source using HTTP reconciliation with WebSocket invalidations."""

    def __init__(
        self,
        client_factory,
        store: JarvisEventStore,
        *,
        on_new_events=None,
        on_failure=None,
        poll_seconds=300,
        disconnected_poll_seconds=30,
        reconnect_seconds=5,
        has_previous_state=False,
        time_ns=time.time_ns,
        sleep=asyncio.sleep,
    ):
        self.client_factory = client_factory
        self.store = store
        self.sync = JarvisSync(store)
        self.on_new_events = on_new_events
        self.on_failure = on_failure
        self.poll_seconds = poll_seconds
        self.disconnected_poll_seconds = disconnected_poll_seconds
        self.reconnect_seconds = reconnect_seconds
        self._time_ns = time_ns
        self._sleep = sleep
        self._task = None
        self._failure_active = False
        self._has_success = bool(has_previous_state)

    @property
    def running(self):
        return self._task is not None and not self._task.done()

    def start(self):
        if self.running:
            return self._task
        self._task = asyncio.create_task(self.run())
        return self._task

    def teardown(self):
        if self._task is not None and not self._task.done():
            self._task.cancel()

    async def wait_stopped(self):
        if self._task is None:
            return
        try:
            await self._task
        except asyncio.CancelledError:
            pass

    def _set_degraded(self, state, message):
        if self._has_success:
            self.store.mark_stale()
        is_new = self.store.set_source_state(
            "jarvis",
            state,
            message,
            timestamp_ns=self._time_ns(),
        )
        if is_new and not self._failure_active:
            self._failure_active = True
            if self.on_failure is not None:
                self.on_failure(state, message)

    def _set_healthy(self):
        self.store.clear_source_state("jarvis")
        self._failure_active = False

    async def _reconcile(self, client):
        snapshot = await self.sync.snapshot(client, self._time_ns())
        changed = self.store.reconcile(snapshot)
        bootstrap = not self._has_success
        self._has_success = True
        self._set_healthy()
        if changed and not bootstrap and self.on_new_events is not None:
            self.on_new_events(changed)

    async def _watch_changes(self, client, invalidated):
        while True:
            try:
                async for _payload in client.changes():
                    invalidated.set()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                Logger.warning("OperationalEvents: Jarvis WebSocket failure: %s", exc)
            await self._sleep(self.reconnect_seconds)

    async def run(self):
        while True:
            try:
                async with self.client_factory() as client:
                    invalidated = asyncio.Event()
                    watcher = asyncio.create_task(self._watch_changes(client, invalidated))
                    try:
                        while True:
                            invalidated.clear()
                            try:
                                await self._reconcile(client)
                            except asyncio.CancelledError:
                                raise
                            except Exception as exc:
                                Logger.warning(
                                    "OperationalEvents: Jarvis reconciliation failure: %s",
                                    exc,
                                )
                                self._set_degraded(
                                    "unreachable",
                                    "Jarvis alert state is unavailable; showing stale data",
                                )

                            timeout = (
                                self.poll_seconds
                                if not self._failure_active
                                else self.disconnected_poll_seconds
                            )
                            try:
                                await asyncio.wait_for(invalidated.wait(), timeout=timeout)
                            except asyncio.TimeoutError:
                                pass
                    finally:
                        watcher.cancel()
                        try:
                            await watcher
                        except (asyncio.CancelledError, Exception):
                            pass
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                Logger.warning("OperationalEvents: Jarvis source failure: %s", exc)
                self._set_degraded(
                    "unreachable",
                    "Jarvis alert state is unavailable; showing stale data",
                )
                await self._sleep(self.disconnected_poll_seconds)
