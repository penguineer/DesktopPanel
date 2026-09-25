""" Pytest tests for the operational event controller module """

import operational_event_controller
from operational_event_controller import OperationalEventController


class _FakeSource:
    instances = []

    def __init__(
        self,
        client_factory,
        store,
        on_new_events=None,
        on_failure=None,
        recovery_after_ns=None,
    ):
        self.client_factory = client_factory
        self.store = store
        self.on_new_events = on_new_events
        self.on_failure = on_failure
        self.recovery_after_ns = recovery_after_ns
        self.history_covered_through_ns = recovery_after_ns
        self.started = False
        self.torn_down = False
        self.__class__.instances.append(self)

    def start(self):
        self.started = True

    def teardown(self):
        self.torn_down = True





class _FakeJarvisSource:
    instances = []

    def __init__(
        self,
        client_factory,
        store,
        on_new_events=None,
        on_failure=None,
        has_previous_state=False,
    ):
        self.client_factory = client_factory
        self.store = store
        self.on_new_events = on_new_events
        self.on_failure = on_failure
        self.has_previous_state = has_previous_state
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
        _FakeJarvisSource.instances = []

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

    def test_restarted_source_receives_previous_coverage_boundary(self, monkeypatch):
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
        assert first.recovery_after_ns is None

        first.history_covered_through_ns = 123456789
        controller.update_config({
            "history_duration": "PT48H",
            "loki": {
                "url": "https://loki.example",
                "user": "desktop-panel",
                "password": "first",
            },
        })

        assert _FakeSource.instances[1].recovery_after_ns == 123456789

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

    def test_repeated_invalid_duration_never_starts_sources(self, monkeypatch):
        monkeypatch.setattr(operational_event_controller, "LokiEventSource", _FakeSource)
        monkeypatch.setattr(
            operational_event_controller,
            "JarvisEventSource",
            _FakeJarvisSource,
        )
        controller = OperationalEventController()
        config = {
            "history_duration": "24h",
            "loki": {
                "url": "https://loki.example",
                "user": "desktop-panel",
                "password": "secret",
            },
            "jarvis": {
                "url": "https://jarvis.example",
            },
        }

        controller.update_config(config)
        controller.update_config(config)

        assert _FakeSource.instances == []
        assert _FakeJarvisSource.instances == []

    def test_valid_config_restarts_after_invalid_duration(self, monkeypatch):
        monkeypatch.setattr(operational_event_controller, "LokiEventSource", _FakeSource)
        monkeypatch.setattr(
            operational_event_controller,
            "JarvisEventSource",
            _FakeJarvisSource,
        )
        controller = OperationalEventController()
        valid = {
            "history_duration": "PT24H",
            "loki": {
                "url": "https://loki.example",
                "user": "desktop-panel",
                "password": "secret",
            },
            "jarvis": {
                "url": "https://jarvis.example",
            },
        }

        controller.update_config(valid)
        first_loki = _FakeSource.instances[-1]
        first_jarvis = _FakeJarvisSource.instances[-1]

        controller.update_config({
            **valid,
            "history_duration": "24h",
        })

        assert first_loki.torn_down is True
        assert first_jarvis.torn_down is True

        controller.update_config(valid)

        assert len(_FakeSource.instances) == 2
        assert len(_FakeJarvisSource.instances) == 2
        assert _FakeSource.instances[-1].started is True
        assert _FakeJarvisSource.instances[-1].started is True

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

    def test_loki_only_config_keeps_jarvis_optional(self, monkeypatch):
        monkeypatch.setattr(operational_event_controller, "LokiEventSource", _FakeSource)
        monkeypatch.setattr(
            operational_event_controller,
            "JarvisEventSource",
            _FakeJarvisSource,
        )
        controller = OperationalEventController()

        controller.update_config({
            "loki": {
                "url": "https://loki.example",
                "user": "desktop-panel",
                "password": "secret",
            },
        })

        assert len(_FakeSource.instances) == 1
        assert _FakeJarvisSource.instances == []

    def test_complete_jarvis_config_starts_independent_source(self, monkeypatch):
        monkeypatch.setattr(operational_event_controller, "LokiEventSource", _FakeSource)
        monkeypatch.setattr(
            operational_event_controller,
            "JarvisEventSource",
            _FakeJarvisSource,
        )
        controller = OperationalEventController()

        controller.update_config({
            "loki": {
                "url": "https://loki.example",
                "user": "desktop-panel",
                "password": "secret",
            },
            "jarvis": {
                "url": "https://jarvis.example",
            },
        })

        assert len(_FakeSource.instances) == 1
        assert len(_FakeJarvisSource.instances) == 1
        assert _FakeJarvisSource.instances[0].started is True
        assert _FakeJarvisSource.instances[0].store is controller.jarvis_store

    def test_jarvis_change_does_not_restart_loki(self, monkeypatch):
        monkeypatch.setattr(operational_event_controller, "LokiEventSource", _FakeSource)
        monkeypatch.setattr(
            operational_event_controller,
            "JarvisEventSource",
            _FakeJarvisSource,
        )
        controller = OperationalEventController()
        base = {
            "loki": {
                "url": "https://loki.example",
                "user": "desktop-panel",
                "password": "secret",
            },
            "jarvis": {
                "url": "https://jarvis-first.example",
            },
        }

        controller.update_config(base)
        loki = _FakeSource.instances[0]
        jarvis = _FakeJarvisSource.instances[0]

        controller.update_config({
            **base,
            "jarvis": {"url": "https://jarvis-second.example"},
        })

        assert len(_FakeSource.instances) == 1
        assert loki.torn_down is False
        assert jarvis.torn_down is True
        assert len(_FakeJarvisSource.instances) == 2
        assert _FakeJarvisSource.instances[1].has_previous_state is False

    def test_incomplete_jarvis_config_creates_only_jarvis_source_error(self, monkeypatch):
        monkeypatch.setattr(operational_event_controller, "LokiEventSource", _FakeSource)
        monkeypatch.setattr(
            operational_event_controller,
            "JarvisEventSource",
            _FakeJarvisSource,
        )
        controller = OperationalEventController()

        controller.update_config({
            "loki": {
                "url": "https://loki.example",
                "user": "desktop-panel",
                "password": "secret",
            },
            "jarvis": {"url": ""},
        })

        assert len(_FakeSource.instances) == 1
        assert _FakeJarvisSource.instances == []
        assert len(controller.jarvis_store.events) == 1
        assert controller.jarvis_store.events[0].state == "configuration-error"

