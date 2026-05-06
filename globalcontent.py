import time

import isodate

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.event import EventDispatcher
from kivy.lang import Builder

from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.properties import ObjectProperty, StringProperty, OptionProperty, NumericProperty, AliasProperty, \
    BooleanProperty, ColorProperty, DictProperty

from kivy.uix.button import Button

from kivy.animation import Animation
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line, InstructionGroup


def _parse_nav_ttl(value) -> float:
    """Parse a navigation TTL value to seconds.

    Accepts:

    * A number — interpreted as **minutes** and converted to seconds.
    * An ISO 8601 duration string (e.g. ``"PT1H"``, ``"PT30M"``,
      ``"PT1H30M"``) — parsed via :mod:`isodate` and converted to seconds.

    :raises ValueError: if the value cannot be parsed.
    """
    if isinstance(value, (int, float)):
        return float(value) * 60.0
    try:
        duration = isodate.parse_duration(str(value))
        return duration.total_seconds()
    except isodate.isoerror.ISO8601Error as e:
        raise ValueError(f"Cannot parse navigation TTL value: {value!r}") from e


class PageRouter(EventDispatcher):
    """Routes page navigation by string handle.

    Pages are identified by their ``label`` string (the handle).  Left-border
    pages get a :class:`ContextButton`; tray-area widgets can also be wired
    to a page via :meth:`register_border_button`.

    Dispatches the ``on_page_selected`` event whenever a page navigation is
    requested, including re-selection of the currently active page.
    """

    def __init__(self, content_panel, tab_height, context_buttons_panel, on_page_changed=None,
                 on_wake_screensaver=None, on_block_input=None):
        super().__init__()
        self.register_event_type('on_page_selected')
        self.register_event_type('on_before_page_switch')

        self._content_panel = content_panel
        self._tab_height = tab_height
        self._context_buttons_panel = context_buttons_panel
        self._on_page_changed = on_page_changed
        self._on_wake_screensaver = on_wake_screensaver
        self._on_block_input = on_block_input

        self._pages_by_handle = {}
        self._current_page = None
        self._go_back_callback = None

    def on_page_selected(self, handle):
        """Default handler for the ``on_page_selected`` event (no-op)."""

    def on_before_page_switch(self, old_page, new_page):
        """Default handler for the ``on_before_page_switch`` event (no-op)."""

    @property
    def current_page(self):
        return self._current_page

    @property
    def current_handle(self):
        return self._current_page.label if self._current_page else None

    def add_page(self, page):
        """Register a page with a :class:`ContextButton` in the left border."""
        handle = page.label
        self._pages_by_handle[handle] = page

        cbtn = page.create_context_button(length=self._tab_height)
        cbtn.page_callback = lambda h=handle: self.switch_to_label(h)
        self._context_buttons_panel.add_widget(cbtn)

        if self._current_page is None:
            self.switch_to_label(handle)

    def register_border_button(self, widget, page=None):
        """Register a border (tray) widget, optionally wiring it to a page."""
        if page is not None:
            handle = page.label
            self._pages_by_handle[handle] = page
            widget.page_callback = lambda h=handle: self.switch_to_label(h)

            if self._current_page is None:
                self.switch_to_label(handle)

    def switch_to_label(self, handle: str, trip_screensaver: bool = True,
                        go_back_if_current: bool = True, block_input: bool = False) -> bool:
        """Switch to the page identified by *handle*.

        :param handle: The page label to switch to.
        :param trip_screensaver: When ``True`` (default), wake the screensaver
            so the screen becomes visible.  Pass ``False`` to change the page
            silently without affecting the screensaver.
        :param go_back_if_current: When ``True`` (default), selecting a page
            that is already active triggers a navigation back on the history
            stack instead of staying on the same page.  Pass ``False`` to force
            the page open without going back (e.g. for programmatic navigation).
        :param block_input: When ``True``, trigger a short input-block with a
            desaturation overlay after the page switch so that an accidental tap
            on the new page cannot fire.  Intended for programmatic (e.g. AMQP)
            page switches.  Defaults to ``False``.
        :returns: ``True`` if the page was found and switched to.
        """
        page = self._pages_by_handle.get(handle)
        return self.switch_to_page(page, trip_screensaver=trip_screensaver,
                                   go_back_if_current=go_back_if_current,
                                   block_input=block_input)

    def switch_to_page(self, page, trip_screensaver: bool = True,
                       go_back_if_current: bool = True, block_input: bool = False):
        """Switch to the page.

        :param page: The page to switch to.
        :param trip_screensaver: When ``True`` (default), wake the screensaver
            so the screen becomes visible.  Pass ``False`` to change the page
            silently without affecting the screensaver.
        :param go_back_if_current: When ``True`` (default), selecting a page
            that is already active triggers a navigation back on the history
            stack instead of staying on the same page.  Pass ``False`` to force
            the page open without going back (e.g. for programmatic navigation).
        :param block_input: When ``True``, trigger a short input-block with a
            desaturation overlay after the page switch so that an accidental tap
            on the new page cannot fire.  Intended for programmatic (e.g. AMQP)
            page switches.  Defaults to ``False``.
        :returns: ``True`` if the page was found and switched to.
        """

        if page is None:
            return False

        if trip_screensaver and self._on_wake_screensaver:
            self._on_wake_screensaver()

        if self._current_page is page:
            if go_back_if_current and self._go_back_callback and self._go_back_callback():
                return True
            self.dispatch('on_page_selected', page.label)
            return True

        if self._current_page is not None:
            self.dispatch('on_before_page_switch', self._current_page, page)
            self._content_panel.remove_widget(self._current_page)
            self._current_page.active = False

        self._current_page = page
        page.active = True
        self._content_panel.add_widget(page)

        if self._on_page_changed:
            self._on_page_changed(page)

        if block_input and self._on_block_input:
            self._on_block_input()

        self.dispatch('on_page_selected', page.label)

        return True

    def go_back(self) -> bool:
        """Navigate back to the previously visited page.

        Delegates to the go-back callback owned by the :class:`NavBackWidget`.

        :returns: ``True`` if navigation succeeded, ``False`` if there is no
            history or no go-back callback is registered.
        """
        if self._go_back_callback:
            return bool(self._go_back_callback())
        return False


