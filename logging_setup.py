"""Configure Kivy console logging for container stdout/stderr semantics."""

import logging
import os
import sys

# Kivy's default console handler writes all severities to stderr. Disable that
# handler before importing Kivy so even framework startup messages cannot be
# misclassified by Docker as errors. File logging and LoggerHistory stay active.
os.environ.setdefault("KIVY_NO_CONSOLELOG", "1")

_ORIGINAL_STDERR = sys.stderr

import kivy.logger as _kivy_logger
from kivy.logger import Logger


def _is_stderr_record(record):
    """Return whether Kivy created this record from a direct stderr write."""
    try:
        parts = record.msg.split(':', 1)
    except (AttributeError, TypeError):
        return False
    return len(parts) == 2 and parts[0] == "stderr"


class _BelowErrorFilter(logging.Filter):
    """Allow non-stderr records below ERROR severity."""

    def filter(self, record):
        return record.levelno < logging.ERROR and not _is_stderr_record(record)


class _ErrorOrStderrFilter(logging.Filter):
    """Allow ERROR+ records and direct stderr writes."""

    def filter(self, record):
        return record.levelno >= logging.ERROR or _is_stderr_record(record)


class _StderrHandler(logging.StreamHandler):
    """Preserve Kivy's unformatted passthrough for direct stderr writes."""

    def emit(self, record):
        if _is_stderr_record(record):
            try:
                self.stream.write(record.msg.split(':', 1)[1] + '\n')
                self.flush()
            except Exception:
                self.handleError(record)
            return
        super().emit(record)


def _formatter():
    """Create a Kivy-style formatter compatible with Kivy 2.1 and newer."""
    fmt = "[%(levelname)-7s] %(message)s"
    if hasattr(_kivy_logger, "KivyFormatter"):
        return _kivy_logger.KivyFormatter(fmt, use_color=False)
    if hasattr(_kivy_logger, "ColoredFormatter"):
        return _kivy_logger.ColoredFormatter(fmt, use_color=False)
    return logging.Formatter(fmt)


def _console_logger(logger):
    """Return the logger that owns Kivy's console policy for this Kivy mode."""
    # Kivy 2.1 makes Logger the root logger. Newer Kivy in its default KIVY
    # mode installs handlers on the root logger and lets Logger propagate.
    if logger.propagate and logging.root is not logger:
        return logging.root
    return logger


def configure_console_logging(logger=Logger, stdout_stream=None,
                              stderr_stream=None):
    """Route Kivy logs below ERROR to stdout and errors to stderr.

    Kivy's built-in console handler is disabled before import. This function
    installs the DesktopPanel stream policy while leaving Kivy's history and
    file handlers untouched. Direct writes captured through ``sys.stderr`` are
    passed through unformatted to the process' original stderr stream.
    """
    target = _console_logger(logger)
    if any(getattr(handler, "_desktop_panel_stream_split", False)
           for handler in target.handlers):
        return

    if stdout_stream is None:
        stdout_stream = sys.stdout
    if stderr_stream is None:
        stderr_stream = _ORIGINAL_STDERR

    formatter = _formatter()

    stdout_handler = logging.StreamHandler(stdout_stream)
    stdout_handler.setFormatter(formatter)
    stdout_handler.addFilter(_BelowErrorFilter())
    stdout_handler._desktop_panel_stream_split = True

    stderr_handler = _StderrHandler(stderr_stream)
    stderr_handler.setFormatter(formatter)
    stderr_handler.addFilter(_ErrorOrStderrFilter())
    stderr_handler._desktop_panel_stream_split = True

    target.addHandler(stdout_handler)
    target.addHandler(stderr_handler)
