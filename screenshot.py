""" Module for application screenshots: window captures and widget thumbnails """

from datetime import datetime

from kivy import Logger
from kivy.core.window import Window
from kivy.graphics.texture import Texture


def screenshot_window(name=None):
    """Take a screenshot of the entire application window and save to a file.

    :param name: Optional file name.  When ``None`` a timestamped default is
        used (``Screenshot <datetime>.png``).
    :returns: The file path written by Kivy, or ``None`` on failure.
    """
    if name is None:
        name = "Screenshot {}.png".format(datetime.now())
    Logger.info("Screenshot: Taking a screenshot to %s", name)
    return Window.screenshot(name=name)


class ScaleStrategy:
    """Abstract base class for widget thumbnail scaling strategies.

    Subclasses implement :meth:`capture` to produce a
    :class:`~kivy.graphics.texture.Texture` from a widget using different
    approaches (e.g. fit-to-box, foreground crop, …).
    """

    def capture(self, widget, max_width, max_height):
        """Capture *widget* and return a thumbnail texture, or ``None``.

        :param widget: A Kivy widget that is attached to the widget tree and
            has non-zero size.
        :param max_width: Hint: maximum thumbnail width in pixels.
        :param max_height: Hint: maximum thumbnail height in pixels.
        :returns: A :class:`~kivy.graphics.texture.Texture`, or ``None`` on
            failure or when the widget has zero dimensions.
        """
        raise NotImplementedError


class AspectFitStrategy(ScaleStrategy):
    """Scales the full widget content to fit within *max_width* × *max_height*.

    The widget's aspect ratio is preserved.  The returned texture exactly fits
    the requested bounding box on one axis, and may be smaller on the other.
    """

    def capture(self, widget, max_width, max_height):
        if widget is None or widget.width <= 0 or widget.height <= 0:
            return None
        try:
            aspect = widget.width / widget.height
            if aspect > max_width / max_height:
                scale = max_width / widget.width
            else:
                scale = max_height / widget.height
            return widget.export_as_image(scale=scale).texture
        except Exception as e:
            Logger.warning("Screenshot: AspectFitStrategy: %s", e)
            return None


class ForegroundCropStrategy(ScaleStrategy):
    """Crops to the bounding box of non-background content before returning.

    Captures the widget at an intermediate resolution, scans the raw pixel data
    to find the tightest bounding box of pixels above a brightness threshold,
    and returns a texture of only that cropped region.  When the cropped
    texture is rendered into the fill-meter slot by OpenGL, the foreground
    colours fill the slot rather than being lost in a large black background —
    helping users recognise each page by its distinct foreground colours.

    Falls back to :class:`AspectFitStrategy` when no foreground content is
    found (i.e. the widget is entirely black).
    """

    _SCAN_WIDTH = 160
    """Intermediate capture width used for bounding-box pixel analysis."""

    _THRESHOLD = 20
    """Minimum channel value (0–255) for a pixel to be considered foreground."""

    def capture(self, widget, max_width, max_height):
        if widget is None or widget.width <= 0 or widget.height <= 0:
            return None
        try:
            scale = self._SCAN_WIDTH / widget.width
            tex = widget.export_as_image(scale=scale).texture
            w, h = tex.width, tex.height
            data = tex.pixels          # RGBA bytes
            threshold = self._THRESHOLD

            min_x, max_x = w, 0
            min_y, max_y = h, 0
            found = False
            for py in range(h):
                for px in range(w):
                    off = (py * w + px) * 4
                    if (data[off] > threshold
                            or data[off + 1] > threshold
                            or data[off + 2] > threshold):
                        if px < min_x:
                            min_x = px
                        if px > max_x:
                            max_x = px
                        if py < min_y:
                            min_y = py
                        if py > max_y:
                            max_y = py
                        found = True

            if not found:
                return AspectFitStrategy().capture(widget, max_width, max_height)

            crop_w = max_x - min_x + 1
            crop_h = max_y - min_y + 1
            cropped = bytearray(crop_w * crop_h * 4)
            for cy in range(crop_h):
                src_off = ((min_y + cy) * w + min_x) * 4
                dst_off = cy * crop_w * 4
                cropped[dst_off:dst_off + crop_w * 4] = data[src_off:src_off + crop_w * 4]

            crop_tex = Texture.create(size=(crop_w, crop_h), colorfmt='rgba')
            crop_tex.blit_buffer(bytes(cropped), colorfmt='rgba', bufferfmt='ubyte')
            return crop_tex
        except Exception as e:
            Logger.warning("Screenshot: ForegroundCropStrategy: %s", e)
            return None


def capture_widget_texture(widget, max_width, max_height, strategy=None):
    """Capture a widget's rendered content as a thumbnail texture.

    The widget must be attached to the widget tree and have non-zero size.

    :param widget: The Kivy widget to capture.
    :param max_width: Hint: maximum thumbnail width in pixels.
    :param max_height: Hint: maximum thumbnail height in pixels.
    :param strategy: A :class:`ScaleStrategy` instance that controls how the
        thumbnail is produced.  Defaults to :class:`AspectFitStrategy`.
    :returns: A :class:`~kivy.graphics.texture.Texture`, or ``None`` if
        capture failed or the widget has zero dimensions.
    """
    if strategy is None:
        strategy = AspectFitStrategy()
    return strategy.capture(widget, max_width, max_height)