class ContentPage(RelativeLayout):
    conf_lambda = ObjectProperty(None)
    """ If this lambda is set, the conf property is determined (by a calling party, i.e. the
        GlobalContentArea) to determine the configuration from a global configuration. 
    """

    conf = DictProperty(None)
    mqttc = ObjectProperty(None)

    label = StringProperty(None)
    icon = StringProperty(None)

    active = BooleanProperty(False)

    def on_active(self, _instance, value):
        if self.btn is not None:
            self.btn.active = value

    notification = OptionProperty("None", options=["None",
                                                   "Info",
                                                   "Warning",
                                                   "Critical",
                                                   "Alert"])

    def on_notification(self, _instance, state):
        if self.btn is not None:
            self.btn.notify_state = state

    btn = ObjectProperty(None, rebind=True)

    def on_btn(self, _instance, value):
        if value is not None:
            value.notify_state = self.notification
            value.active = self.active

    def __init__(self, **kwargs):
        super(RelativeLayout, self).__init__(**kwargs)

        self._btn = None

    def create_context_button(self, length):
        """Create a :class:`ContextButton` for this page.

        The returned button has no ``page_callback`` set; the caller (typically
        :class:`PageRouter`) is responsible for wiring the callback immediately
        after creation.
        """
        self.btn = ContextButton(icon_path=self.icon,
                                 size=(length, length))
        return self.btn


Builder.load_string("""
<ContextButton>:
    size_hint_y: None
    background_normal: ''
    background_down: ''
    background_color: 0, 0, 0, 1

    Image:
        source: 'assets/context_notify_frame.png'
        x: self.parent.x
        y: self.parent.y 
        size: (64, 64)
        color: root._notify_color

    Image:
        #:set l_active 48
        #:set l_inactive 32
        source: root.icon_path
        x:
            self.parent.x + (self.parent.width / 2) \
            - ((l_active if root.active else l_inactive) / 2)
        y:
            self.parent.y + (self.parent.height / 2) \
            - ((l_active if root.active else l_inactive) / 2)
        size: ((l_active if root.active else l_inactive), (l_active if root.active else l_inactive))
        color: root.icon_active_color if root.active else root.icon_inactive_color
""")


