""" Module for power display """
from kivy import Logger
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import ObjectProperty, DictProperty, NumericProperty
from kivy.uix.relativelayout import RelativeLayout

class Colors:
    # Base color definitions
    COLOR_BLACK = [0, 0, 0, 1]
    COLOR_WHITE = [1, 1, 1, 1]
    COLOR_GREY = [77 / 256, 77 / 256, 76 / 256, 1]
    COLOR_GREEN = [0 / 256, 163 / 256, 86 / 256, 1]
    COLOR_YELLOW = [249 / 256, 176 / 256, 0 / 256, 1]
    COLOR_RED = [228 / 256, 5 / 256, 41 / 256, 1]

Builder.load_string("""
#:import Colors power.Colors

<PowerWidget>:
    size_hint: 1, 1

    Label:
        halign: 'center'
        text: '---' if root.power is None else f"%d"%root.power
        text_size: root.width, None    
        font_size: 32
        size_hint_x: None
        font_name: 'assets/FiraMono-Regular.ttf'
        color: Colors.COLOR_RED if root.value_error else \
               Colors.COLOR_GREY if root.power is None else \
               Colors.COLOR_WHITE

    Label:
        halign: 'right'
        text: 'W'
        text_size: root.width, None    
        font_size: 16
        size_hint_x: None
        font_name: 'assets/FiraMono-Regular.ttf'
        color: Colors.COLOR_RED if root.value_error else \
               Colors.COLOR_GREY if root.power is None else \
               Colors.COLOR_WHITE
""")

class PowerWidget(RelativeLayout):
    mqttc = ObjectProperty(None)
    conf = DictProperty()

    power = NumericProperty(None, allownone=True)
    value_error = ObjectProperty(None, allownone=True)


    def __init__(self, **kwargs):
        super().__init__(**kwargs)

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
        Clock.schedule_once(lambda dt: self._update_power(payload))

    def _update_power(self, payload):
        try:
            self.value_error = None
            self.power = float(payload)
        except ValueError as e:
            Logger.error(e)
            self.value_error = e
            self.power = None
