""" Module for capturing widget content as scaled-down textures """

from kivy import Logger


def capture_widget_texture(widget, max_width, max_height):
    """Capture a widget's rendered content as a small thumbnail texture.

    The widget must be attached to the widget tree and have non-zero size.
    The returned texture preserves the widget's aspect ratio and fits within
    the *max_width* × *max_height* bounding box.

    :param widget: The Kivy widget to capture.
    :param max_width: Maximum width of the thumbnail in pixels.
    :param max_height: Maximum height of the thumbnail in pixels.
    :returns: A :class:`~kivy.graphics.texture.Texture`, or ``None`` if
        capture failed or the widget has zero dimensions.
    """
    if widget is None or widget.width <= 0 or widget.height <= 0:
        return None

    try:
        aspect = widget.width / widget.height
        if aspect > max_width / max_height:
            scale = max_width / widget.width
        else:
            scale = max_height / widget.height

        core_image = widget.export_as_image(scale=scale)
        return core_image.texture
    except Exception as e:
        Logger.warning("PageScreenshot: Failed to capture widget: %s", e)
        return None
