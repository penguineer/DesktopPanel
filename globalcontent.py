from kivy.core.window import Window
from kivy.event import EventDispatcher
from kivy.lang import Builder

from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.properties import ObjectProperty, StringProperty, OptionProperty, NumericProperty, AliasProperty, \
    BooleanProperty, ColorProperty, DictProperty

from kivy.uix.button import Button

from kivy.animation import Animation
from kivy.graphics import Color, Rectangle, InstructionGroup

from page_screenshot import capture_widget_texture


class PageRouter(EventDispatcher):
    """Routes page navigation by string handle.

    Pages are identified by their ``label`` string (the handle).  Left-border
    pages get a :class:`ContextButton`; tray-area widgets can also be wired
    to a page via :meth:`register_border_button`.

    Dispatches the ``on_page_selected`` event whenever a page navigation is
    requested, including re-selection of the currently active page.
    """

    def __init__(self, content_panel, tab_height, context_buttons_panel, on_page_changed=None,
                 on_wake_screensaver=None):
        super().__init__()
        self.register_event_type('on_page_selected')
        self.register_event_type('on_before_page_switch')

        self._content_panel = content_panel
        self._tab_height = tab_height
        self._context_buttons_panel = context_buttons_panel
        self._on_page_changed = on_page_changed
        self._on_wake_screensaver = on_wake_screensaver

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
                        go_back_if_current: bool = True) -> bool:
        """Switch to the page identified by *handle*.

        :param handle: The page label to switch to.
        :param trip_screensaver: When ``True`` (default), wake the screensaver
            so the screen becomes visible.  Pass ``False`` to change the page
            silently without affecting the screensaver.
        :param go_back_if_current: When ``True`` (default), selecting a page
            that is already active triggers a navigation back on the history
            stack instead of staying on the same page.  Pass ``False`` to force
            the page open without going back (e.g. for programmatic navigation).
        :returns: ``True`` if the page was found and switched to.
        """
        page = self._pages_by_handle.get(handle)
        return self.switch_to_page(page, trip_screensaver=trip_screensaver,
                                   go_back_if_current=go_back_if_current)

    def switch_to_page(self, page, trip_screensaver: bool = True,
                       go_back_if_current: bool = True):
        """Switch to the page.

        :param page: The page to switch to.
        :param trip_screensaver: When ``True`` (default), wake the screensaver
            so the screen becomes visible.  Pass ``False`` to change the page
            silently without affecting the screensaver.
        :param go_back_if_current: When ``True`` (default), selecting a page
            that is already active triggers a navigation back on the history
            stack instead of staying on the same page.  Pass ``False`` to force
            the page open without going back (e.g. for programmatic navigation).
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
            rgba: [249/256, 176/256, 0/256, 1] if root.has_history else [77/256, 77/256, 76/256, 1]
        Triangle:
            points:
                root.x + root.width * 0.65, \
                root.y + root.fill_meter_height + (root.height - root.fill_meter_height) * 0.15, \
                root.x + root.width * 0.25, \
                root.y + root.fill_meter_height + (root.height - root.fill_meter_height) * 0.5, \
                root.x + root.width * 0.65, \
                root.y + root.fill_meter_height + (root.height - root.fill_meter_height) * 0.85
""")


