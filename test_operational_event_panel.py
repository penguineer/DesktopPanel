""" Pytest tests for the operational event panel helpers """

from operational_event_panel import _entry_height


class TestOperationalEventPanelLayout:
    def test_expanded_row_is_taller_than_collapsed_row(self):
        collapsed = _entry_height("A warning message")
        expanded = _entry_height(
            "A warning message",
            '{"host": "host-a", "severity": "warning"}',
            True,
        )

        assert expanded > collapsed

    def test_multiline_details_increase_expanded_height(self):
        short = _entry_height("message", "one", True)
        multiline = _entry_height("message", "one\ntwo\nthree", True)

        assert multiline > short
