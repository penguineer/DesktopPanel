from datetime import datetime

from kivy.lang import Builder

from kivy.uix.stacklayout import StackLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty, ColorProperty
from kivy.clock import Clock

Builder.load_string("""
<DateTimeDisplay>:
    orientation: 'vertical'
    spacing: -5
    size: [100, 0]
 
    Label:
        text: root.time_value
        font_size: 24
        font_name: 'assets/FiraMono-Regular.ttf'
        color: root.text_color
        size_hint_x: None

    Label:
        text: root.date_value
        font_size: 12
        font_name: 'assets/FiraMono-Regular.ttf'
        color: root.text_color
        size_hint_x: None

""")


class DateTimeDisplay(BoxLayout):
    date_value = StringProperty('    -  -  ')
    time_value = StringProperty('  :  ')
    text_color = ColorProperty([249 / 256, 176 / 256, 0 / 256, 1])

    def __init__(self, **kwargs):
        super(BoxLayout, self).__init__(**kwargs)

        self.update_datetime()
        Clock.schedule_interval(lambda dt: self.update_datetime(), 1)

    def update_datetime(self):
        datestr = str(datetime.now())

        self.date_value = datestr[0:10]
        self.time_value = f"%s:%s" % (datestr[11:13], datestr[14:16])


Builder.load_string("""
<TrayBar>:
    orientation: 'tb-rl'
    size_hint_x: None
""")


class TrayBar(StackLayout):
    def __init__(self, **kwargs):
        super(StackLayout, self).__init__(**kwargs)

    def register_widget(self, widget):
        widget.size_hint = (None, 1)
        widget.size[1] = 0
        self.add_widget(widget)
        self.do_layout()

    def remove_widget(self, widget):
        pass


Builder.load_string("""
<StatusBar>:
    orientation: 'horizontal'

    DateTimeDisplay:
        size_hint_x: None
        
    Label:
        # This is a placeholder to stretch out the status bar
        
    TrayBar:
        size_hint_x: None
        id: tray_bar
""")


class StatusBar(BoxLayout):
    def __init__(self, **kwargs):
        super(BoxLayout, self).__init__(**kwargs)

    @property
    def tray_bar(self):
        return self.ids.tray_bar
