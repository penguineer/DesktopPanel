from functools import partial

from kivy.lang import Builder

from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import ObjectProperty, StringProperty, OptionProperty, \
    ListProperty, NumericProperty, AliasProperty, BooleanProperty, \
    ColorProperty

from kivy.uix.button import Button


Builder.load_string("""
<ContextButton>:
    size_hint_y: None
""")


class ContextButton(Button):
    index = NumericProperty(0)

    def __init__(self, index=0, **kwargs):
        self.index = index

        super(Button, self).__init__(**kwargs, text=str(index))


Builder.load_string("""
<ContextButton>:
    size_hint_y: None
""")


class ContextButton(Button):
    index = NumericProperty(0)

    def __init__(self, index=0, **kwargs):
        self.index = index

        super(Button, self).__init__(**kwargs, text=str(index))


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
                    
                    PageLayout:
                        id: ContentPanel
                        border: 0
                    
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
    border_color = ColorProperty([77/256, 77/256, 76/256, 1])
    """Border color, in the format (r, g, b, a).

    :attr:`border_color` is a :class:`~kivy.properties.ColorProperty` and
    defaults to [77/256, 177/256, 76/256, 1].
    """

    _current_tab = ObjectProperty(None)

    def get_current_tab(self):
        return self._current_tab

    current_tab = AliasProperty(get_current_tab, None, bind=('_current_tab', ))
    """Links to the currently selected or active tab.

    :attr:`current_tab` is an :class:`~kivy.AliasProperty`, read-only.
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
        self._tabs = []
        self._btns = []
        self._statusbar = None

        super(GlobalContentArea, self).__init__(**kwargs)

#        self.ids.StatusBar.add_widget(GlobalContentPanel2())
#        self.ids.ContentPanel.add_widget(GlobalContentPanel3())

    def set_page(self, page):
        self.ids.ContentPanel.page = page
        self._current_tab = self._tabs[page]

    def register_content(self, name, icon, content):
        index = len(self._btns)
        cbtn = ContextButton(index=index,
                             on_press=lambda inst: self.set_page(index),
                             size=(self.tab_width, self.tab_height))
        self._btns.append(cbtn)
        self.ids.ContextButtons.add_widget(cbtn)

        self._tabs.append(content)
        self.ids.ContentPanel.add_widget(content)
        self._current_tab = content

    def register_status_bar(self, statusbar):
        # Remove a status bar if it already exists
        if self._statusbar is not None:
            self.ids.StatusBar.remove_widget(self._statusbar)

        self._statusbar = statusbar

        # Register status bar if one was given
        if self._statusbar is not None:
            self.ids.StatusBar.add_widget(self._statusbar)
