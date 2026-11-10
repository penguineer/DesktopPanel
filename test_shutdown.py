"""Tests for the signal-driven application shutdown helper."""

import signal

import pytest

from shutdown import install_shutdown_handlers


class FakeLoop:
    def __init__(self, supports_signals=True):
        self.supports_signals = supports_signals
        self.handlers = {}
        self.removed = []
        self.scheduled = []

    def add_signal_handler(self, signum, callback, *args):
        if not self.supports_signals:
            raise NotImplementedError
        self.handlers[signum] = (callback, args)

    def remove_signal_handler(self, signum):
        self.removed.append(signum)
        self.handlers.pop(signum, None)

    def call_soon_threadsafe(self, callback, *args):
        self.scheduled.append((callback, args))


@pytest.fixture
def fake_signal_api(monkeypatch):
    originals = {
        signal.SIGINT: object(),
        signal.SIGTERM: object(),
    }
    installed = dict(originals)
    monkeypatch.setattr(signal, "getsignal", originals.__getitem__)
    monkeypatch.setattr(
        signal, "signal", lambda signum, handler: installed.__setitem__(signum, handler)
    )
    return originals, installed


def test_sigterm_requests_shutdown_once_and_restores_handlers(fake_signal_api):
    originals, installed = fake_signal_api
    loop = FakeLoop()
    requests = []
    restore = install_shutdown_handlers(loop, requests.append)

    callback, args = loop.handlers[signal.SIGTERM]
    callback(*args)
    callback, args = loop.handlers[signal.SIGINT]
    callback(*args)

    assert requests == [signal.SIGTERM]
    restore()
    assert loop.removed == [signal.SIGINT, signal.SIGTERM]
    assert installed == originals


def test_windows_fallback_schedules_shutdown_on_the_event_loop(fake_signal_api):
    originals, installed = fake_signal_api
    loop = FakeLoop(supports_signals=False)
    requests = []
    restore = install_shutdown_handlers(loop, requests.append)

    installed[signal.SIGINT](signal.SIGINT, None)
    installed[signal.SIGTERM](signal.SIGTERM, None)
    assert requests == []
    for callback, args in loop.scheduled:
        callback(*args)

    assert requests == [signal.SIGINT]
    restore()
    assert installed == originals
