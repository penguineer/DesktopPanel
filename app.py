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
from statusbar import TrayIcon

from kivy import Logger
from kivy.config import Config
from kivy.app import App
from kivy.core.window import Window

from kivy.clock import Clock

from kivy.properties import ObjectProperty

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

    def __init__(self, config, mqttc, **kwargs):
        super().__init__(**kwargs)

        self._config = config
        self.mqttc = mqttc

        self.ca = None

        self.presence_tray = None

    def build(self):
        home_page = HomePage()
        system_page = SystemPage()
        system_page.conf = self._config.get("system", None)
        system_page.mqttc = self.mqttc
        gtd_page = GtdPage()
        gtd_page.conf = self._config.get("gtd", None)
        gtd_page.mqttc = self.mqttc

        ca = globalcontent.GlobalContentArea()
        ca.mqttc = self.mqttc
        ca.conf = self._config
        Clock.schedule_once(lambda dt: ca.register_content(home_page))
        Clock.schedule_once(lambda dt: ca.register_content(system_page))
        Clock.schedule_once(lambda dt: ca.register_content(gtd_page))

        self.presence_tray = ca.status_bar.ids.presence

        self.mqtt_icon = TrayIcon(label='MQTT', icon="assets/mqtt_icon_64px.png")
        ca.status_bar.tray_bar.register_widget(self.mqtt_icon)

        self.amqp_icon = TrayIcon(label='AMQP', icon="assets/rabbitmq_icon_64px.png")
        ca.status_bar.tray_bar.register_widget(self.amqp_icon)

        Clock.schedule_once(lambda dt: ca.set_page(1))

        self.ca = ca
        return ca

    def select(self, index):
        Clock.schedule_once(lambda dt: self.ca.set_page(index))

    def popup_presence_dlg(self, _cmd, _args):
        if self.presence_tray:
            self.presence_tray.popup_handler()


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

    with open("desktop-panel-config.json", "r") as f:
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
    cmd_dispatch.add_command_handler("screenshot", command_screenshot)
    cmd_dispatch.add_command_handler("presence popup", app.popup_presence_dlg)

    await app.async_run()

    amqp_conn.stop()
    client.loop_stop()


if __name__ == '__main__':
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