class NavBackWidget(Button):
    """Navigation back button that owns and controls the page history stack.

    Displays a visual back-navigation arrow.  The widget is active (yellow)
    when the navigation stack contains history entries and inactive (grey)
    when the stack is exhausted.  A fill-meter strip at the bottom shows
    scaled thumbnails of pages that have been pushed onto the stack, from
    left to right.

    Wire this widget to a :class:`PageRouter` by binding its callbacks to
    the router's events and setting :attr:`_switch_callback`::

        router.bind(on_page_selected=nav_back._on_page_selected)
        router.bind(on_before_page_switch=nav_back._on_before_page_switch)
        nav_back._switch_callback = router.switch_to_label
    """

    STACK_MAX_DEPTH = 3
    """Maximum number of entries kept on the navigation history stack."""

    has_history = BooleanProperty(False)
    """``True`` when the navigation stack has at least one entry to go back to.

    :attr:`has_history` is a :class:`~kivy.properties.BooleanProperty` and
    defaults to ``False``.
    """

    fill_meter_height = NumericProperty(0)
    """Height in pixels reserved at the bottom of the widget for the fill-meter
    thumbnail strip.  Updated automatically whenever the screenshot list changes.

    :attr:`fill_meter_height` is a :class:`~kivy.properties.NumericProperty`
    and defaults to ``0``.
    """

    def __init__(self, **kwargs):
        self._history = []
        self._screenshots = []      # parallel list of textures, one per _history entry
        self._pending_screenshot = None
        self._going_back = False
        self._current_handle = None
        self._switch_callback = None
        self._fill_meter_group = None
        super().__init__(**kwargs)
        self.bind(size=self._redraw_fill_meter, pos=self._redraw_fill_meter)

    def on_press(self):
        """Kivy event handler: navigate back when the stack is non-empty."""
        if self.has_history:
            self.go_back()

    def go_back(self) -> bool:
        """Navigate to the previously visited page.

        Pops entries from the navigation stack until a page different from the
        current one is found, then switches to it without pushing the current
        page back onto the stack.  Any intermediate stack entries that match
        the current page are discarded.

        :returns: ``True`` if navigation succeeded, ``False`` if the stack is
            empty or contains only entries matching the current page.
        """
        if not self._history:
            return False

        current = self._current_handle
        handle = self._history.pop()
        if self._screenshots:
            self._screenshots.pop()
        while handle == current and self._history:
            handle = self._history.pop()
            if self._screenshots:
                self._screenshots.pop()

        if handle == current:
            self.has_history = bool(self._history)
            self._redraw_fill_meter()
            return False

        self._going_back = True
        result = bool(self._switch_callback and self._switch_callback(handle))
        self._going_back = False
        self.has_history = bool(self._history)
        self._redraw_fill_meter()
        return result

    def _on_before_page_switch(self, _instance, old_page, _new_page):
        """Capture a thumbnail of *old_page* before it is removed from the tree.

        Called by :class:`PageRouter` just before it removes the old page from
        the content panel, so the widget is still fully rendered and FBO
        capture works correctly.  The texture is stashed in
        :attr:`_pending_screenshot` and consumed by the next
        :meth:`_on_page_selected` call.
        """
        if self._going_back:
            self._pending_screenshot = None
            return
        if self._current_handle is None:
            self._pending_screenshot = None
            return

        thumb_w = max(1, int(self.width / self.STACK_MAX_DEPTH))
        # Preserve aspect ratio: compute height from page dimensions
        if old_page.width > 0 and old_page.height > 0:
            thumb_h = max(1, int(thumb_w * old_page.height / old_page.width))
        else:
            thumb_h = thumb_w

        self._pending_screenshot = capture_widget_texture(old_page, thumb_w, thumb_h)

    def _on_page_selected(self, _instance, handle):
        """React to a :class:`PageRouter` ``on_page_selected`` event.

        Pushes the previous page onto the history stack when navigating to a
        different page.  Does nothing during a :meth:`go_back` traversal.
        If the top of the stack already holds the same handle that is being
        pushed, it is popped first so that the handle is always pushed exactly
        once — preventing two consecutive identical entries.
        """
        if self._going_back:
            self._current_handle = handle
            return

        if self._current_handle is not None and self._current_handle != handle:
            if self._history and self._history[-1] == self._current_handle:
                self._history.pop()
                if self._screenshots:
                    self._screenshots.pop()
            self._history.append(self._current_handle)
            self._screenshots.append(self._pending_screenshot)
            self._pending_screenshot = None
            if len(self._history) > self.STACK_MAX_DEPTH:
                self._history.pop(0)
                if self._screenshots:
                    self._screenshots.pop(0)

        self._current_handle = handle
        self.has_history = bool(self._history)
        self._redraw_fill_meter()

    def _redraw_fill_meter(self, *_args):
        """Redraw the fill-meter thumbnail strip on the widget canvas."""
        if self._fill_meter_group is not None:
            self.canvas.remove(self._fill_meter_group)
            self._fill_meter_group = None

        textures = [t for t in self._screenshots if t is not None]
        if not textures:
            self.fill_meter_height = 0
            return

        n = self.STACK_MAX_DEPTH
        slot_w = self.width / n

        # Determine thumbnail height from first texture aspect ratio
        first = textures[0]
        if first.width > 0:
            thumb_h = slot_w * first.height / first.width
        else:
            thumb_h = slot_w * 0.58  # fallback ~16:9 landscape

        self.fill_meter_height = thumb_h

        group = InstructionGroup()
        for i, tex in enumerate(textures):
            x = self.x + i * slot_w
            y = self.y
            group.add(Color(1, 1, 1, 1))
            group.add(Rectangle(texture=tex, pos=(x, y), size=(slot_w, thumb_h)))

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

    def _on_conf(self, _instance, conf: dict) -> None:
        for page in self._pages:
            self._page_conf(page)
        for item in self._status_items:
            conf_lambda = item['conf_lambda']
            widget = item['widget']
            if conf_lambda is not None and hasattr(widget, 'conf'):
                widget.conf = conf_lambda(conf) if conf else None

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
