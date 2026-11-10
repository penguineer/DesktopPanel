#!/usr/bin/python3

# Desktop Panel - Desktop control panel
# with Raspberry Pi and RPi Touch Screen

# Author: Stefan Haun <tux@netz39.de>
import asyncio
import signal
import sys
import json

from logging_setup import configure_console_logging

configure_console_logging()

import amqp
import mqtt
import influxdb
import globalcontent
from page_gtd import GtdPage
from page_home import HomePage
from page_presence import PresencePage, PresenceTrayWidget
from spacestatus import SpaceStatusWidget
from page_system import SystemPage
from reloadable_json import JsonObserver
from datetime_display import DateTimeDisplay
from screenshot import screenshot_window
from shutdown import install_shutdown_handlers

from kivy import Logger
from kivy.config import Config
from kivy.app import App
from kivy.base import stopTouchApp
from kivy.core.window import Window

from kivy.clock import Clock

from kivy.properties import ObjectProperty, StringProperty

class TabbedPanelApp(App):
    conf_path = StringProperty()
    conf = ObjectProperty(None)
    mqttc = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.ca = None
        self.config_obs = None
        self.amqp_widget = None
        self.influxdb_widget = None
        self.presence_tray = None
        self.system_page = None
        self.gtd_page = None
        self._stopped = False

        self.bind(conf_path=self._on_conf_path)
        self.bind(conf=self._on_conf)
        self.bind(mqttc=self._on_mqttc)

    def _on_conf_path(self, _instance, path: str) -> None:
        if self.config_obs:
            self.config_obs.teardown()
            self.config_obs = None

        if not path:
            return

        self.config_obs = JsonObserver(path,
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
        if self.influxdb_widget:
            self.influxdb_widget.conf = conf.get("influxdb", None) if conf else None

    def _on_mqttc(self, _instance, mqttc) -> None:
        if self.ca:
            self.ca.mqttc = mqttc

    def build(self):
        home_page = HomePage()
        system_page = SystemPage()
        self.system_page = system_page
        system_page.conf_lambda = lambda conf: conf.get("system", dict())
        gtd_page = GtdPage()
        self.gtd_page = gtd_page
        gtd_page.conf_lambda = lambda conf: conf.get("gtd", dict())

        ca = globalcontent.GlobalContentArea()
        ca.conf = self.conf
        Clock.schedule_once(lambda dt: ca.register_content(home_page))
        Clock.schedule_once(lambda dt: ca.register_content(system_page))
        Clock.schedule_once(lambda dt: ca.register_content(gtd_page))

        self.mqttc = mqtt.MqttClient()
        self.mqttc.conf = self.conf
        ca.mqttc = self.mqttc
        ca.register_tray_item(self.mqttc)

        self.amqp_widget = amqp.AmqpWidget()
        self.amqp_widget.conf = self.conf.get("amqp", None) if self.conf else None
        self.amqp_widget.add_command_handler("test", command_log)
        self.amqp_widget.add_command_handler("screenshot", command_screenshot)
        self.amqp_widget.add_command_handler("show page", self._schedule_show_page)
        ca.register_tray_item(self.amqp_widget)

        self.influxdb_widget = influxdb.InfluxDbWidget()
        self.influxdb_widget.conf = self.conf.get("influxdb", None) if self.conf else None
        ca.register_tray_item(self.influxdb_widget)

        system_page.amqp_widget = self.amqp_widget
        system_page.influxdb_widget = self.influxdb_widget

        ca.register_status_item(DateTimeDisplay())

        self.presence_tray = PresenceTrayWidget()
        ca.register_status_item(
            self.presence_tray,
            conf_lambda=lambda conf: conf.get("presence", None))

        spacestatus = SpaceStatusWidget()
        ca.register_status_item(
            spacestatus,
            conf_lambda=lambda conf: conf.get("spaceApi", None))

        presence_page = PresencePage()
        Clock.schedule_once(lambda dt: self._register_presence_page(ca, presence_page))

        self.ca = ca
        return ca

    def _register_presence_page(self, ca, presence_page):
        """Wire the PresencePage to the PresenceTrayWidget and register it with the router."""
        self.presence_tray.register_presence_page(presence_page)
        presence_page.go_back_callback = ca.router.go_back
        ca.register_border_button(self.presence_tray, presence_page)

    def on_stop(self):
        if self._stopped:
            return
        self._stopped = True

        # Tear down each resource even if another resource fails to stop.
        for name, resource in (
            ("configuration observer", self.config_obs),
            ("GTD page", self.gtd_page),
            ("system page", self.system_page),
            ("MQTT", self.mqttc),
            ("AMQP", self.amqp_widget),
            ("InfluxDB", self.influxdb_widget),
        ):
            if resource is not None:
                try:
                    resource.teardown()
                except Exception:
                    Logger.exception("App: Failed to stop %s", name)

    def select(self, index):
        Clock.schedule_once(lambda dt: self.ca.set_page(index))

    def _schedule_show_page(self, _cmd, args):
        handle = args.get("page", None)
        go_back_if_current = args.get("go_back_if_current", False)
        block_input = args.get("block_input", False)
        if handle:
            Clock.schedule_once(
                lambda dt: self.ca.router.switch_to_label(handle,
                                                          go_back_if_current=go_back_if_current,
                                                          block_input=block_input))

    def schedule_update_configuration(self, conf):
        Clock.schedule_once(lambda dt: self.setter('conf')(self, conf))


def command_log(cmd, args):
    Logger.info("App: Received command %s with args %s.", cmd, args)


def command_screenshot(_cmd, _args):
    screenshot_window()


async def main():
    def request_stop(signum):
        Logger.info("App: Received %s, shutting down", signal.Signals(signum).name)
        # Let async_run() finish normally so Kivy invokes on_stop() once.
        stopTouchApp()

    restore_signals = install_shutdown_handlers(
        asyncio.get_running_loop(), request_stop
    )
    try:
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
        app.conf_path = "configuration/desktop-panel-config.json"

        await app.async_run()
    finally:
        restore_signals()


if __name__ == '__main__':
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
