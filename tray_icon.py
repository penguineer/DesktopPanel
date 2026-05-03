""" Module for the TrayIcon widget """

from kivy.lang import Builder

from kivy.uix.relativelayout import RelativeLayout
from kivy.properties import StringProperty, ColorProperty, ObjectProperty

Builder.load_string("""
<TrayIcon>:
    size_hint: None, None
    size: 32, 48

    Image:
        size_hint: None, None
        size: 32, 32
        pos: 0, 16
        source: root.icon
        keep_ratio: True
        color: root.icon_color

    Label:
        size_hint: None, None
        size: 32, 16
        pos: 0, 0
        text: root.label if root.label else ''
        font_size: 10        
        color: root.icon_color
""")


class TrayIcon(RelativeLayout):
    label = StringProperty(None, allownone=True)
    icon = StringProperty(None)
    icon_color = ColorProperty([77 / 256, 77 / 256, 76 / 256, 1])

    page_callback = ObjectProperty(None, allownone=True)

    def __init__(self, label=None, icon=None, **kwargs):
        self.label = label
        self.icon = icon

        super(RelativeLayout, self).__init__(**kwargs)

    def on_touch_down(self, touch):
        if self.page_callback and callable(self.page_callback) and self.collide_point(*touch.pos):
            self.page_callback()
            return True
        return super(TrayIcon, self).on_touch_down(touch)
