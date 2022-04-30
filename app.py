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
from statusbar import StatusBar, TrayIcon

from kivy import Logger
from kivy.config import Config
from kivy.app import App
from kivy.core.window import Window

from kivy.clock import Clock

from kivy.lang import Builder
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


Builder.load_string("""
<HomePage>:
    label: 'home'
    icon: 'assets/icon_home.png'

    Label:
        text: 'HOME'
""")


class HomePage(globalcontent.ContentPage):
    pass


Builder.load_string("""
<SystemPage>:
    label: 'system'
    icon: 'assets/icon_system.png'
    
    Label:
        text: 'SYSTEM'            
""")


class SystemPage(globalcontent.ContentPage):
    pass


from kivy.properties import StringProperty, ListProperty


Builder.load_string("""
#:import IssueList issues.IssueList

<GtdPage>:
    label: 'system'
    icon: 'assets/icon_gtd.png'

    BoxLayout:
        orientation: 'horizontal'

        Label:
            text: ''

        IssueList:
            issue_list_path: root.issue_list_path
            size_hint: None, 1           
""")


class GtdPage(globalcontent.ContentPage):
    mqttc = ObjectProperty(None)
    issue_list_path = StringProperty("issuelist.json")


class TabbedPanelApp(App):
    mqtt_icon = ObjectProperty(None)
    amqp_icon = ObjectProperty(None)

    mqttc = ObjectProperty(None)

    def __init__(self, config, mqttc, **kwargs):
        super().__init__(**kwargs)

        self._config = config
        self.mqttc = mqttc

        self.ca = None

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

        ca.register_status_bar(StatusBar())

        self.mqtt_icon = TrayIcon(label='MQTT', icon="assets/mqtt_icon_64px.png")
        ca.status_bar.tray_bar.register_widget(self.mqtt_icon)

        self.amqp_icon = TrayIcon(label='AMQP', icon="assets/rabbitmq_icon_64px.png")
        ca.status_bar.tray_bar.register_widget(self.amqp_icon)

        Clock.schedule_once(lambda dt: ca.set_page(2))

        self.ca = ca
        return ca


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

    await app.async_run()

    amqp_conn.stop()
    client.loop_stop()


if __name__ == '__main__':
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
