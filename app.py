#!/usr/bin/python3

# Desktop Panel - Desktop control panel
# with Raspberry Pi and RPi Touch Screen

# Author: Stefan Haun <tux@netz39.de>
import asyncio
from datetime import datetime
import signal
import sys

import json

import amqp
import mqtt
import globalcontent
from page_gtd import GtdPage
from page_home import HomePage
from page_system import SystemPage
from reloadable_json import JsonObserver
from statusbar import TrayIcon

from kivy import Logger
from kivy.config import Config
from kivy.app import App
from kivy.core.window import Window

from kivy.clock import Clock

from kivy.properties import ObjectProperty, StringProperty

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
    amqp_icon = ObjectProperty(None)

    conf_path = StringProperty()
    conf = ObjectProperty(None)
    mqttc = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.ca = None
        self.config_obs = None

        self.bind(conf_path=self._on_conf_path)
        self.bind(conf=self._on_conf)
        self.bind(mqttc=self._on_mqttc)

    def _on_conf_path(self, _instance, path: str) -> None:
        if self.config_obs:
            self.config_obs.teardown()
            self.config_obs = None

        if not path:
            return

        self.config_obs = JsonObserver("desktop-panel-config.json",
                                       update_callback=self.schedule_update_configuration,
                                       failed_callback=None)
        self.config_obs.setup()

    def _on_conf(self, _instance, conf: dict) -> None:
        if self.ca:
            self.ca.conf = conf
        if self.mqttc:
            self.mqttc.conf = conf.get("mqtt", None)

    def _on_mqttc(self, _instance, mqttc) -> None:
        if self.ca:
            self.ca.mqttc = mqttc

    def build(self):
        home_page = HomePage()
        system_page = SystemPage()
        system_page.conf_lambda = lambda conf: conf.get("system", dict())
        gtd_page = GtdPage()
        gtd_page.conf_lambda = lambda conf: conf.get("gtd", dict())

        ca = globalcontent.GlobalContentArea()
        ca.conf = self.conf
        Clock.schedule_once(lambda dt: ca.register_content(home_page))
        Clock.schedule_once(lambda dt: ca.register_content(system_page))
        Clock.schedule_once(lambda dt: ca.register_content(gtd_page))

        self.mqttc = mqtt.MqttClient()
        self.mqttc.conf = self.conf
        ca.mqttc = self.mqttc
        ca.status_bar.tray_bar.register_widget(self.mqttc)

        self.amqp_icon = TrayIcon(label='AMQP', icon="assets/rabbitmq_icon_64px.png")
        ca.status_bar.tray_bar.register_widget(self.amqp_icon)

        self.ca = ca
        return ca

    def on_stop(self):
        if self.config_obs is not None:
            self.config_obs.teardown()

    def select(self, index):
        Clock.schedule_once(lambda dt: self.ca.set_page(index))

    def popup_presence_dlg(self, _cmd, _args):
        if self.ca:
            self.ca.status_bar.ids.presence.popup_handler()

    def schedule_update_configuration(self, conf):
        Clock.schedule_once(lambda dt: self.setter('conf')(self, conf))


def command_log(cmd, args):
    Logger.info("App: Received command %s with args %s.", cmd, args)


def command_screenshot(_cmd, _args):
    name = "Screenshot {}.png".format(datetime.now())
    Logger.info("Taking a screenshot to %s", name)
    Window.screenshot(name=name)


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

    # TODO Move AMQP into widgets so that they can reload the configuration
    with open("desktop-panel-config.json", "r") as f:
        config = json.load(f)

    amqp_access = amqp.AmqpAccessConfiguration.from_json_cfg(config)
    amqp_resource = amqp.AmqpResourceConfiguration.from_json_cfg(config)
    cmd_dispatch = amqp.AmqpCommandDispatch()
    amqp_conn = amqp.AmqpConnector(amqp_access_cfg=amqp_access,
                                   amqp_resource_cfg=amqp_resource,
                                   dispatch=cmd_dispatch)
    amqp_conn.setup()

    # build and run app
    app = TabbedPanelApp()
    app.schedule_update_configuration(config)
    # Setup path for automatic reloading
    # We still need to preload the configuration until MQTT and AMQP are moved into widgets
    app.conf_path = "desktop-panel-config.json"
    app.bind(amqp_icon=lambda i, v: amqp_conn.update_tray_icon(v))

    # TODO bind command handlers
    cmd_dispatch.add_command_handler("test", command_log)
    cmd_dispatch.add_command_handler("screenshot", command_screenshot)
    cmd_dispatch.add_command_handler("presence popup", app.popup_presence_dlg)

    await app.async_run()

    amqp_conn.stop()


if __name__ == '__main__':
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
