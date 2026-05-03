from datetime import datetime

from kivy.lang import Builder

from kivy.uix.relativelayout import RelativeLayout
from kivy.properties import StringProperty, ColorProperty, ObjectProperty, DictProperty
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


Builder.load_string("""
<TrayIcon>:
    size_hint: None, None
    size: 32, 48

    Image:
        size_hint: None, None
        size: 32, 32
        pos: 0, 16
        source: root.icon
        #source: 'assets/mqtt_icon_64px.png'
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


Builder.load_string("""
<StatusBar>:
    BoxLayout:
        orientation: 'horizontal'
        size_hint_y: 1
        spacing: 10
        padding: [10, 0]

        DateTimeDisplay:
            size_hint_x: None

        StackLayout:
            id: status_items
            orientation: 'lr-tb'
            size_hint: None, 1
            width: self.minimum_width
            spacing: 10

        Widget:
            # This is a placeholder to stretch out the status bar
            size_hint_x: 1

        StackLayout:
            id: right_panel
            orientation: 'tb-rl'
            size_hint: None, 1
            width: self.minimum_width
            spacing: 5
""")


class StatusBar(RelativeLayout):
    conf = DictProperty(None)
    mqttc = ObjectProperty(None)
    screensaver = ObjectProperty(None, allownone=True)

    def __init__(self, **kwargs):
        self._status_items = []

        super(RelativeLayout, self).__init__(**kwargs)

        self.bind(conf=self._on_conf)
        self.bind(mqttc=self._on_mqttc)
        self.bind(screensaver=self._on_screensaver)

    def register_tray_item(self, widget):
        """Register a widget on the right side of the status bar (tray area).

        Widgets are stacked from right to left as they are added.
        """
        widget.size_hint = (None, 1)
        widget.size[1] = 0
        self.ids.right_panel.add_widget(widget)

    def register_status_item(self, widget, conf_lambda=None):
        """Register a widget in the dynamic status bar item area.

        The widget is added to the left portion of the status bar (after the
        clock, before the spacer).  If *conf_lambda* is provided it is called
        with the current conf dict whenever conf changes; the result is assigned
        to ``widget.conf``.  The widget also receives the current ``mqttc`` and
        ``screensaver`` values if it exposes those properties, and will be kept
        up to date as those values change.
        """
        widget.size_hint = (None, 1)
        self._status_items.append({'widget': widget, 'conf_lambda': conf_lambda})
        self.ids.status_items.add_widget(widget)

        if conf_lambda is not None and hasattr(widget, 'conf'):
            widget.conf = conf_lambda(self.conf) if self.conf else None
        if hasattr(widget, 'mqttc'):
            widget.mqttc = self.mqttc
        if hasattr(widget, 'screensaver'):
            widget.screensaver = self.screensaver

    def _on_conf(self, _instance, conf: dict) -> None:
        for item in self._status_items:
            conf_lambda = item['conf_lambda']
            widget = item['widget']
            if conf_lambda is not None and hasattr(widget, 'conf'):
                widget.conf = conf_lambda(conf) if conf else None

    def _on_mqttc(self, _instance, mqttc) -> None:
        for item in self._status_items:
            widget = item['widget']
            if hasattr(widget, 'mqttc'):
                widget.mqttc = mqttc

    def _on_screensaver(self, _instance, screensaver) -> None:
        for item in self._status_items:
            widget = item['widget']
            if hasattr(widget, 'screensaver'):
                widget.screensaver = screensaver
