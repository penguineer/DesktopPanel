""" Pytest tests for the scrollable_list module """

import pytest

from scrollable_list import _compute_scroll_indicators


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

    def test_overflow_near_top_threshold(self):
        # Just below the 0.999 threshold → above arrow visible
        above, below = _compute_scroll_indicators(
            content_height=400, view_height=200, scroll_y=0.998
        )
        assert above
        assert below

    def test_overflow_at_exact_top_threshold(self):
        # At exactly 0.999 → above arrow not visible (>=0.999 means "at top")
        above, below = _compute_scroll_indicators(
            content_height=400, view_height=200, scroll_y=0.999
        )
        assert not above
        assert below

    def test_overflow_near_bottom_threshold(self):
        # Just above the 0.001 threshold → below arrow visible
        above, below = _compute_scroll_indicators(
            content_height=400, view_height=200, scroll_y=0.002
        )
        assert above
        assert below

    def test_overflow_at_exact_bottom_threshold(self):
        # At exactly 0.001 → below arrow not visible (<=0.001 means "at bottom")
        above, below = _compute_scroll_indicators(
            content_height=400, view_height=200, scroll_y=0.001
        )
        assert above
        assert not below

    def test_zero_content_height(self):
        above, below = _compute_scroll_indicators(
            content_height=0, view_height=200, scroll_y=1.0
        )
        assert not above
        assert not below

    def test_zero_view_height_with_content(self):
        # View height zero with content → overflow is True
        above, below = _compute_scroll_indicators(
            content_height=100, view_height=0, scroll_y=0.5
        )
        assert above
        assert below
