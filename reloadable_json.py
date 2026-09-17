""" Module for reloadable JSON files """

import json
import os
from typing import Callable, Optional

from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver

from kivy import Logger


class JsonObserver(FileSystemEventHandler):
    def __init__(self,
                 json_path: str,
                 update_callback: Callable[[json], None],
                 failed_callback: Optional[Callable[[bool], None]] = None):
        if not json_path:
            raise ValueError("JSON file path must be provided!")

        self._json_path = os.path.abspath(json_path)
        self._watch_path = os.path.dirname(self._json_path)

        if not update_callback:
            raise ValueError("Update callback must be provided!")
        self._update_callback = update_callback

        self._failed_callback = failed_callback

        self._observer = None

    def setup(self):
        self._observer = PollingObserver()
        self._observer.schedule(self,
                                self._watch_path,
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

    def _reload_if_target(self, event_path: str):
        if os.path.abspath(event_path) != self._json_path:
            return

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

    def on_modified(self, event):
        self._reload_if_target(event.src_path)

    def on_created(self, event):
        self._reload_if_target(event.src_path)

    def on_moved(self, event):
        self._reload_if_target(event.dest_path)
