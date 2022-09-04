""" Module for reloadable JSON files """

import json
from typing import Callable, Optional

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from kivy import Logger


class JsonObserver(FileSystemEventHandler):
    def __init__(self,
                 json_path: str,
                 update_callback: Callable[[json], None],
                 failed_callback: Optional[Callable[[bool], None]] = None):
        if not json_path:
            raise ValueError("JSON file path must be provided!")

        self._json_path = json_path

        if not update_callback:
            raise ValueError("Update callback must be provided!")
        self._update_callback = update_callback

        self._failed_callback = failed_callback

        self._observer = None

    def setup(self):
        self._observer = Observer()
        self._observer.schedule(self,
                                self._json_path,
                                recursive=False)
        try:
            self._observer.start()
        except FileNotFoundError as e:
            self._observer = None
            raise e

    def teardown(self):
        if self._observer is not None and self._observer.is_alive():
            self._observer.stop()
            self._observer.join()

    def on_modified(self, _event):
        try:
            with open(self._json_path, "r") as f:
                self._update_callback(json.load(f))
                if self._failed_callback is not None:
                    self._failed_callback(False)
        except FileNotFoundError as e:
            Logger.warning("Issues: %s", e)
        except json.decoder.JSONDecodeError as e:
            if self._failed_callback is not None:
                self._failed_callback(True)
            Logger.warning("Issues: %s", e)
