""" Module for temperature display """
from kivy import Logger
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import StringProperty, NumericProperty, ColorProperty, ObjectProperty, ListProperty, DictProperty
from kivy.uix.relativelayout import RelativeLayout

import time


class Colors:
    # Base color definitions
    COLOR_BLACK = [0, 0, 0, 1]
    COLOR_WHITE = [1, 1, 1, 1]
    COLOR_GREY = [77 / 256, 77 / 256, 76 / 256, 1]
    COLOR_GREEN = [0 / 256, 163 / 256, 86 / 256, 1]
    COLOR_YELLOW = [249 / 256, 176 / 256, 0 / 256, 1]
    COLOR_RED = [228 / 256, 5 / 256, 41 / 256, 1]


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
#:import Colors temperature.Colors

<TemperatureView>:    
    BoxLayout:
        orientation: 'vertical'
        size: 40, 95
        size_hint: None, None

        Label:
            text_size: root.width, None    
            #size: self.texture_size
            size: 40, 12
            size_hint: None, None
            #text: root.label
            text: root.conf.label if root.conf else '--'
            font_size: 10
            halign: 'center'
            color: Colors.COLOR_RED if root.value_error else \
                   Colors.COLOR_GREY if root._temp is None else \
                   Colors.COLOR_WHITE

        ThermometerWidget:
            limit_min: root.conf.get("min", 0) if root.conf else 0
            limit_warn: root.conf.get("warn", 0) if root.conf else 0
            limit_alarm: root.conf.get("alarm", 0) if root.conf else 0
            temperature: root._temp
""")


class TemperatureView(RelativeLayout):
    MEASUREMENT_TIMEOUT = 20  # [s]

    mqttc = ObjectProperty(None)
    conf = DictProperty(None)
    value_error = ObjectProperty(None, allownone=True)

    _label_color = ColorProperty(Colors.COLOR_GREY)

    _temp = NumericProperty(None, allownone=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # The time of last measurement
        self.measure_instant = None
        # Schedule the check
        # (Scheduling does not have to be super precise, so we chose a rather long interval.)
        Clock.schedule_interval(lambda dt: self._check_measurement_age(), 5)

    def on_conf(self, _instance, _conf: list) -> None:
        self._update_mqtt()

    def on_mqttc(self, _instance, _mqttc) -> None:
        self._update_mqtt()

    def _update_mqtt(self):
        if not self.conf or not self.mqttc:
            return

        topic = self.conf.get("topic", None)
        self.mqttc.subscribe(topic, self._mqtt_callback)

    def _mqtt_callback(self, _client, _userdata, message):
        payload = message.payload.decode("utf-8")
        Clock.schedule_once(lambda dt: self._update_temperature(payload))

    def _update_temperature(self, payload):
        # We received a measurement
        self.measure_instant = time.time()

        try:
            self.value_error = None
            self._temp = float(payload)
        except ValueError as e:
            Logger.error(e)
            self.value_error = e
            self._temp = None

    def _check_measurement_age(self):
        age = time.time() - self.measure_instant \
            if self.measure_instant is not None \
            else TemperatureView.MEASUREMENT_TIMEOUT + 1

        if age > TemperatureView.MEASUREMENT_TIMEOUT:
            self._temp = None


Builder.load_string("""
#:import Colors temperature.Colors

<ThermometerWidget>:    
    BoxLayout:
        orientation: 'vertical'
        size: 40, 85
        size_hint: None, None

        Label:
            size_hint: 1, 1
            canvas:
                # Background
                Color:
                    rgba: Colors.COLOR_GREY
                Ellipse: 
                    pos: self.center_x-13, 0
                    size: 26, 26
                Color:
                    rgba: Colors.COLOR_BLACK
                Ellipse: 
                    pos: self.center_x-12, 1
                    size: 24, 24                    
                Color:
                    rgba: Colors.COLOR_GREY
                Rectangle:
                    pos: self.center_x-6, 24
                    size: 12, 56

                # Level 1
                Color:
                    rgba: Colors.COLOR_GREEN if root._level and root._level >= 1 else Colors.COLOR_BLACK
                Rectangle:
                    pos: self.center_x-5, 25
                    size: 10, 10    
                # Level 2
                Color:
                    rgba: Colors.COLOR_GREEN if root._level and root._level >= 2 else Colors.COLOR_BLACK
                Rectangle:
                    pos: self.center_x-5, 36
                    size: 10, 10    
                # Level 3
                Color:
                    rgba: Colors.COLOR_GREEN if root._level and root._level >= 3 else Colors.COLOR_BLACK
                Rectangle:
                    pos: self.center_x-5, 47
                    size: 10, 10    
                # Level 4
                Color:
                    rgba: Colors.COLOR_YELLOW if root._level and root._level >= 4 else Colors.COLOR_BLACK
                Rectangle:
                    pos: self.center_x-5, 58
                    size: 10, 10    
                # Level 5
                Color:
                    rgba: Colors.COLOR_RED if root._level and root._level >= 5 else Colors.COLOR_BLACK
                Rectangle:
                    pos: self.center_x-5, 69
                    size: 10, 10    

        Label:
            pos: 10, 50
            size: 40, 26  # The height moves the text up without needing to define a padding label
            size_hint: None, None
            text: root._temp_label
            font_size: 12   
            text_size: root.width, None    
            halign: 'center'
            color: root._temp_color
""")


class ThermometerWidget(RelativeLayout):
    limit_min = NumericProperty(0)
    limit_warn = NumericProperty(0)
    limit_alarm = NumericProperty(0)

    temperature = NumericProperty(None, allownone=True)

    _temp_label = StringProperty("--°")
    _level = NumericProperty(None, allownone=True)
    _temp_color = ColorProperty(Colors.COLOR_GREY)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.bind(on_limit_min=lambda _s, _i, _v: self._populate_level())
        self.bind(on_limit_warn=lambda _s, _i, _v: self._populate_level())
        self.bind(on_limit_alarm=lambda _s, _i, _v: self._populate_level())

    def on_temperature(self, _instance, _value):
        self._populate_label()
        self._populate_level()

    def _populate_label(self):
        self._temp_label = f"%d°" % round(self.temperature) if self.temperature is not None else "--°"

    def _populate_level(self):
        # Level 0 if there is no temperature
        if self.temperature is None:
            self._level = None

            return

        # Level 5 if past alarm temperature
        if self.temperature >= self.limit_alarm:
            self._level = 5

            return

        # Level 4 if past warn temperature
        if self.temperature >= self.limit_warn:
            self._level = 4

            return

        # Distribute the rest over the levels 0 to 3
        # Note that there is int-like cut-off instead of rounding!
        t_range = max(0, self.limit_warn - self.limit_min)
        level = (self.temperature - self.limit_min) / t_range * 4 if t_range else 0
        self._level = max(0, level)  # avoid negative values for the level

    def on__level(self, _instance, _value):
        if self._level is None:
            self._temp_color = Colors.COLOR_GREY
        elif self._level == 5:
            self._temp_color = Colors.COLOR_RED
        elif self._level == 4:
            self._temp_color = Colors.COLOR_YELLOW
        else:
            self._temp_color = Colors.COLOR_GREEN
