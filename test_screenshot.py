""" Pytest tests for the screenshot module """

import pytest
from screenshot import (
    ScaleStrategy,
    AspectFitStrategy,
    ForegroundCropStrategy,
    capture_widget_texture,
)


class _MockWidget:
    """Minimal stand-in for a Kivy widget."""

    def __init__(self, width=0, height=0):
        self.width = width
        self.height = height


class TestScaleStrategy:
    def test_capture_raises_not_implemented(self):
        s = ScaleStrategy()
        with pytest.raises(NotImplementedError):
            s.capture(None, 100, 100)


class TestAspectFitStrategy:
    def test_none_widget_returns_none(self):
        assert AspectFitStrategy().capture(None, 100, 100) is None

    def test_zero_width_returns_none(self):
        assert AspectFitStrategy().capture(_MockWidget(width=0, height=100), 100, 100) is None

    def test_zero_height_returns_none(self):
        assert AspectFitStrategy().capture(_MockWidget(width=100, height=0), 100, 100) is None


class TestForegroundCropStrategy:
    def test_none_widget_returns_none(self):
        assert ForegroundCropStrategy().capture(None, 100, 100) is None

    def test_zero_width_returns_none(self):
        assert ForegroundCropStrategy().capture(_MockWidget(width=0, height=100), 100, 100) is None

    def test_zero_height_returns_none(self):
        assert ForegroundCropStrategy().capture(_MockWidget(width=100, height=0), 100, 100) is None


class TestCaptureWidgetTexture:
    def test_none_widget_returns_none(self):
        assert capture_widget_texture(None, 100, 100) is None

    def test_zero_width_returns_none(self):
        assert capture_widget_texture(_MockWidget(width=0, height=100), 100, 100) is None

    def test_zero_height_returns_none(self):
        assert capture_widget_texture(_MockWidget(width=100, height=0), 100, 100) is None

    def test_default_strategy_is_aspect_fit(self):
        """capture_widget_texture with None strategy falls back to AspectFitStrategy."""
        # Verify by passing a zero-size widget — AspectFitStrategy returns None
        result = capture_widget_texture(_MockWidget(width=0, height=0), 100, 100)
        assert result is None

    def test_explicit_strategy_used(self):
        """capture_widget_texture passes through to the provided strategy."""

        class _NullStrategy(ScaleStrategy):
            def capture(self, _widget, _max_w, _max_h):
                return "sentinel"

        result = capture_widget_texture(_MockWidget(width=100, height=100), 100, 100,
                                        strategy=_NullStrategy())
        assert result == "sentinel"
