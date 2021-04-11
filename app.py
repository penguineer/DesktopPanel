#!/usr/bin/python3

# Desktop Panel - Desktop control panel
# with Raspberry Pi and RPi Touch Screen

# Author: Stefan Haun <tux@netz39.de>
import asyncio
import signal
import sys

import json

import amqp
import mqtt
import globalcontent
from page_gtd import GtdPage
from page_home import HomePage
from page_system import SystemPage
from statusbar import StatusBar, TrayIcon
from presence_ui import PresenceDlg, Presence, PresencePingTechEmitter
from presence_conn import PresenceSvcCfg, PingTechPresenceReceiver, PingTechPresenceUpdater, MqttPresenceUpdater

from kivy import Logger
from kivy.config import Config
from kivy.app import App
from kivy.core.window import Window

from kivy.clock import Clock

from kivy.properties import ObjectProperty, StringProperty, ListProperty

running = True


def sigint_handler(_signal, _frame):
    global running

    if running:
        Logger.info("SIGINT: SIGINT received. Stopping the queue.")
        running = False
    else:
        Logger.warn("SIGINT: Receiving SIGINT the second time. Exit.")
        sys.exit(0)


class TabbedPanelApp(App):
    mqtt_icon = ObjectProperty(None)
    amqp_icon = ObjectProperty(None)

    config = ObjectProperty(None)
    mqttc = ObjectProperty(None)
    presence_receiver = ObjectProperty(None)
    presence_emitter = ObjectProperty(None)
    mqtt_presence_updater = ObjectProperty(None)

    active_presence = StringProperty(None)
    requested_presence = StringProperty(None)

    handle_self = StringProperty()
    handle_others = ListProperty()
    presence_list = ListProperty()

    def __init__(self, config, mqttc, **kwargs):
        super().__init__(**kwargs)

        self._config = config
        self.mqttc = mqttc

        self.ca = None
        self.pr_sel = None

        self.bind(active_presence=self._on_active_presence)
        self.property('active_presence').dispatch(self)

        self.bind(presence_list=self._on_presence_list)
        self.property('presence_list').dispatch(self)

        self.bind(requested_presence=self._on_presence_request)

        self._load_presence_config()

        mqtt_cfg = self._config.get('mqtt', None)
        if self.mqttc and mqtt_cfg:
            presence_topic = mqtt_cfg.get('presence-topic', None)
            if presence_topic:
                self.mqtt_presence_updater = MqttPresenceUpdater(self.mqttc, presence_topic)

    def build(self):
        home_page = HomePage()
        system_page = SystemPage()
        gtd_page = GtdPage()
        gtd_page.mqttc = self.mqttc
        issuelist_cfg = self._config.get("issuelist", None)
        if issuelist_cfg:
            gtd_page.issue_list_path = issuelist_cfg.get("path", "issuelist.cfg")

        ca = globalcontent.GlobalContentArea()
        Clock.schedule_once(lambda dt: ca.register_content(home_page))
        Clock.schedule_once(lambda dt: ca.register_content(system_page))
        Clock.schedule_once(lambda dt: ca.register_content(gtd_page))

        sb = StatusBar()
        ca.register_status_bar(sb)
        self.bind(active_presence=sb.ids.presence.setter('active_presence'))
        self.property('active_presence').dispatch(self)
        sb.ids.presence.touch_cb = self.popup_handler

        self.mqtt_icon = TrayIcon(label='MQTT', icon="assets/mqtt_icon_64px.png")
        ca.status_bar.tray_bar.register_widget(self.mqtt_icon)

        self.amqp_icon = TrayIcon(label='AMQP', icon="assets/rabbitmq_icon_64px.png")
        ca.status_bar.tray_bar.register_widget(self.amqp_icon)

        Clock.schedule_once(lambda dt: ca.set_page(2))

        self.ca = ca
        return ca

    def select(self, index):
        Clock.schedule_once(lambda dt: self.ca.set_page(index))

    def popup_handler(self, _cmd=None, _args=None):
        Clock.schedule_once(lambda dt: self._presence_load())

        if self.pr_sel is not None and self.pr_sel.is_inactive():
            self.pr_sel = None

        if self.pr_sel is None:
            self.pr_sel = PresenceDlg()

            self.pr_sel.handle_self = self.handle_self
            self.pr_sel.handle_others = self.handle_others
            self.pr_sel.presence_list = self.presence_list

            # Don't do this bind:
            #   self.bind(active_presence=self.pr_sel.setter('active_presence'))
            # This results in dangling property binds and repeated calls of inactive widgets.

            self.pr_sel.active_presence = self.active_presence
            self.pr_sel.requested_presence = self.requested_presence
            self.pr_sel.bind(requested_presence=self.setter('requested_presence'))

            self.pr_sel.open()
        else:
            self.pr_sel.dismiss()
            self.pr_sel = None

    def _presence_load(self):
        self.presence_receiver.receive_status(self._on_presence_loaded,
                                              self._on_presence_load_failed)

    def _on_presence_loaded(self, remote_presence):
        for e in self.presence_list:
            presence = remote_presence.get(e.handle)
            if presence is not None:
                e.presence = presence.get('status', "unknown")

            if e.handle == self.handle_self:
                self.active_presence = e.presence

        self.property('presence_list').dispatch(self)

    def _on_presence_load_failed(self, error):
        Logger.error("Presence: Error while fetching presence: " + str(error))
        for e in self.presence_list:
            e.presence = "unknown"

    def _on_presence_request(self, _instance, value):
        Clock.schedule_once(lambda dt: self.pr_sel is None or self.pr_sel.dismiss(), timeout=0.25)
        Clock.schedule_once(lambda dt: setattr(self, 'active_presence', value))
        Clock.schedule_once(lambda dt: setattr(self.presence_emitter, 'requested_presence', value))

    def _on_active_presence(self, _instance, value):
        if self.presence_list is not None and len(self.presence_list):
            p = self.presence_list[0]
            p.presence = value

        if self.pr_sel is not None:
            self.pr_sel.active_presence = value

        if self.mqtt_presence_updater is not None and value:
            self.mqtt_presence_updater.update_status(value)

    def _on_presence_list(self, _instance, _value):
        if self.pr_sel is not None:
            self.pr_sel.presence_list = []
            self.pr_sel.presence_list = self.presence_list

    def _load_presence_config(self):
        if 'presence' not in self._config:
            return

        pr = self._config.get('presence', None)
        if pr is None:
            return

        self.handle_self = pr.get('self', None)
        self.handle_others = pr.get('others', [])

        pl = []

        people = pr.get('people', {})
        if people is not None:
            for p in [self.handle_self] + self.handle_others:
                person = people.get(p, None)
                if person is not None:
                    presence = Presence(handle=p,
                                        view_name=person.get('view_name', None),
                                        avatar=person.get('avatar', None))
                    pl.append(presence)

        self.presence_list = pl

        presence_svc_cfg = PresenceSvcCfg(
            svc=pr['svc'],
            handle=pr['self'],
            token=pr['token']
        )
        self.presence_receiver = PingTechPresenceReceiver(presence_svc_cfg)
        self.presence_updater = PingTechPresenceUpdater(presence_svc_cfg)
        self.presence_emitter = PresencePingTechEmitter(presence_updater=self.presence_updater)

        self._presence_load()


