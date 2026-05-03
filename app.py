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
from page_presence import PresencePage
from page_system import SystemPage
from reloadable_json import JsonObserver

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
    conf_path = StringProperty()
    conf = ObjectProperty(None)
    mqttc = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.ca = None
        self.config_obs = None
        self.amqp_widget = None

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

        try:
            with open(path, "r") as f:
                self.schedule_update_configuration(json.load(f))
        except FileNotFoundError as e:
            Logger.warning("App: Configuration file not found: %s", e)
        except json.decoder.JSONDecodeError as e:
            Logger.warning("App: Invalid JSON in configuration file: %s", e)

    def _on_conf(self, _instance, conf: dict) -> None:
        if self.ca:
            self.ca.conf = conf
        if self.mqttc:
            self.mqttc.conf = conf.get("mqtt", None)
        if self.amqp_widget:
            self.amqp_widget.conf = conf.get("amqp", None) if conf else None

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

        self.amqp_widget = amqp.AmqpWidget()
        self.amqp_widget.conf = self.conf.get("amqp", None) if self.conf else None
        self.amqp_widget.add_command_handler("test", command_log)
        self.amqp_widget.add_command_handler("screenshot", command_screenshot)
        self.amqp_widget.add_command_handler("show page", self._schedule_show_page)
        ca.status_bar.tray_bar.register_widget(self.amqp_widget)

        system_page.amqp_widget = self.amqp_widget

        presence_page = PresencePage()
        Clock.schedule_once(lambda dt: self._register_presence_page(ca, presence_page))

        self.ca = ca
        return ca

    def _register_presence_page(self, ca, presence_page):
        """Wire the PresencePage to the PresenceTrayWidget and register it with the router.

        Called one frame after build() so that all KV-defined widget ids on the
        status bar and PresenceTrayWidget are guaranteed to be available.
        """
        presence = ca.status_bar.ids.presence

        presence_page.request_callback = presence.ids.change_handler.post_status

        presence_page.handle_self = presence.handle_self
        presence.bind(handle_self=presence_page.setter('handle_self'))

        presence_page.contacts = presence.contacts
        presence.bind(contacts=presence_page.setter('contacts'))

        presence_page.presence_list = presence.presence_list
        presence.bind(presence_list=presence_page.setter('presence_list'))

        presence_page.tracked_entries = presence.ids.presence_tracker.tracked_entries
        presence.ids.presence_tracker.bind(tracked_entries=presence_page.setter('tracked_entries'))

        presence_page.requested_status = presence.ids.change_handler.requested_status
        presence.ids.change_handler.bind(requested_status=presence_page.setter('requested_status'))
        presence_page.bind(requested_status=presence.ids.change_handler.setter('requested_status'))

        presence_page.active_presence = presence.active_presence
        presence.bind(active_presence=presence_page.setter('active_presence'))

        presence_page.bind(active=self._on_presence_page_active)

        ca.register_border_button(presence, presence_page)

    def _on_presence_page_active(self, instance, value):
        """Refresh presence data when the presence page becomes visible."""
        if not value:
            return
        presence = self.ca.status_bar.ids.presence
        Clock.schedule_once(lambda dt: presence.ids.presence_receiver.receive_status())
        Clock.schedule_once(lambda dt: presence.ids.history_fetcher.fetch_history())

    def on_stop(self):
        if self.config_obs is not None:
            self.config_obs.teardown()
        if self.amqp_widget is not None:
            self.amqp_widget.teardown()

    def select(self, index):
        Clock.schedule_once(lambda dt: self.ca.set_page(index))

    def _schedule_show_page(self, _cmd, args):
        handle = args.get("page", None)
        if handle:
            Clock.schedule_once(lambda dt: self.ca.router.switch_to(handle))

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

    # build and run app
    app = TabbedPanelApp()
    # Setup path for automatic reloading with initial configuration pre-load
    app.conf_path = "desktop-panel-config.json"

    await app.async_run()


if __name__ == '__main__':
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
