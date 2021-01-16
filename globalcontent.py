from kivy.lang import Builder

from kivy.uix.anchorlayout import AnchorLayout
from kivy.properties import ObjectProperty, StringProperty, OptionProperty, NumericProperty, AliasProperty, \
    BooleanProperty, ColorProperty

from kivy.uix.button import Button

from kivy.animation import Animation


class ContentPage:
    def __init__(self, index, label, icon, content):
        self._index = index
        self._label = label
        self._icon = icon
        self._content = content

        self._btn = None

    def create_context_button(self, length, cb):
        self._btn = ContextButton(index=self._index,
                                  icon_path=self._icon,
                                  on_press=cb,
                                  size=(length, length))
        return self._btn

    @property
    def index(self):
        return self._index

    @property
    def label(self):
        return self._label

    @property
    def icon(self):
        return self._icon

    @property
    def content(self):
        return self._content

    @property
    def btn(self):
        return self._btn


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
        color: root._notify_color

    Image:
        #:set l_active 64
        #:set l_inactive 48
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

    def __init__(self, index=0, icon_path=None, **kwargs):
        self.index = index
        self.icon_path = icon_path

        # Alert animation
        anim_in = Animation(_notify_color=[228 / 256, 5 / 256, 41 / 256, 1], duration=1., t='out_cubic')
        anim_out = Animation(_notify_color=[228 / 256, 5 / 256, 41 / 256, 0], duration=1., t='in_cubic')
        self._alert_anim = anim_in + anim_out
        self._alert_anim.repeat = True

        super(Button, self).__init__(**kwargs, text="")
        self.on_notify_state(self, "None")


Builder.load_string("""

<GlobalContentArea>:
    anchor_y: 'top'
    anchor_x: 'left'
    size_hint: 1, 1
    pos_hint: {'center_x': .5, 'center_y': .5}
    tab_width: 100
    tab_height: 100
    
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
            size: [root.tab_width-1, 50]
            size_hint_y: None
            #anchor_x: 'left'
            orientation: 'lr-bt'
       
        AnchorLayout:
            size: [root.width - root.tab_width-4, 50]
            size_hint_x: None
            anchor_y: 'top'
            
            BoxLayout: 
                orientation: 'vertical'
                spacing: 5
                
                AnchorLayout:
                    id: StatusBar
                    size: [300, root.status_height - 1]
                    size_hint_y: None
                    anchor_y: 'top'
    
                AnchorLayout:          
                    size: [300, root.height - root.status_height - 4]
                    size_hint_y: None
                    anchor_x: 'left'
                    anchor_y: 'top'
                    
                    AnchorLayout:
                        id: ContentPanel
                        anchor_x: 'left'
                        anchor_y: 'top'                   
""")


class GlobalContentArea(AnchorLayout):
    """Base window for the application, hosts context buttons, status bar and content area.

    Some properties copied from Kivy's TabbedPanel
    """

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

    tab_height = NumericProperty('100dp')
    '''Specifies the height of the tab header.

    :attr:`tab_height` is a :class:`~kivy.properties.NumericProperty` and
    defaults to 100.
    '''

    tab_width = NumericProperty('100dp', allownone=True)
    '''Specifies the width of the tab header.

    :attr:`tab_width` is a :class:`~kivy.properties.NumericProperty` and
    defaults to 100.
    '''

    status_height = NumericProperty('50dp')
    '''Specifies the height of the status bar.

    :attr:`status_height` is a :class:`~kivy.properties.NumericProperty` and
    defaults to 100.
    '''

    def __init__(self, **kwargs):
        self._pages = []
        self._statusbar = None

        super(GlobalContentArea, self).__init__(**kwargs)

    def set_page(self, page):
        if self._current_page is not None:
            self.ids.ContentPanel.remove_widget(self._current_page.content)
            self._current_page.btn.active = False

        self._current_page = self._pages[page]

        self.ids.ContentPanel.add_widget(self._current_page.content)
        self._current_page.btn.active = True

    def register_content(self, name, icon, content):
        index = len(self._pages)
        page = ContentPage(index=index,
                           label=name,
                           icon=icon,
                           content=content)
        self._pages.append(page)

        cbtn = page.create_context_button(length=self.tab_height,
                                          cb=lambda inst: self.set_page(index))
        self.ids.ContextButtons.add_widget(cbtn)

        if self._current_page is None:
            self.set_page(index)

    def register_status_bar(self, statusbar):
        # Remove a status bar if it already exists
        if self._statusbar is not None:
            self.ids.StatusBar.remove_widget(self._statusbar)

        self._statusbar = statusbar

        # Register status bar if one was given
        if self._statusbar is not None:
            self.ids.StatusBar.add_widget(self._statusbar)
