"""Configuration and lifecycle controller for operational events."""

import time

from kivy import Logger

from jarvis_events import JarvisClient, JarvisEventSource
from loki_events import LokiClient, LokiEventSource
from operational_events import JarvisEventStore, OperationalEventStore
from timewidget import parse_iso8601_duration


class OperationalEventController(object):
    """Own the independent Loki and Jarvis stores and configured sources."""

    def __init__(self, on_new_events=None, on_failure=None):
        self.loki_store = OperationalEventStore()
        self.jarvis_store = JarvisEventStore()
        # Compatibility for Phase 2 callers while the UI moves to explicit stores.
        self.store = self.loki_store
        self._on_new_events = on_new_events
        self._on_failure = on_failure
        self._loki_source = None
        self._jarvis_source = None
        self._loki_config_key = None
        self._jarvis_config_key = None
        self._history_duration = None
        self._history_covered_through_ns = None

    def update_config(self, config):
        """Apply a system.operational_events configuration dictionary."""

        config = config or {}
        history_duration = config.get("history_duration", "PT24H")
        loki = config.get("loki") or {}
        jarvis = config.get("jarvis") or {}

        if history_duration != self._history_duration:
            try:
                seconds = parse_iso8601_duration(history_duration)
                if seconds <= 0:
                    raise ValueError(
                        "Operational event history duration must be greater than zero"
                    )
            except ValueError as exc:
                self._configuration_error(
                    self.loki_store,
                    "loki",
                    "Invalid operational event history duration",
                    exc,
                )
                if jarvis:
                    self._configuration_error(
                        self.jarvis_store,
                        "jarvis",
                        "Invalid operational event history duration",
                        exc,
                    )
                self._stop_loki()
                self._stop_jarvis()
                self._loki_config_key = None
                self._jarvis_config_key = None
                return

            self.loki_store.history_duration = history_duration
            self.jarvis_store.history_duration = history_duration
            self._history_duration = history_duration

        self._update_loki(config, loki, history_duration)
        self._update_jarvis(config, jarvis, history_duration)

    def _update_loki(self, config, loki, history_duration):
        url = loki.get("url")
        user = loki.get("user")
        password = loki.get("password")
        config_key = (bool(config), history_duration, url, user, password)
        if config_key == self._loki_config_key:
            return

        self._stop_loki()
        self._loki_config_key = config_key

        if not config:
            self.loki_store.clear_source_state("loki")
            return

        if not url or not user or not password:
            self._configuration_error(
                self.loki_store,
                "loki",
                "Loki operational event configuration is incomplete",
            )
            return

        def client_factory():
            return LokiClient(url, user, password)

        self._loki_source = LokiEventSource(
            client_factory,
            self.loki_store,
            on_new_events=self._on_new_events,
            on_failure=self._on_failure,
            recovery_after_ns=self._history_covered_through_ns,
        )
        self._loki_source.start()

    def _update_jarvis(self, config, jarvis, history_duration):
        url = jarvis.get("url")
        config_key = (bool(config), history_duration, url)
        if config_key == self._jarvis_config_key:
            return

        had_previous_state = self.jarvis_store.has_alerts
        self._stop_jarvis()
        self._jarvis_config_key = config_key

        # Jarvis is optional for installations that only configure Loki.
        if not config or not jarvis:
            self.jarvis_store.clear_source_state("jarvis")
            return

        if not url:
            self._configuration_error(
                self.jarvis_store,
                "jarvis",
                "Jarvis operational event configuration is incomplete",
            )
            return

        def client_factory():
            return JarvisClient(url)

        self._jarvis_source = JarvisEventSource(
            client_factory,
            self.jarvis_store,
            on_new_events=self._on_new_events,
            on_failure=self._on_failure,
            has_previous_state=had_previous_state,
        )
        self._jarvis_source.start()

    def _configuration_error(self, store, source, message, exc=None):
        if exc is None:
            Logger.error("OperationalEvents: %s", message)
        else:
            Logger.error("OperationalEvents: %s: %s", message, exc)

        is_new = store.set_source_state(
            source,
            "configuration-error",
            message,
            timestamp_ns=time.time_ns(),
        )
        if is_new and self._on_failure is not None:
            self._on_failure("configuration-error", message)

    def _stop_loki(self):
        if self._loki_source is None:
            return
        coverage = getattr(
            self._loki_source,
            "history_covered_through_ns",
            None,
        )
        if coverage is not None:
            self._history_covered_through_ns = coverage
        self._loki_source.teardown()
        self._loki_source = None

    def _stop_jarvis(self):
        if self._jarvis_source is None:
            return
        self._jarvis_source.teardown()
        self._jarvis_source = None

    def teardown(self):
        self._stop_loki()
        self._stop_jarvis()
