from kivy.core.window import Window
from kivy.lang import Builder

from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.properties import ObjectProperty, StringProperty, OptionProperty, NumericProperty, AliasProperty, \
    BooleanProperty, ColorProperty, DictProperty

from kivy.uix.button import Button

from kivy.animation import Animation


class PageRouter(object):
    """Routes page navigation by string handle.

    Pages are identified by their ``label`` string (the handle).  Left-border
    pages get a :class:`ContextButton`; tray-area widgets can also be wired
    to a page via :meth:`register_border_button`.  Navigation history is
    recorded for a future "jump back" feature.
    """

    def __init__(self, content_panel, tab_height, context_buttons_panel, on_page_changed=None):
        self._content_panel = content_panel
        self._tab_height = tab_height
        self._context_buttons_panel = context_buttons_panel
        self._on_page_changed = on_page_changed

        self._pages_by_handle = {}
        self._current_page = None
        self._history = []

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
        cbtn.page_callback = lambda h=handle: self.switch_to(h)
        self._context_buttons_panel.add_widget(cbtn)

        if self._current_page is None:
            self.switch_to(handle)

    def register_border_button(self, widget, page=None):
        """Register a border (tray) widget, optionally wiring it to a page."""
        if page is not None:
            handle = page.label
            self._pages_by_handle[handle] = page
            widget.page_callback = lambda h=handle: self.switch_to(h)

            if self._current_page is None:
                self.switch_to(handle)

    def switch_to(self, handle: str) -> bool:
        """Switch to the page identified by *handle*.

        :returns: ``True`` if the page was found and switched to.
        """
        page = self._pages_by_handle.get(handle)
        if page is None:
            return False

        if self._current_page is page:
            return True

        if self._current_page is not None:
            self._content_panel.remove_widget(self._current_page)
            self._current_page.active = False
            self._history.append(self._current_page.label)

        self._current_page = page
        page.active = True
        self._content_panel.add_widget(page)

        if self._on_page_changed:
            self._on_page_changed(page)

        return True

    def switch_to_page(self, page):
        """Convenience: switch by page object rather than handle string."""
        return self.switch_to(page.label)


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
 
        StackLayout:
            id: ContextButtons
            size: [root.tab_width-1, root.height]
            size_hint_x: None
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
        )

        self.bind(conf=self._on_conf)
        self.bind(mqttc=self._on_mqttc)
        self.bind(screensaver=self._on_screensaver)

        # Wake up the screensaver on every touch event
        # Blocks the event if the screen saver is active, so that the user is not poking in the dark (literally)
        Window.bind(on_touch_down=lambda i, e: self.ids.screensaver.wake_up())

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
            self._router.switch_to(self._pages[page].label)

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
