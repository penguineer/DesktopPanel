""" Module for scrollable list with scroll indicator overlay """

from kivy.lang import Builder
from kivy.properties import BooleanProperty
from kivy.uix.floatlayout import FloatLayout


def _compute_scroll_indicators(content_height, view_height, scroll_y):
    """Compute whether scroll indicator arrows should be visible.

    :param content_height: Total pixel height of the scrollable content.
    :param view_height: Pixel height of the visible viewport.
    :param scroll_y: Current vertical scroll position (1.0 = top, 0.0 = bottom).
    :returns: Tuple ``(has_more_above, has_more_below)``.
    """
    has_overflow = content_height > view_height
    has_more_above = has_overflow and scroll_y < 0.999
    has_more_below = has_overflow and scroll_y > 0.001
    return has_more_above, has_more_below


Builder.load_string("""
<ScrollableList>:
    # ▲ overlaid at the very top of the list
    Label:
        text: '▲'
        font_size: 12
        font_name: 'assets/FiraMono-Regular.ttf'
        color: 77/256.0, 77/256.0, 76/256.0, 1
        halign: 'center'
        valign: 'center'
        size_hint: 1, None
        height: 14
        pos_hint: {'top': 1}
        opacity: 1 if root._has_more_above else 0

    # ▼ overlaid at the very bottom of the list
    Label:
        text: '▼'
        font_size: 12
        font_name: 'assets/FiraMono-Regular.ttf'
        color: 77/256.0, 77/256.0, 76/256.0, 1
        halign: 'center'
        valign: 'center'
        size_hint: 1, None
        height: 14
        pos_hint: {'y': 0}
        opacity: 1 if root._has_more_below else 0
""")


class ScrollableList(FloatLayout):
    """FloatLayout that overlays ▲/▼ scroll-indicator arrows on a scrollable child.

    Wrap any :class:`~kivy.uix.scrollview.ScrollView` or
    :class:`~kivy.uix.recycleview.RecycleView` inside this widget and call
    :meth:`bind_scroll_view` with that widget after the KV tree is built
    (e.g. inside ``on_kv_post``).  The arrows automatically appear whenever
    there is content hidden above or below the visible area.

    To force an indicator refresh after the list data changes, call
    :meth:`update_indicators`.
    """

    _has_more_above = BooleanProperty(False)
    _has_more_below = BooleanProperty(False)

    def bind_scroll_view(self, sv):
        """Bind scroll-position tracking to a ScrollView or RecycleView.

        :param sv: The scrollable widget whose ``scroll_y`` drives the
                   indicator visibility.
        """
        sv.bind(scroll_y=self._on_scroll)
        # Raise the scroll-indicator arrows to the top of the children stack
        # so they render *after* the StencilView (ScrollView/RecycleView).
        # This guarantees the GL stencil state is clean when the arrow Labels
        # are drawn, preventing them from being invisible when the dialog is
        # opened over pages that contain other RecycleView/ScrollView widgets.
        self._raise_arrows()

    def _raise_arrows(self):
        """Re-order scroll indicator labels to render on top of the scroll view.

        Removes and re-adds the ▲/▼ labels so that they are the last children
        rendered (children[0] and children[1] in Kivy's stack), placing them
        visually above the scroll content and ensuring they paint after any
        StencilView push/pop cycle.
        """
        # Take a snapshot before removing (remove_widget mutates self.children).
        arrows = [c for c in list(self.children) if getattr(c, 'text', '') in ('▲', '▼')]
        for arrow in arrows:
            self.remove_widget(arrow)
        for arrow in arrows:
            self.add_widget(arrow)

    def _on_scroll(self, sv, scroll_y):
        """Update ▲/▼ indicator visibility on every scroll event."""
        try:
            # RecycleView exposes content height via layout_manager
            content_height = sv.layout_manager.height
        except AttributeError:
            # ScrollView: first child is the content container
            content_height = sv.children[0].height if sv.children else 0
        self._has_more_above, self._has_more_below = _compute_scroll_indicators(
            content_height, sv.height, scroll_y
        )

    def update_indicators(self, sv):
        """Manually refresh the ▲/▼ indicator state.

        Call this after the list data changes so that the arrows reflect the
        new content height immediately, without waiting for a scroll event.

        :param sv: The same scrollable widget passed to :meth:`bind_scroll_view`.
        """
        self._on_scroll(sv, sv.scroll_y)