class ContextButton(Button):
    notify_state = OptionProperty("None", options=["None",
                                                   "Info",
                                                   "Warning",
                                                   "Critical",
                                                   "Alert"])

    notify_colors = {
        "None": [0 / 256, 0 / 256, 0 / 256, 1],
        "Info": [0 / 256, 132 / 256, 176 / 256, 1],
        "Warning": [249 / 256, 176 / 256, 0 / 256, 1],
        "Critical": [228 / 256, 5 / 256, 41 / 256, 1],
        "Alert": [228 / 256, 5 / 256, 41 / 256, 1]
    }

    def on_notify_state(self, _instance, value):
        if value == "Alert":
            self._notify_color = [0, 0, 0, 0]
            self._alert_anim.start(self)
        else:
            self._alert_anim.cancel(self)
            self._notify_color = self.notify_colors[value]

    _notify_color = ColorProperty()

    icon_active_color = ColorProperty([249 / 256, 176 / 256, 0 / 256, 1])
    icon_inactive_color = ColorProperty([77 / 256, 77 / 256, 76 / 256, 1])
    icon_path = StringProperty(None)

    active = BooleanProperty(False)

    index = NumericProperty(0)

    page_callback = ObjectProperty(None, allownone=True)

    def __init__(self, icon_path=None, **kwargs):
        self.icon_path = icon_path

        # Alert animation
        anim_in = Animation(_notify_color=[228 / 256, 5 / 256, 41 / 256, 1], duration=1., t='out_cubic')
        anim_out = Animation(_notify_color=[228 / 256, 5 / 256, 41 / 256, 0], duration=1., t='in_cubic')
        self._alert_anim = anim_in + anim_out
        self._alert_anim.repeat = True

        super(Button, self).__init__(**kwargs, text="")
        self.on_notify_state(self, "None")
        self.bind(on_press=self._on_press_dispatch)

    def _on_press_dispatch(self, _instance):
        if self.page_callback and callable(self.page_callback):
            self.page_callback()


Builder.load_string("""
<NavBackWidget>:
    background_normal: ''
    background_down: ''
    background_color: 0, 0, 0, 1
    text: ''
    canvas.after:
        Color:
            rgba: [68/256, 53/256, 126/256, 1] if root.has_history else [77/256, 77/256, 76/256, 1]
        # Filled left-pointing arrowhead
        Triangle:
            points: root.x + root.width * 0.20, root.y + root.height * 0.65, \
                    root.x + root.width * 0.38, root.y + root.height * 0.77, \
                    root.x + root.width * 0.38, root.y + root.height * 0.53
        # Arrow shaft running from the arrowhead base to the right
        Line:
            width: 1.5
            cap: 'square'
            points: root.x + root.width * 0.38, root.y + root.height * 0.65, \
                    root.x + root.width * 0.80, root.y + root.height * 0.65
""")


