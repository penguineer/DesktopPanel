#!/usr/bin/python3

# Desktop Panel - Desktop control panel
# with Raspberry Pi and RPi Touch Screen

# Author: Stefan Haun <tux@netz39.de>

import signal
import sys

import json

import mqtt
import globalcontent
from statusbar import StatusBar, TrayIcon

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
        print("SIGINT received. Stopping the queue.")
        running = False
    else:
        print("Receiving SIGINT the second time. Exit.")
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


Builder.load_string("""
<GtdPage>:
    label: 'system'
    icon: 'assets/icon_gtd.png'

    Label:
        text: 'GTD'
""")


class GtdPage(globalcontent.ContentPage):
    pass


class TabbedPanelApp(App):
    mqtt_icon = ObjectProperty(None)

    def build(self):
        home_page = HomePage()
        system_page = SystemPage()
        gtd_page = GtdPage()

        ca = globalcontent.GlobalContentArea()
        Clock.schedule_once(lambda dt: ca.register_content(home_page))
        Clock.schedule_once(lambda dt: ca.register_content(system_page))
        Clock.schedule_once(lambda dt: ca.register_content(gtd_page))

        ca.register_status_bar(StatusBar())

        self.mqtt_icon = TrayIcon(label='MQTT', icon="assets/mqtt_icon_64px.png")
        ca.status_bar.tray_bar.register_widget(self.mqtt_icon)

        return ca


def main():
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

    # TODO build and run app
    app = TabbedPanelApp()
    app.bind(mqtt_icon=lambda i, v: mqtt.update_tray_icon(client, v))

    app.run()

    client.loop_stop()


if __name__ == '__main__':
    main()
