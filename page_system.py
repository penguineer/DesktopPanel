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

        BoxLayout:
            orientation: 'vertical'
            size_hint_x: 0.5  # complement of syslog panel width above
            padding: [0, 10, 10, 0]
            spacing: 10

            # Power row: history graph on the left, live reading on the right
            BoxLayout:
                orientation: 'horizontal'
                spacing: 10
                size_hint_x: 1
                size_hint_y: None
                height: 50

                PowerHistoryGraph:
                    conf: root.conf.get("power", {}).get("graph", {}) if root.conf else {}
                    influxdb_widget: root.influxdb_widget

                PowerWidget:
                    id: power
                    conf: root.conf.get("power", {}) if root.conf else {}
                    mqttc: root.mqttc

            # Spacer pushes the temperature panel to the bottom of the column
            Widget:
                size_hint_y: 1

            # Temperature panel – right-aligned at the bottom of the column
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
