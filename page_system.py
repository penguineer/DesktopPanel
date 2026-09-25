""" Module for page System """

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import ObjectProperty

import globalcontent
from operational_event_controller import OperationalEventController
from operational_events import SyslogEvent

Builder.load_string("""
#:import TemperaturePanel temperature.TemperaturePanel
#:import PowerWidget power.PowerWidget
#:import PowerHistoryGraph power.PowerHistoryGraph
#:import OperationalEventPanel operational_event_panel.OperationalEventPanel

<SystemPage>:
    label: 'system'
    icon: 'assets/icon_system.png'

    BoxLayout:
        orientation: 'horizontal'
        spacing: 10
        padding: [0, 0, 10, 10]

        OperationalEventPanel:
            id: operational_event_panel
            size_hint_x: 0.5
            store: root.operational_store

        BoxLayout:
            orientation: 'vertical'
            size_hint_x: 0.5  # complement of syslog panel width above
            padding: [0, 12, 10, 0]
            spacing: 10

            # Power row: history graph on the left, live reading on the right
            BoxLayout:
                orientation: 'horizontal'
                spacing: 10
                size_hint_x: 1
                size_hint_y: None
                height: 32

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
    operational_store = ObjectProperty(None, allownone=True)

    def __init__(self, **kwargs):
        self._operational_events = OperationalEventController(
            on_new_events=self._schedule_operational_events,
            on_failure=self._schedule_operational_failure,
        )
        super().__init__(**kwargs)
        self.operational_store = self._operational_events.store

    def on_conf(self, _instance, conf):
        operational_conf = (conf or {}).get("operational_events")
        self._operational_events.update_config(operational_conf)

    def _schedule_operational_events(self, events):
        Clock.schedule_once(
            lambda _dt, captured=list(events): self._on_operational_events(captured)
        )

    def _schedule_operational_failure(self, state, message):
        Clock.schedule_once(
            lambda _dt, source_state=state, text=message:
                self._on_operational_failure(source_state, text)
        )

    def _on_operational_events(self, events):
        if self.active:
            return

        level = "None"
        for event in events:
            if not isinstance(event, SyslogEvent):
                continue
            if event.severity in ("critical", "crit", "alert", "emergency", "emerg"):
                level = "Critical"
                break
            if event.severity in ("error", "err"):
                level = "Warning"
            elif level == "None":
                level = "Info"

        rank = {"None": 0, "Info": 1, "Warning": 2, "Critical": 3, "Alert": 4}
        if rank[level] > rank[self.notification]:
            self.notification = level

    def _on_operational_failure(self, _state, _message):
        if not self.active and self.notification in ("None", "Info"):
            self.notification = "Warning"

    def teardown(self):
        self._operational_events.teardown()

    def on_active(self, _instance, active):
        super().on_active(_instance, active)
        if active:
            self.notification = "None"
