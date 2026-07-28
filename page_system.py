""" Module for page System """

from kivy.lang import Builder
from kivy.properties import ObjectProperty

import globalcontent

Builder.load_string("""
#:import TemperaturePanel temperature.TemperaturePanel
#:import PowerWidget power.PowerWidget
#:import PowerHistoryGraph power.PowerHistoryGraph
#:import SyslogMessagePanel syslog_messages.SyslogMessagePanel

<SystemPage>:
    label: 'system'
    icon: 'assets/icon_system.png'

    BoxLayout:
        orientation: 'horizontal'
        spacing: 10
        padding: [0, 0, 10, 10]

        SyslogMessagePanel:
            id: syslog_panel
            size_hint_x: 0.5  # syslog panel width fraction; adjust here to resize
            amqp_widget: root.amqp_widget
            amqp_queue: root.conf.get('syslog_channel', '') if root.conf else ''
            min_priority: root.conf.get('syslog_min_priority', 'error') if root.conf else 'error'
            acknowledge_after: root.conf.get('syslog_acknowledge_after', 3600) if root.conf else 3600
            max_entries: root.conf.get('syslog_max_entries', 50) if root.conf else 50
            message_callback: root.on_syslog_message

        AnchorLayout:
            anchor_x: 'right'
            anchor_y: 'bottom'
            size_hint_x: 0.5  # complement of syslog panel width above
            padding: [0, 0, 10, 0]

            BoxLayout:
                orientation: 'vertical'
                spacing: 10
                size_hint_x: 1
                size_hint_y: None
                height: 40 + 10 + temperatures.height

                # Power row: history graph on the left, live reading on the right
                BoxLayout:
                    orientation: 'horizontal'
                    spacing: 10
                    size_hint_x: 1
                    size_hint_y: None
                    height: 40

                    PowerHistoryGraph:
                        conf: root.conf.get("power", {}).get("graph", {}) if root.conf else {}
                        influxdb_widget: root.influxdb_widget

                    PowerWidget:
                        id: power
                        size_hint_x: None
                        width: max(temperatures.width, 110)
                        conf: root.conf.get("power", {}) if root.conf else {}
                        mqttc: root.mqttc

                # Temperature panel – right-aligned below the power row
                AnchorLayout:
                    anchor_x: 'right'
                    size_hint_x: 1
                    size_hint_y: None
                    height: temperatures.height

                    TemperaturePanel:
                        id: temperatures
                        conf: root.conf.get("temperatures", {}) if root.conf else {}
                        mqttc: root.mqttc
""")


class SystemPage(globalcontent.ContentPage):
    amqp_widget = ObjectProperty(None, allownone=True)
    influxdb_widget = ObjectProperty(None, allownone=True)

    def on_syslog_message(self, msg):
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
