""" Module for page System """

from kivy.clock import Clock
from kivy.lang import Builder

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
    def on_syslog_message(self, msg):
        """Receive a new syslog message from the AMQP connector.

        This method is safe to call from any thread; UI updates are
        scheduled on the Kivy main thread.
        """
        Clock.schedule_once(lambda dt: self._handle_syslog(msg))

    def _handle_syslog(self, msg):
        self.ids.syslog_panel.add_message(msg)

        if not self.active:
            if msg.is_critical():
                self.notification = "Critical"
            elif self.notification == "None":
                # "None" is the OptionProperty default defined in ContentPage;
                # only upgrade to Warning if no higher-priority notification is active.
                self.notification = "Warning"

    def on_active(self, _instance, active):
        # ContentPage.on_active updates the tab button's active state;
        # call super() to preserve that behaviour before clearing the notification.
        super().on_active(_instance, active)
        if active:
            self.notification = "None"
