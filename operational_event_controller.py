"""Configuration and lifecycle controller for operational events."""

import time

from kivy import Logger

from loki_events import LokiClient, LokiEventSource
from operational_events import OperationalEventStore


class OperationalEventController(object):
    """Own the operational event store and configured Loki source."""

    def __init__(self, on_new_events=None, on_failure=None):
        self.store = OperationalEventStore()
        self._on_new_events = on_new_events
        self._on_failure = on_failure
        self._source = None
        self._config_key = None

    def update_config(self, config):
        """Apply a system.operational_events configuration dictionary."""

        config = config or {}
        history_duration = config.get("history_duration", "PT24H")
        loki = config.get("loki") or {}

        url = loki.get("url")
        user = loki.get("user")
        password = loki.get("password")

        config_key = (history_duration, url, user, password)
        if config_key == self._config_key:
            return

        self.teardown()
        self._config_key = config_key

        try:
            self.store.history_duration = history_duration
        except ValueError as exc:
            self._configuration_error(
                "Invalid operational event history duration",
                exc,
            )
            return

        if not config:
            self.store.clear_source_state("loki")
            return

        if not url or not user or not password:
            self._configuration_error(
                "Loki operational event configuration is incomplete"
            )
            return

        def client_factory():
            return LokiClient(url, user, password)

        self._source = LokiEventSource(
            client_factory,
            self.store,
            on_new_events=self._on_new_events,
            on_failure=self._on_failure,
        )
        self._source.start()

    def _configuration_error(self, message, exc=None):
        if exc is None:
            Logger.error("OperationalEvents: %s", message)
        else:
            Logger.error("OperationalEvents: %s: %s", message, exc)

        is_new = self.store.set_source_state(
            "loki",
            "configuration-error",
            message,
            timestamp_ns=time.time_ns(),
        )
        if is_new and self._on_failure is not None:
            self._on_failure("configuration-error", message)

    def teardown(self):
        if self._source is not None:
            self._source.teardown()
            self._source = None
