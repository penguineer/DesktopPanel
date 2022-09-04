""" Module for page System """

from kivy.lang import Builder

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
            conf: root.conf.get("temperatures", {}) if root.conf else {}
            mqttc: root.mqttc
""")


class SystemPage(globalcontent.ContentPage):
    pass
