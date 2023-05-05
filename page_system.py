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
        padding: 10
    
        BoxLayout:
            size: 95, 160
            orientation: 'vertical'
            spacing: 10
            size_hint: None, None
    
            PowerWidget:
                conf: root.conf.get("power", {}) if root.conf else {}
                mqttc: root.mqttc
    
            TemperaturePanel:
                id: temperatures
                conf: root.conf.get("temperatures", {}) if root.conf else {}
                mqttc: root.mqttc
""")


class SystemPage(globalcontent.ContentPage):
    pass
