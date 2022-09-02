""" Module for page System """

from kivy.lang import Builder
from kivy.properties import ObjectProperty, DictProperty

import globalcontent

Builder.load_string("""
#:import TemperaturePanel temperature.TemperaturePanel

<SystemPage>:
    label: 'system'
    icon: 'assets/icon_system.png'
    
    Label:
        text: 'SYSTEM'
   
    AnchorLayout:
        size_hint: 1, 1
        anchor_x: 'right'
        anchor_y: 'bottom'
        padding: 10
    
        TemperaturePanel:
            id: temperatures
            mqttc: root.mqttc
""")


class SystemPage(globalcontent.ContentPage):
    mqttc = ObjectProperty(None)
    conf = DictProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.bind(conf=self._on_conf)

    def _on_conf(self, _instance, conf: dict) -> None:
        if conf:
            self.ids.temperatures.conf = conf.get("temperatures", None)
        else:
            self.ids.temperatures.conf = None

