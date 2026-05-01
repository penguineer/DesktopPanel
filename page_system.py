""" Module for page System """

from kivy.lang import Builder
from kivy.properties import ObjectProperty

import globalcontent

Builder.load_string("""
#:import TemperaturePanel temperature.TemperaturePanel
#:import PowerWidget power.PowerWidget
#:import SyslogMessagePanel syslog_messages.SyslogMessagePanel

<SystemPage>:
    label: 'system'
    icon: 'assets/icon_system.png'

    BoxLayout:
        orientation: 'horizontal'
        spacing: 10
        padding: [10, 10]

        SyslogMessagePanel:
            id: syslog_panel
            size_hint_x: 0.5  # syslog panel width fraction; adjust here to resize
            amqp_widget: root.amqp_widget
            amqp_queue: root.conf.get('syslog_channel', '') if root.conf else ''
            min_priority: root.conf.get('syslog_min_priority', 'error') if root.conf else 'error'
            acknowledge_after: root.conf.get('syslog_acknowledge_after', 3600) if root.conf else 3600
            message_callback: root._on_syslog_message

        AnchorLayout:
            anchor_x: 'right'
            anchor_y: 'bottom'
            size_hint_x: 0.5  # complement of syslog panel width above
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


class SystemPage(globalcontent.ContentPage):
    amqp_widget = ObjectProperty(None, allownone=True)

    def _on_syslog_message(self, msg):
        """Update the tab notification badge when a new syslog message arrives."""
        if not self.active:
            if msg.is_critical():
                self.notification = "Critical"
            elif msg.priority in ('error', 'err') and self.notification == "None":
                self.notification = "Warning"

    def on_active(self, _instance, active):
        # ContentPage.on_active updates the tab button's active state;
        # call super() to preserve that behaviour before clearing the notification.
        super().on_active(_instance, active)
        if active:
            self.notification = "None"