class NavBackWidget(Button):
    """Navigation back button that owns and controls the page history stack.

    Displays a visual back-navigation arrow.  The widget is active (lilac)
    when the navigation stack contains history entries and inactive (grey)
    when the stack is exhausted.  A fill-meter strip at the bottom shows
    a lilac slot for each occupied history entry and a grey slot for each
    remaining empty capacity, up to :attr:`STACK_MAX_DEPTH`.

    Wire this widget to a :class:`PageRouter` by binding its callbacks to
    the router's events and setting :attr:`_switch_callback`::

        router.bind(on_page_selected=nav_back._on_page_selected)
        router.bind(on_before_page_switch=nav_back._on_before_page_switch)
        nav_back._switch_callback = router.switch_to_label
    """

    STACK_MAX_DEPTH = 3
    """Maximum number of entries kept on the navigation history stack."""

    _DEFAULT_TTL_SECONDS = 3600.0
    """Default time-to-live for a navigation stack entry, in seconds (1 hour)."""

    # Fallback inverse aspect ratio (height/width) used to size fill-meter slots
    # when the Window dimensions are not yet available.  9/16 is the portrait
    # reciprocal of the standard 16:9 landscape display used by the target hardware.
    _FALLBACK_THUMB_ASPECT = 9 / 16

    # Width in pixels of the gap drawn between fill-meter slots so that the
    # background colour shows through and individual slots remain countable.
    _SLOT_SEPARATOR_WIDTH = 2

    # Gap in pixels between the fill-meter strip and the left, right, and bottom
    # borders of the widget.
    _BORDER_GAP = 8

    # Horizontal extent of the arrow as fractions of widget width.
    # The arrowhead tip is at _ARROW_LEFT and the shaft end is at _ARROW_RIGHT.
    _ARROW_LEFT = 0.20
    _ARROW_RIGHT = 0.80

    has_history = BooleanProperty(False)
    """``True`` when the navigation stack has at least one entry to go back to.

    :attr:`has_history` is a :class:`~kivy.properties.BooleanProperty` and
    defaults to ``False``.
    """

    def __init__(self, **kwargs):
        # Each entry in _history is a (handle: str, pushed_at: float) tuple,
        # where pushed_at is a time.monotonic() timestamp recorded when the entry
        # was pushed.  Expiry is evaluated as pushed_at + _ttl_seconds at
        # purge/check time so that a TTL config change applies to all entries.
        self._history = []
        self._going_back = False
        self._current_handle = None
        self._switch_callback = None
        self._fill_meter_group = None
        self._ttl_seconds = self._DEFAULT_TTL_SECONDS
        self._expiry_event = None  # single pending Clock event for the next expiry
        super().__init__(**kwargs)
        # Read the real display aspect ratio (portrait h/w) once at startup so
        # fill-meter slots reflect the actual screen proportions.  Falls back to
        # the 16:9 default when Window dimensions are not yet available.
        w, h = Window.width, Window.height
        self._display_aspect = (h / w) if (w > 0 and h > 0) else self._FALLBACK_THUMB_ASPECT
        self.bind(size=self._redraw_fill_meter, pos=self._redraw_fill_meter)

    def on_press(self):
        """Kivy event handler: navigate back when the stack is non-empty."""
        if self.has_history:
            self.go_back()

    def go_back(self) -> bool:
        """Navigate to the previously visited page.

        Purges any TTL-expired entries first, then pops entries from the
        navigation stack until a page different from the current one is found,
        then switches to it without pushing the current page back onto the stack.
        Any intermediate stack entries that match the current page are discarded.

        :returns: ``True`` if navigation succeeded, ``False`` if the stack is
            empty or contains only entries matching the current page.
        """
        self._purge_expired()
        if not self._history:
            return False

        current = self._current_handle
        handle, _ = self._history.pop()
        while handle == current and self._history:
            handle, _ = self._history.pop()

        if handle == current:
            self.has_history = bool(self._history)
            self._redraw_fill_meter()
            self._schedule_expiry()
            return False

        self._going_back = True
        result = bool(self._switch_callback and self._switch_callback(handle))
        self._going_back = False
        self.has_history = bool(self._history)
        self._redraw_fill_meter()
        self._schedule_expiry()
        return result

    def _on_before_page_switch(self, _instance, _old_page, _new_page):
        """No-op hook kept for PageRouter event-binding compatibility."""

    def _on_page_selected(self, _instance, handle):
        """React to a :class:`PageRouter` ``on_page_selected`` event.

        Pushes the previous page onto the history stack when navigating to a
        different page.  Does nothing during a :meth:`go_back` traversal.
        If the top of the stack already holds the same handle that is being
        pushed, it is popped first so that the handle is always pushed exactly
        once — preventing two consecutive identical entries.
        Each pushed entry records ``time.monotonic()`` as its push timestamp.
        Expiry is evaluated as ``pushed_at + _ttl_seconds`` at purge time so
        that a TTL config change applies to all existing entries immediately.
        """
        if self._going_back:
            self._current_handle = handle
            return

        if self._current_handle is not None and self._current_handle != handle:
            if self._history and self._history[-1][0] == self._current_handle:
                self._history.pop()
            pushed_at = time.monotonic()
            self._history.append((self._current_handle, pushed_at))
            if len(self._history) > self.STACK_MAX_DEPTH:
                self._history.pop(0)
            self._schedule_expiry()

        self._current_handle = handle
        self.has_history = bool(self._history)
        self._redraw_fill_meter()

    def _purge_expired(self):
        """Remove all TTL-expired entries from the history stack.

        Called lazily before any pop operation and proactively from the
        scheduled expiry timer.  Updates :attr:`has_history` and redraws
        the fill meter if any entries were removed.
        """
        now = time.monotonic()
        if not any(t + self._ttl_seconds <= now for _, t in self._history):
            self._schedule_expiry()
            return
        self._history = [(h, t) for h, t in self._history if t + self._ttl_seconds > now]
        self.has_history = bool(self._history)
        self._redraw_fill_meter()
        self._schedule_expiry()

    def _on_expiry_timer(self, _dt):
        """Clock callback: fired when the oldest stack entry is due to expire."""
        self._expiry_event = None
        self._purge_expired()

    def _schedule_expiry(self):
        """Schedule (or cancel) a single Clock event for the next TTL expiry.

        Cancels any previously scheduled event and sets a new one timed for
        when the oldest remaining stack entry expires, using the current
        ``_ttl_seconds``.  No event is scheduled when the stack is empty.
        Must be called after any change to ``_ttl_seconds`` or ``_history`` so
        that the pending timer always reflects the current configuration.
        """
        if self._expiry_event is not None:
            self._expiry_event.cancel()
            self._expiry_event = None

        if not self._history:
            return

        now = time.monotonic()
        earliest = min(t + self._ttl_seconds for _, t in self._history)
        delay = max(0.0, earliest - now)
        self._expiry_event = Clock.schedule_once(self._on_expiry_timer, delay)

    def set_stack_ttl(self, ttl_seconds: float) -> None:
        """Set the time-to-live for navigation stack entries.

        All existing entries are immediately evaluated against the new TTL
        and the expiry timer is rescheduled accordingly.

        :param ttl_seconds: New TTL in seconds.  Must be a non-negative number.
        :raises ValueError: if *ttl_seconds* is negative.
        """
        if ttl_seconds < 0:
            raise ValueError(f"stack TTL must be non-negative, got {ttl_seconds!r}")
        self._ttl_seconds = ttl_seconds
        self._schedule_expiry()

    def _redraw_fill_meter(self, *_args):
        """Redraw the fill-meter slot strip on the widget canvas.

        All :attr:`STACK_MAX_DEPTH` slots are drawn at the bottom of the widget,
        inset by :attr:`_BORDER_GAP` pixels from the left, right, and bottom edges.
        Occupied slots are shown as lilac rounded rectangles; empty slots are shown
        as dark-grey rounded rectangles.  A narrow gap separates each slot so the
        total slot count is always visible.

        The arrow (drawn in ``canvas.after``) is always rendered on top of the
        fill meter.
        """
        if self._fill_meter_group is not None:
            self.canvas.remove(self._fill_meter_group)
            self._fill_meter_group = None

        if self.width <= 0:
            return

        n = self.STACK_MAX_DEPTH
        gap = self._SLOT_SEPARATOR_WIDTH

        # Horizontal span: full widget width minus 8 px on each side.
        meter_x = self.x + self._BORDER_GAP
        meter_w = self.width - 2 * self._BORDER_GAP
        slot_w = (meter_w - gap * (n - 1)) / n

        # Slot height: real display aspect ratio (portrait h/w), capped so the
        # fill meter does not crowd the arrow area.
        thumb_h = min(slot_w * self._display_aspect, self.height * 0.4)

        # Vertical position: sit 8 px above the bottom edge.
        slot_y = self.y + self._BORDER_GAP

        # Corner radius: 1.5 px — just enough to round without looking circular.
        radius = 1.5

        occupied = len(self._history)

        group = InstructionGroup()
        for i in range(n):
            x = meter_x + i * (slot_w + gap)
            if i < occupied:
                # Occupied slot: lilac rounded rectangle
                group.add(Color(68 / 256, 53 / 256, 126 / 256, 1))
            else:
                # Empty slot: grey rounded rectangle
                group.add(Color(77 / 256, 77 / 256, 76 / 256, 1))
            group.add(RoundedRectangle(pos=(x, slot_y), size=(slot_w, thumb_h), radius=[radius]))

        self.canvas.add(group)
        self._fill_meter_group = group


