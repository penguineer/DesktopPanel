import io
import logging

from logging_setup import configure_console_logging


class TestConfigureConsoleLogging:
    @staticmethod
    def _logger(stderr_stream):
        logger = logging.Logger("desktop-panel-test", level=logging.DEBUG)
        logger.propagate = False
        configure_console_logging(
            logger=logger,
            stdout_stream=io.StringIO(),
            stderr_stream=stderr_stream,
        )
        return logger

    def test_routes_below_error_to_stdout_and_errors_to_stderr(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        logger = logging.Logger("desktop-panel-test", level=logging.DEBUG)
        logger.propagate = False

        configure_console_logging(
            logger=logger,
            stdout_stream=stdout,
            stderr_stream=stderr,
        )

        logger.info("information")
        logger.warning("warning")
        logger.error("error")
        logger.critical("critical")

        assert "information" in stdout.getvalue()
        assert "warning" in stdout.getvalue()
        assert "error" not in stdout.getvalue()
        assert "critical" not in stdout.getvalue()
        assert "error" in stderr.getvalue()
        assert "critical" in stderr.getvalue()

    def test_preserves_direct_stderr_passthrough(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        logger = logging.Logger("desktop-panel-test", level=logging.DEBUG)
        logger.propagate = False

        configure_console_logging(
            logger=logger,
            stdout_stream=stdout,
            stderr_stream=stderr,
        )
        logger.warning("stderr: direct diagnostic")

        assert stdout.getvalue() == ""
        assert stderr.getvalue().splitlines() == [" direct diagnostic"]

    def test_configuration_is_idempotent(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        logger = logging.Logger("desktop-panel-test", level=logging.DEBUG)
        logger.propagate = False

        configure_console_logging(
            logger=logger,
            stdout_stream=stdout,
            stderr_stream=stderr,
        )
        configure_console_logging(
            logger=logger,
            stdout_stream=stdout,
            stderr_stream=stderr,
        )
        logger.info("once-info")
        logger.error("once-error")

        assert stdout.getvalue().count("once-info") == 1
        assert stderr.getvalue().count("once-error") == 1

    def test_propagating_logger_installs_handlers_on_root(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        root = logging.Logger("desktop-panel-root", level=logging.DEBUG)
        logger = logging.Logger("desktop-panel-child", level=logging.DEBUG)
        logger.parent = root
        logger.propagate = True

        original_root = logging.root
        try:
            logging.root = root
            configure_console_logging(
                logger=logger,
                stdout_stream=stdout,
                stderr_stream=stderr,
            )
            logger.info("root-info")
            logger.error("root-error")
        finally:
            logging.root = original_root

        assert "root-info" in stdout.getvalue()
        assert "root-error" not in stdout.getvalue()
        assert "root-error" in stderr.getvalue()
