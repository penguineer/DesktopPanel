""" Pytest tests for reloadable JSON observation. """

from types import SimpleNamespace

from watchdog.events import FileCreatedEvent, FileModifiedEvent, FileMovedEvent

import reloadable_json as reloadable_json_module
from reloadable_json import JsonObserver


class _FakePollingObserver:
    def __init__(self):
        self.scheduled = None
        self.started = False

    def schedule(self, handler, path, recursive=False):
        self.scheduled = (handler, path, recursive)

    def start(self):
        self.started = True

    def is_alive(self):
        return False


class TestJsonObserver:
    def test_setup_uses_polling_observer_and_watches_parent_directory(
            self, monkeypatch, tmp_path):
        configuration = tmp_path / "configuration"
        configuration.mkdir()
        json_path = configuration / "test.json"
        json_path.write_text("{}")
        fake_observer = _FakePollingObserver()

        monkeypatch.setattr(
            reloadable_json_module,
            "PollingObserver",
            lambda: fake_observer,
        )

        observer = JsonObserver(str(json_path), lambda _data: None)
        observer.setup()

        assert fake_observer.started is True
        assert fake_observer.scheduled == (
            observer,
            str(configuration.resolve()),
            False,
        )

    def test_modified_target_reloads_json(self, tmp_path):
        json_path = tmp_path / "test.json"
        json_path.write_text('{"value": 1}')
        updates = []
        observer = JsonObserver(str(json_path), updates.append)

        observer.on_modified(FileModifiedEvent(str(json_path)))

        assert updates == [{"value": 1}]

    def test_unrelated_file_is_ignored(self, tmp_path):
        json_path = tmp_path / "test.json"
        json_path.write_text('{"value": 1}')
        unrelated_path = tmp_path / "other.json"
        unrelated_path.write_text('{"value": 2}')
        updates = []
        observer = JsonObserver(str(json_path), updates.append)

        observer.on_modified(FileModifiedEvent(str(unrelated_path)))

        assert updates == []

    def test_created_target_reloads_json(self, tmp_path):
        json_path = tmp_path / "test.json"
        json_path.write_text('{"value": 1}')
        updates = []
        observer = JsonObserver(str(json_path), updates.append)

        observer.on_created(FileCreatedEvent(str(json_path)))

        assert updates == [{"value": 1}]

    def test_moved_target_reloads_json(self, tmp_path):
        json_path = tmp_path / "test.json"
        json_path.write_text('{"value": 1}')
        temporary_path = tmp_path / "test.json.tmp"
        updates = []
        observer = JsonObserver(str(json_path), updates.append)

        observer.on_moved(FileMovedEvent(str(temporary_path), str(json_path)))

        assert updates == [{"value": 1}]