Builder.load_string("""
#:import ScreenSaver screensaver.ScreenSaver
#:import BacklightControl backlight.BacklightControl

<GlobalContentArea>:
    anchor_y: 'top'
    anchor_x: 'left'
    
    screensaver: screensaver
    
    canvas:
        #:set border_spacing 10
        Color:
            rgba: self.border_color

        # Vert divider line
        Line:
            points: [self.tab_width+2, border_spacing, self.tab_width+2, self.height-border_spacing]
            width: 1
            cap: 'none'
            
        # Horiz divider line
        Line:
            points: 
                self.tab_width+2+border_spacing, self.height - self.status_height - 2, \
                self.width-border_spacing, self.height - self.status_height - 2
            width: 1
            cap: 'none'

    BoxLayout:
        orientation: 'horizontal'
        spacing: 5

        BoxLayout:
            orientation: 'vertical'
            size_hint_x: None
            width: root.tab_width - 1
            spacing: 5

            NavBackWidget:
                id: nav_back
                size_hint: 1, None
                height: root.status_height

            StackLayout:
                id: ContextButtons
                orientation: 'lr-bt'
            
        BoxLayout: 
            orientation: 'vertical'
            spacing: 5

            BoxLayout:
                id: status_area
                orientation: 'horizontal'
                size_hint_y: None
                height: root.status_height
                spacing: 10
                padding: [10, 0]

                BoxLayout:
                    id: status_items
                    orientation: 'horizontal'
                    size_hint: None, 1
                    width: self.minimum_width
                    spacing: 10

                Widget:
                    # Spacer stretches between the two item boxes
                    size_hint_x: 1

                BoxLayout:
                    id: tray_items
                    orientation: 'horizontal'
                    size_hint: None, 1
                    width: self.minimum_width
                    spacing: 5
    
            AnchorLayout:          
                size: [root.width - root.tab_width-4, root.height - root.status_height - 4]
                anchor_x: 'left'
                anchor_y: 'top'
                id: ContentPanel


    # Screen saver on top of everything
    ScreenSaver:
        id: screensaver
        conf: root.conf.get("screen", None) if root.conf else None
        
    BacklightControl:
        id: backlight
        conf: root.conf.get("screen", None) if root.conf else None
        power: not screensaver.active        
""")


