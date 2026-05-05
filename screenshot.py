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


class SalientScaleStrategy(ScaleStrategy):
    """Downscales while preserving spatial layout and highlighting salient colours.

    Captures the widget at its **full native resolution** so no detail is
    discarded before analysis.  The output is produced by max-luminance pooling:
    the source image is partitioned into rectangular blocks (one per output
    pixel) and each output pixel is assigned the colour of the *brightest*
    input pixel inside its block.

    As a result:

    * The full bounding rectangle is kept intact — element positions are not
      shifted.
    * Foreground colour landmarks (bright UI elements) survive the downscale
      because the bright pixel in each block always wins over dark background
      pixels in the same block.
    * The thumbnail reads as a colour-distribution map of the original page,
      making pages visually recognisable even at the tiny fill-meter slot size.

    Luminance is approximated as ``max(R, G, B)`` — the maximum channel value.
    This is faster than perceptual weights and equally effective for the purpose
    of selecting the brightest pixel in each block.
    """

    def capture(self, widget, max_width, max_height):
        if widget is None or widget.width <= 0 or widget.height <= 0:
            return None
        try:
            # Capture at full native widget resolution — no pre-scaling loss.
            src_tex = widget.export_as_image(scale=1).texture
            src_w, src_h = src_tex.width, src_tex.height
            if src_w <= 0 or src_h <= 0:
                return None
            data = src_tex.pixels  # RGBA bytes

            # Output size: fit within bounding box preserving aspect ratio.
            if src_w * max_height > src_h * max_width:
                out_w = int(max_width)
                out_h = max(1, int(out_w * src_h / src_w))
            else:
                out_h = int(max_height)
                out_w = max(1, int(out_h * src_w / src_h))

            # Max-luminance pooling: each output pixel = brightest source pixel
            # in the corresponding input block.
            # block_w / block_h are floats: fractional block sizes are handled by
            # the int() truncation in the inner loop boundary calculations.
            block_w = src_w / out_w
            block_h = src_h / out_h

            out_data = bytearray(out_w * out_h * 4)
            for oy in range(out_h):
                sy0 = int(oy * block_h)
                sy1 = max(sy0 + 1, min(int((oy + 1) * block_h), src_h))
                for ox in range(out_w):
                    sx0 = int(ox * block_w)
                    sx1 = max(sx0 + 1, min(int((ox + 1) * block_w), src_w))
                    best_lum = None
                    br = bg = bb = ba = 0
                    for sy in range(sy0, sy1):
                        row_base = sy * src_w * 4
                        for sx in range(sx0, sx1):
                            off = row_base + sx * 4
                            r = data[off]
                            g = data[off + 1]
                            b = data[off + 2]
                            a = data[off + 3]
                            lum = max(r, g, b)
                            if best_lum is None or lum > best_lum:
                                best_lum = lum
                                br, bg, bb, ba = r, g, b, a
                    dst_off = (oy * out_w + ox) * 4
                    out_data[dst_off] = br
                    out_data[dst_off + 1] = bg
                    out_data[dst_off + 2] = bb
                    out_data[dst_off + 3] = ba

            out_tex = Texture.create(size=(out_w, out_h), colorfmt='rgba')
            out_tex.blit_buffer(bytes(out_data), colorfmt='rgba', bufferfmt='ubyte')
            return out_tex
        except Exception as e:
            Logger.warning("Screenshot: SalientScaleStrategy: %s", e)
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
