""" Module for the DateTimeDisplay widget """

from datetime import datetime

from kivy.lang import Builder

from kivy.uix.relativelayout import RelativeLayout
from kivy.properties import StringProperty, ColorProperty
from kivy.clock import Clock

Builder.load_string("""
<DateTimeDisplay>:
    size: [120, 0]
    BoxLayout:
        orientation: 'horizontal'
        spacing: -70

        BoxLayout:
            orientation: 'vertical'
            padding: 6

            Label:
                size_hint: None, None
                size: 24, 36
                canvas.before:
                    Color: 
                        rgb: root.text_color
                
                    Rectangle:
                        pos: self.pos
                        size: self.size
                        source: 'assets/calendar.png'
                color: root.text_color
                font_size: 16
                bold: True
                text_size: [None, 28]
                text: root.week_value

            Widget:

        BoxLayout:
            orientation: 'vertical'
            spacing: -5

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


class DateTimeDisplay(RelativeLayout):
    date_value = StringProperty('    -  -  ')
    time_value = StringProperty('  :  ')
    week_value = StringProperty('00')
    text_color = ColorProperty([249 / 256, 176 / 256, 0 / 256, 1])

    def __init__(self, **kwargs):
        super(RelativeLayout, self).__init__(**kwargs)

        self.update_datetime()
        Clock.schedule_interval(lambda dt: self.update_datetime(), 1)

    def update_datetime(self):
        now = datetime.now()

        datestr = str(now)
        self.date_value = datestr[0:10]
        self.time_value = f"%s:%s" % (datestr[11:13], datestr[14:16])

        cal = datetime.now().isocalendar()
        self.week_value = str(cal.week)