class GlobalContentArea(AnchorLayout):
    """Base window for the application, hosts context buttons, status bar and content area.

    Some properties copied from Kivy's TabbedPanel
    """

    conf = DictProperty(None)
    """Application configuration"""

    mqttc = ObjectProperty(None)
    """MQTT client for the application"""

    screensaver = ObjectProperty(None, allownone=True)

    background_color = ColorProperty([0, 0, 0, 1])
    """Background color, in the format (r, g, b, a).

    :attr:`background_color` is a :class:`~kivy.properties.ColorProperty` and
    defaults to [1, 1, 1, 1].
    """
    border_color = ColorProperty([77 / 256, 77 / 256, 76 / 256, 1])
    """Border color, in the format (r, g, b, a).

    :attr:`border_color` is a :class:`~kivy.properties.ColorProperty` and
    defaults to [77/256, 177/256, 76/256, 1].
    """

    _current_page = ObjectProperty(None)

    def get_current_page(self):
        return self._current_page

    current_page = AliasProperty(get_current_page, None, bind=('_current_page',))
    """Links to the currently selected or active page.

    :attr:`current_page` is an :class:`~kivy.AliasProperty`, read-only.
    """

    tab_height = NumericProperty('64px')
    '''Specifies the height of the tab header.

    :attr:`tab_height` is a :class:`~kivy.properties.NumericProperty` and
    defaults to 64.
    '''

    tab_width = NumericProperty('64px', allownone=True)
    '''Specifies the width of the tab header.

    :attr:`tab_width` is a :class:`~kivy.properties.NumericProperty` and
    defaults to 64.
    '''

    status_height = NumericProperty('50px')
    '''Specifies the height of the status bar.

    :attr:`status_height` is a :class:`~kivy.properties.NumericProperty` and
    defaults to 100.
    '''

    def __init__(self, **kwargs):
        self._pages = []
        self._status_items = []

        super(GlobalContentArea, self).__init__(**kwargs)

        self._router = PageRouter(
            content_panel=self.ids.ContentPanel,
            tab_height=self.tab_height,
            context_buttons_panel=self.ids.ContextButtons,
            on_page_changed=lambda page: setattr(self, '_current_page', page),
            on_wake_screensaver=self._wake_screensaver,
            on_block_input=self._block_screensaver,
        )
        nav_back = self.ids.nav_back
        self._router.bind(on_page_selected=nav_back._on_page_selected)
        self._router.bind(on_before_page_switch=nav_back._on_before_page_switch)
        nav_back._switch_callback = self._router.switch_to_label
        self._router._go_back_callback = nav_back.go_back

        self.bind(conf=self._on_conf)
        self.bind(mqttc=self._on_mqttc)
        self.bind(screensaver=self._on_screensaver)

        # Wake up the screensaver on every touch event
        # Blocks the event if the screen saver is active, so that the user is not poking in the dark (literally)
        Window.bind(on_touch_down=lambda i, e: self.ids.screensaver.wake_up())

    def _wake_screensaver(self) -> None:
        if self.screensaver:
            self.screensaver.wake_up()

    def _block_screensaver(self) -> None:
        if self.screensaver:
            self.screensaver.trigger_block()

    def _on_conf(self, _instance, conf: dict) -> None:
        for page in self._pages:
            self._page_conf(page)
        for item in self._status_items:
            conf_lambda = item['conf_lambda']
            widget = item['widget']
            if conf_lambda is not None and hasattr(widget, 'conf'):
                widget.conf = conf_lambda(conf) if conf else None
        self._apply_nav_conf(conf)

    def _apply_nav_conf(self, conf: dict) -> None:
        """Read ``conf["navigation"]`` and apply settings to the nav-back widget.

        Recognised keys under ``"navigation"``:

        * ``"stack_ttl"`` — time-to-live for history stack entries, given as a
          number (minutes) or an ISO 8601 duration string (e.g. ``"PT1H"``).
          Defaults to 1 hour when not set.  When the value changes the expiry
          timer is rescheduled immediately so that all existing stack entries
          are evaluated against the new TTL.
        """
        nav_conf = conf.get("navigation", {}) if conf else {}
        ttl_value = nav_conf.get("stack_ttl", None)
        if ttl_value is not None:
            try:
                self.ids.nav_back.set_stack_ttl(_parse_nav_ttl(ttl_value))
            except ValueError as e:
                from kivy import Logger
                Logger.warning("App: Invalid navigation stack_ttl value %r: %s", ttl_value, e)

    def _page_conf(self, page):
        if page and page.conf_lambda:
            page.conf = page.conf_lambda(self.conf) if self.conf else dict()

    def _on_mqttc(self, _instance, mqttc) -> None:
        for page in self._pages:
            page.mqttc = mqttc
        for item in self._status_items:
            widget = item['widget']
            if hasattr(widget, 'mqttc'):
                widget.mqttc = mqttc

    def _on_screensaver(self, _instance, screensaver) -> None:
        for item in self._status_items:
            widget = item['widget']
            if hasattr(widget, 'screensaver'):
                widget.screensaver = screensaver

    def set_page(self, page):
        if 0 <= page < len(self._pages):
            self._router.switch_to_label(self._pages[page].label)

    def register_content(self, page):
        self._pages.append(page)

        # set configuration
        self._page_conf(page)

        # set mqttc property
        page.mqttc = self.mqttc

        self._router.add_page(page)

    def register_border_button(self, widget, page=None):
        """Register a border (tray) widget, optionally associating it with a page.

        If *page* is provided it is registered with the router so that touching
        *widget* navigates to it.  *page* also receives the global conf/mqttc
        updates via the standard :meth:`_on_conf` / :meth:`_on_mqttc` hooks.
        """
        if page is not None:
            self._pages.append(page)
            self._page_conf(page)
            page.mqttc = self.mqttc

        self._router.register_border_button(widget, page)

    @property
    def router(self):
        return self._router

    def _register_bar_widget(self, widget, box_id, conf_lambda=None):
        """Add *widget* to the named status bar box and wire configuration."""
        widget.size_hint_x = None
        self._status_items.append({'widget': widget, 'conf_lambda': conf_lambda})
        self.ids[box_id].add_widget(widget)
        if conf_lambda is not None and hasattr(widget, 'conf'):
            widget.conf = conf_lambda(self.conf) if self.conf else None
        if hasattr(widget, 'mqttc'):
            widget.mqttc = self.mqttc
        if hasattr(widget, 'screensaver'):
            widget.screensaver = self.screensaver

    def register_status_item(self, widget, conf_lambda=None):
        """Register a widget in the left status bar area (grows left-to-right)."""
        self._register_bar_widget(widget, 'status_items', conf_lambda)

    def register_tray_item(self, widget, conf_lambda=None):
        """Register a widget in the right tray area (grows left-to-right)."""
        self._register_bar_widget(widget, 'tray_items', conf_lambda)
