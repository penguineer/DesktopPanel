""" Module for temperature display """

from kivy.lang import Builder
from kivy.properties import StringProperty, NumericProperty, ColorProperty, ObjectProperty, ListProperty, DictProperty
from kivy.uix.relativelayout import RelativeLayout

import mqtt

Builder.load_string("""
<TemperaturePanel>:
    size: 0, 76
    size_hint: None, None
    
    BoxLayout:
        orientation: 'horizontal'
        spacing: 1
        id: main_layout
""")


class TemperaturePanel(RelativeLayout):
    mqttc = ObjectProperty(None)
    conf = ListProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.bind(conf=self._on_conf)

    def _on_conf(self, _instance, conf: list) -> None:
        layout = self.ids.main_layout
        layout.clear_widgets()

        if not conf:
            return

        for t in conf:
            view = TemperatureView()
            view.conf = t
            self.bind(mqttc=view.setter('mqttc'))
            self.property('mqttc').dispatch(self)
            layout.add_widget(view)

        self.size = [len(conf) * 35, 76]


Builder.load_string("""
<TemperatureView>:    
    BoxLayout:
        orientation: 'vertical'
        size: 40, 76
        size_hint: None, None

        Label:
            text_size: root.width, None    
            size: self.texture_size
            size_hint: None, None
            #text: root.label
            text: root.conf.label if root.conf else '--'
            font_size: 10
            halign: 'center'
            color: root.label_color

        Label:
            size: root.width, 64
            size_hint: None, None
            canvas:
                # Background
                Color:
                    rgba: root.COLOR_GREY
                Ellipse: 
                    pos: self.center_x-13, -5
                    size: 26, 26
                Color:
                    rgba: root.COLOR_BLACK
                Ellipse: 
                    pos: self.center_x-12, -4
                    size: 24, 24                    
                Color:
                    rgba: root.COLOR_GREY
                Rectangle:
                    pos: self.center_x-6, 19
                    size: 12, 56
            
                # Level 1
                Color:
                    rgba: root.COLOR_BLACK if root.level < 1 else root.COLOR_GREEN
                Rectangle:
                    pos: self.center_x-5, 20
                    size: 10, 10    
                # Level 2
                Color:
                    rgba: root.COLOR_BLACK if root.level < 2 else root.COLOR_GREEN
                Rectangle:
                    pos: self.center_x-5, 31
                    size: 10, 10    
                # Level 3
                Color:
                    rgba: root.COLOR_BLACK if root.level < 3 else root.COLOR_GREEN
                Rectangle:
                    pos: self.center_x-5, 42
                    size: 10, 10    
                # Level 4
                Color:
                    rgba: root.COLOR_BLACK if root.level < 4 else root.COLOR_YELLOW
                Rectangle:
                    pos: self.center_x-5, 53
                    size: 10, 10    
                # Level 5
                Color:
                    rgba: root.COLOR_BLACK if root.level < 5 else root.COLOR_RED
                Rectangle:
                    pos: self.center_x-5, 64
                    size: 10, 10    

        Label:
            size: 40, 14
            size_hint: None, None
            text: root.temp
            font_size: 12   
            text_size: root.width, None    
            size: self.texture_size
            halign: 'center'
            color: root.temp_color

""")


class TemperatureView(RelativeLayout):
    COLOR_BLACK = [0, 0, 0, 1]
    COLOR_WHITE = [1, 1, 1, 1]
    COLOR_GREY = [77 / 256, 77 / 256, 76 / 256, 1]
    COLOR_GREEN = [0 / 256, 163 / 256, 86 / 256, 1]
    COLOR_YELLOW = [249 / 256, 176 / 256, 0 / 256, 1]
    COLOR_RED = [228 / 256, 5 / 256, 41 / 256, 1]

    temp = StringProperty("--°")
    level = NumericProperty(0)
    label_color = ColorProperty(COLOR_GREY)
    temp_color = ColorProperty(COLOR_GREY)

    mqttc = ObjectProperty(None)
    conf = DictProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.bind(conf=self._on_conf)
        self.bind(mqttc=self._on_mqttc)

    def _on_conf(self, _instance, _conf: list) -> None:
        self._update_mqtt()

    def _on_mqttc(self, _instance, _mqttc) -> None:
        self._update_mqtt()

    def _update_mqtt(self):
        if not self.conf or not self.mqttc:
            return

        topic = self.conf.get("topic", None)
        mqtt.add_topic_callback(self.mqttc, topic, self._mqtt_callback)

    def _mqtt_callback(self, _client, _userdata, message):
        payload = message.payload.decode("utf-8")
        try:
            temp_f = float(payload)

            self.label_color = TemperatureView.COLOR_WHITE
            self.temp_color = TemperatureView.COLOR_GREY
            self.temp = f"%d°" % round(temp_f)

            self._calculate_level(temp_f)

        except ValueError as e:
            print(e)
            self.temp = "EE"
            self.label_color = TemperatureView.COLOR_RED
            self.temp_color = TemperatureView.COLOR_RED

    def _calculate_level(self, temp_f):
        # Any ValueError from float conversions will be caught by _mqtt_callback

        # Level 5 if past alarm temperature
        alarm_s = self.conf.get("alarm", None)
        if alarm_s:
            alarm = float(alarm_s)
            if temp_f >= alarm:
                self.level = 5
                self.label_color = TemperatureView.COLOR_RED
                self.temp_color = TemperatureView.COLOR_RED

                return

        # Level 4 if past warn temperature
        warn_s = self.conf.get("warn", None)
        if warn_s:
            warn = float(warn_s)
            if temp_f >= warn:
                self.level = 4
                self.temp_color = TemperatureView.COLOR_YELLOW

                return

        # everything else depends on the temperature limits
        min_s = self.conf.get("min", None)

        if min_s and warn_s:
            t_min = float(min_s)
            t_max = float(warn_s)

            temp_f = 42
            # Distribute the rest over the levels 0 to 3
            # Note that there is int-like cut-off instead of rounding!
            self.level = (temp_f - t_min) / (t_max - t_min) * 4
            self.temp_color = TemperatureView.COLOR_GREEN
