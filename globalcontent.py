from kivy.core.window import Window
from kivy.lang import Builder

from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.properties import ObjectProperty, StringProperty, OptionProperty, NumericProperty, AliasProperty, \
    BooleanProperty, ColorProperty, DictProperty

from kivy.uix.button import Button

from kivy.animation import Animation


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

    def create_context_button(self, length, cb):
        self.btn = ContextButton(icon_path=self.icon,
                                 on_press=cb,
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

    def __init__(self, icon_path=None, **kwargs):
        self.icon_path = icon_path

        # Alert animation
        anim_in = Animation(_notify_color=[228 / 256, 5 / 256, 41 / 256, 1], duration=1., t='out_cubic')
        anim_out = Animation(_notify_color=[228 / 256, 5 / 256, 41 / 256, 0], duration=1., t='in_cubic')
        self._alert_anim = anim_in + anim_out
        self._alert_anim.repeat = True

        super(Button, self).__init__(**kwargs, text="")
        self.on_notify_state(self, "None")


Builder.load_string("""
#:import ScreenSaver screensaver.ScreenSaver
#:import BacklightControl backlight.BacklightControl

#:import StatusBar statusbar.StatusBar

<GlobalContentArea>:
    anchor_y: 'top'
    anchor_x: 'left'
    
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

            StatusBar:
                size: [root.width - root.tab_width-4, root.status_height]
                size_hint_x: None
                size_hint_y: None
                anchor_y: 'top'   
                anchor_x: 'left'         
                id: StatusBar
                conf: root.conf
                mqttc: root.mqttc
    
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
        self._statusbar = None

        super(GlobalContentArea, self).__init__(**kwargs)

        self.bind(conf=self._on_conf)
        self.bind(mqttc=self._on_mqttc)

        # Wake up the screensaver on every touch event
        # Blocks the event if the screen saver is active, so that the user is not poking in the dark (literally)
        Window.bind(on_touch_down=lambda i, e: self.ids.screensaver.wake_up())

    def _on_conf(self, _instance, _conf: dict) -> None:
        for page in self._pages:
            self._page_conf(page)

    def _page_conf(self, page):
        if page and page.conf_lambda:
            page.conf = page.conf_lambda(self.conf) if self.conf else dict()

    def _on_mqttc(self, _instance, mqttc) -> None:
        for page in self._pages:
            page.mqttc = mqttc

    def set_page(self, page):
        if self._current_page is not None:
            self.ids.ContentPanel.remove_widget(self._current_page)
            self._current_page.active = False

        self._current_page = self._pages[page]

        self._current_page.active = True
        self.ids.ContentPanel.add_widget(self._current_page)

    def register_content(self, page):
        index = len(self._pages)
        self._pages.append(page)

        # set configuration
        self._page_conf(page)

        # set mqttc property
        page.mqttc = self.mqttc

        cbtn = page.create_context_button(length=self.tab_height,
                                          cb=lambda inst: self.set_page(index))
        self.ids.ContextButtons.add_widget(cbtn)

        if self._current_page is None:
            self.set_page(index)

    @property
    def status_bar(self):
        return self.ids.StatusBar
