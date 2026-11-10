"""Coordinated signal handling for the Kivy/asyncio application lifecycle."""

import signal


def install_shutdown_handlers(loop, request_stop):
    """Request shutdown once on SIGINT or SIGTERM, returning a restore callback.

    The native asyncio signal API is used on Unix. On Windows, where that API
    is unavailable, a standard signal handler forwards the request to the loop.
    """
    previous_handlers = {}
    loop_handlers = []
    stopping = False

    def handle_signal(signum):
        nonlocal stopping
        if stopping:
            return
        stopping = True
        request_stop(signum)

    def restore():
        for signum in loop_handlers:
            loop.remove_signal_handler(signum)
        for signum, previous in previous_handlers.items():
            signal.signal(signum, previous)

    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[signum] = signal.getsignal(signum)
            try:
                loop.add_signal_handler(signum, handle_signal, signum)
                loop_handlers.append(signum)
            except NotImplementedError:
                signal.signal(
                    signum,
                    lambda received, _frame: loop.call_soon_threadsafe(
                        handle_signal, received
                    ),
                )
    except Exception:
        restore()
        raise

    return restore
