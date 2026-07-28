"""Test old page_system (without PowerHistoryGraph) to confirm it doesn't crash"""
import traceback
from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.clock import Clock
from kivy.lang import Builder

# Simulate old page_system layout (without PowerHistoryGraph)
Builder.load_string("""
#:import TemperaturePanel temperature.TemperaturePanel
#:import PowerWidget power.PowerWidget
#:import SyslogMessagePanel syslog_messages.SyslogMessagePanel

<OldSystemPage>:
    label: 'system'
    icon: 'assets/icon_system.png'

    BoxLayout:
        orientation: 'horizontal'
        spacing: 10
        padding: [0, 0, 10, 10]

        SyslogMessagePanel:
            id: syslog_panel
            size_hint_x: 0.5
            amqp_widget: root.amqp_widget
            amqp_queue: ''
            min_priority: 'error'
            acknowledge_after: 3600
            max_entries: 50
            message_callback: root.on_syslog_message

        AnchorLayout:
            anchor_x: 'right'
            anchor_y: 'bottom'
            size_hint_x: 0.5
            padding: [0, 0, 10, 0]

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

import globalcontent
from kivy.properties import ObjectProperty, DictProperty

class OldSystemPage(globalcontent.ContentPage):
    amqp_widget = ObjectProperty(None, allownone=True)
    conf = DictProperty(None, allownone=True)
    
    def on_syslog_message(self, msg):
        pass
    
    def on_active(self, _instance, active):
        super().on_active(_instance, active)
        if active:
            self.notification = "None"

class TestApp(App):
    def build(self):
        sp = OldSystemPage()
        sp.conf_lambda = lambda conf: conf.get("system", dict())
        
        ca = globalcontent.GlobalContentArea()
        ca.size = (800, 480)
        
        def run(dt):
            try:
                ca.register_content(sp)
                print("register_content OK - system page should be shown")
            except Exception as e:
                print(f"ERROR: {type(e).__name__}: {e}")
                traceback.print_exc()
        
        Clock.schedule_once(run, 0.1)
        Clock.schedule_once(lambda dt: self.stop(), 2)
        return ca

TestApp().run()
