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
                    id: ContentPanel
                    size: [300, root.height - root.status_height - 4]
                    size_hint_y: None
                    anchor_x: 'left'
                    anchor_y: 'top'
                    
""")


class GlobalContentArea(AnchorLayout):
    """Base window for the application, hosts context buttons, status bar and content area.

    Wildly influenced by and copied from Kivy's TabbedPanel!
    Might be replaced by an adapted TabbedPanel later, right now it seems to be easier to take
    the things we need.
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

        super(GlobalContentArea, self).__init__(**kwargs)

#        self.ids.StatusBar.add_widget(GlobalContentPanel2())
#        self.ids.ContentPanel.add_widget(GlobalContentPanel3())

    def register_content(self, name, icon, content):
        self.ids.ContextButtons.add_widget(Button(text=name, size=(100, 100), size_hint_y=None))