def command_log(cmd, args):
    Logger.info("App: Received command %s with args %s.", cmd, args)


async def main():
    signal.signal(signal.SIGINT, sigint_handler)

    Config.set('kivy', 'default_font', [
        ' FiraSans-Regular',
        './assets/FiraSans-Regular.ttf',
        './assets/FiraSans-Regular.ttf',
        './assets/FiraSans-Regular.ttf',
        './assets/FiraSans-Regular.ttf'
    ])
    Window.size = (800, 480)

    with open("desktop-panel.cfg", "r") as f:
        config = json.load(f)

    if 'mqtt' not in config:
        raise ValueError("Missing mqtt section in configuration! See template for an example.")
    mqtt_config = config.get('mqtt')
    client = mqtt.create_client(mqtt_config)

    amqp_access = amqp.AmqpAccessConfiguration.from_json_cfg(config)
    amqp_resource = amqp.AmqpResourceConfiguration.from_json_cfg(config)
    cmd_dispatch = amqp.AmqpCommandDispatch()
    amqp_conn = amqp.AmqpConnector(amqp_access_cfg=amqp_access,
                                   amqp_resource_cfg=amqp_resource,
                                   dispatch=cmd_dispatch)
    amqp_conn.setup()

    # TODO build and run app
    app = TabbedPanelApp(config, client)
    app.bind(mqtt_icon=lambda i, v: mqtt.update_tray_icon(client, v))
    app.bind(amqp_icon=lambda i, v: amqp_conn.update_tray_icon(v))

    # TODO bind command handlers
    cmd_dispatch.add_command_handler("test", command_log)
    cmd_dispatch.add_command_handler("presence popup", app.popup_handler)

    await app.async_run()

    amqp_conn.stop()
    client.loop_stop()


if __name__ == '__main__':
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
