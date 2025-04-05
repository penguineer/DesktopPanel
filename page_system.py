""" Module for page System """

from kivy.lang import Builder

import globalcontent

Builder.load_string("""
#:import TemperaturePanel temperature.TemperaturePanel
#:import PowerWidget power.PowerWidget

<SystemPage>:
    label: 'system'
    icon: 'assets/icon_system.png'
    
    Label:
        text: 'SYSTEM'
   
    AnchorLayout:
        anchor_x: 'right'
        anchor_y: 'bottom'
        padding: [0, 0, 20, 10]
    
        BoxLayout:
            orientation: 'vertical'
            spacing: 10
            size_hint: None, None
            width: temperatures.width
            height: temperatures.height + power.height + 10
    
            PowerWidget:
                id: power
                conf: root.conf.get("power", {}) if root.conf else {}
                mqttc: root.mqttc
    
            TemperaturePanel:
                id: temperatures
                conf: root.conf.get("temperatures", {}) if root.conf else {}
                mqttc: root.mqttc
""")


class SystemPage(globalcontent.ContentPage):
    pass
