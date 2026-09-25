""" Pytest tests for the operational event controller module """

import operational_event_controller
from operational_event_controller import OperationalEventController


class _FakeSource:
    instances = []

    def __init__(self, client_factory, store, on_new_events=None, on_failure=None):
        self.client_factory = client_factory
        self.store = store
        self.on_new_events = on_new_events
        self.on_failure = on_failure
        self.started = False
        self.torn_down = False
        self.__class__.instances.append(self)

    def start(self):
        self.started = True

    def teardown(self):
        self.torn_down = True


class TestOperationalEventController:
    def setup_method(self):
        _FakeSource.instances = []

    def test_missing_config_keeps_source_disabled(self, monkeypatch):
        monkeypatch.setattr(operational_event_controller, "LokiEventSource", _FakeSource)
        controller = OperationalEventController()

        controller.update_config(None)

        assert _FakeSource.instances == []
        assert controller.store.events == []

    def test_complete_config_starts_source(self, monkeypatch):
        monkeypatch.setattr(operational_event_controller, "LokiEventSource", _FakeSource)
        controller = OperationalEventController()

        controller.update_config({
            "history_duration": "PT1H",
            "loki": {
                "url": "https://loki.example",
                "user": "desktop-panel",
                "password": "secret",
            },
        })

        assert controller.store.history_seconds == 3600
        assert len(_FakeSource.instances) == 1
        assert _FakeSource.instances[0].started is True

    def test_unchanged_config_does_not_restart_source(self, monkeypatch):
        monkeypatch.setattr(operational_event_controller, "LokiEventSource", _FakeSource)
        controller = OperationalEventController()
        config = {
            "loki": {
                "url": "https://loki.example",
                "user": "desktop-panel",
                "password": "secret",
            },
        }

        controller.update_config(config)
        controller.update_config(dict(config))

        assert len(_FakeSource.instances) == 1
        assert _FakeSource.instances[0].torn_down is False

    def test_changed_config_restarts_source(self, monkeypatch):
        monkeypatch.setattr(operational_event_controller, "LokiEventSource", _FakeSource)
        controller = OperationalEventController()

        controller.update_config({
            "loki": {
                "url": "https://loki.example",
                "user": "desktop-panel",
                "password": "first",
            },
        })
        first = _FakeSource.instances[0]

        controller.update_config({
            "loki": {
                "url": "https://loki.example",
                "user": "desktop-panel",
                "password": "second",
            },
        })

        assert first.torn_down is True
        assert len(_FakeSource.instances) == 2
        assert _FakeSource.instances[1].started is True

    def test_incomplete_loki_config_creates_source_error(self, monkeypatch):
        monkeypatch.setattr(operational_event_controller, "LokiEventSource", _FakeSource)
        failures = []
        controller = OperationalEventController(
            on_failure=lambda state, message: failures.append((state, message))
        )

        controller.update_config({
            "loki": {
                "url": "https://loki.example",
                "user": "desktop-panel",
            },
        })

        assert len(controller.store.events) == 1
        assert controller.store.events[0].state == "configuration-error"
        assert len(failures) == 1

    def test_invalid_duration_creates_source_error(self, monkeypatch):
        monkeypatch.setattr(operational_event_controller, "LokiEventSource", _FakeSource)
        controller = OperationalEventController()

        controller.update_config({
            "history_duration": "24h",
            "loki": {
                "url": "https://loki.example",
                "user": "desktop-panel",
                "password": "secret",
            },
        })

        assert len(controller.store.events) == 1
        assert controller.store.events[0].state == "configuration-error"
        assert _FakeSource.instances == []

    def test_teardown_stops_source(self, monkeypatch):
        monkeypatch.setattr(operational_event_controller, "LokiEventSource", _FakeSource)
        controller = OperationalEventController()
        controller.update_config({
            "loki": {
                "url": "https://loki.example",
                "user": "desktop-panel",
                "password": "secret",
            },
        })

        source = _FakeSource.instances[0]
        controller.teardown()

        assert source.torn_down is True
