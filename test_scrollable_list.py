""" Pytest tests for the scrollable_list module """

import pytest

from scrollable_list import _compute_scroll_indicators, _SCROLL_ARROW_THRESHOLD_PX


class TestComputeScrollIndicators:
    def test_no_overflow_no_arrows(self):
        above, below = _compute_scroll_indicators(
            content_height=100, view_height=200, scroll_y=1.0
        )
        assert not above
        assert not below

    def test_exact_fit_no_arrows(self):
        above, below = _compute_scroll_indicators(
            content_height=200, view_height=200, scroll_y=1.0
        )
        assert not above
        assert not below

    def test_overflow_at_top_only_below_arrow(self):
        # scroll_y = 1.0 → at top → content hidden below only
        above, below = _compute_scroll_indicators(
            content_height=400, view_height=200, scroll_y=1.0
        )
        assert not above
        assert below

    def test_overflow_at_bottom_only_above_arrow(self):
        # scroll_y = 0.0 → at bottom → content hidden above only
        above, below = _compute_scroll_indicators(
            content_height=400, view_height=200, scroll_y=0.0
        )
        assert above
        assert not below

    def test_overflow_in_middle_both_arrows(self):
        above, below = _compute_scroll_indicators(
            content_height=600, view_height=200, scroll_y=0.5
        )
        assert above
        assert below

    def test_small_hidden_above_suppresses_arrow(self):
        # overflow = 400 - 200 = 200 px
        # hidden_above = (1 - 0.95) * 200 = 10 px ≤ threshold → no above arrow
        above, below = _compute_scroll_indicators(
            content_height=400, view_height=200, scroll_y=0.95
        )
        assert not above
        # hidden_below = 0.95 * 200 = 190 px > threshold → below arrow shown
        assert below

    def test_small_hidden_below_suppresses_arrow(self):
        # overflow = 400 - 200 = 200 px
        # hidden_below = 0.05 * 200 = 10 px ≤ threshold → no below arrow
        above, below = _compute_scroll_indicators(
            content_height=400, view_height=200, scroll_y=0.05
        )
        # hidden_above = (1 - 0.05) * 200 = 190 px > threshold → above arrow shown
        assert above
        assert not below

    def test_hidden_at_exact_threshold_suppresses_arrow(self):
        # hidden_above == threshold exactly → NOT shown (condition is strictly >)
        # threshold = 20 px, overflow = 200 → scroll_y = 1 - 20/200 = 0.9
        above, below = _compute_scroll_indicators(
            content_height=400, view_height=200, scroll_y=0.9
        )
        assert not above
        assert below

    def test_hidden_just_above_threshold_shows_arrow(self):
        # hidden_above slightly > threshold → arrow shown
        # Use overflow=200 and hide 21 px above: scroll_y = 1 - 21/200 = 0.895
        above, below = _compute_scroll_indicators(
            content_height=400, view_height=200, scroll_y=0.895
        )
        assert above
        assert below

    def test_zero_content_height(self):
        above, below = _compute_scroll_indicators(
            content_height=0, view_height=200, scroll_y=1.0
        )
        assert not above
        assert not below

    def test_zero_view_height_with_content(self):
        # View height zero with content → overflow is positive
        above, below = _compute_scroll_indicators(
            content_height=100, view_height=0, scroll_y=0.5
        )
        assert above
        assert below
