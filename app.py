#!/usr/bin/python3

# Desktop Panel - Desktop control panel
# with Raspberry Pi and RPi Touch Screen

# Author: Stefan Haun <tux@netz39.de>

import signal
import sys

import json
from functools import partial

import mqtt
import globalcontent
from pingboard import PingBoardHandler
from presence import PresenceDlg, Presence
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
<IssueEntry>
    orientation: 'horizontal'
    size_hint: 1, None
    spacing: 4
        
    Label:
        text: root.issue_id
        size: 40, 0
        size_hint_x: None
        text_size: self.size[0]-12, self.size[1]
        halign: 'right'
        valign: 'center'
        font_size: 14
        font_name: 'assets/FiraMono-Regular.ttf'
        color: root.id_color

        canvas.before:
            Color:
                rgba: root.id_background
            RoundedRectangle:
                pos: self.pos[0] + 2, self.pos[1] + 1                
                size: self.size[0] - 4, self.size[1] - 2
                radius: [5,5]        
    
    Label:
        text: root.issue_label
        text_size: self.size[0], self.size[1]
        halign: 'left'
        valign: 'center'
        font_size: 14
        color: root.label_color

<IssueList>
    orientation: 'vertical'
    size: 300, 300
    padding: 4
    spacing: 4

    canvas.before:
        Color:
            rgba: root.border_color
        Line:
            rounded_rectangle: self.pos[0]+2, self.pos[1]+2, self.size[0]-4, self.size[1]-4, 5, 100
        Line:
            points: 
                root.pos[0] + 6, \\ 
                root.pos[1] + root.size[1] - 24 - 4, \\ 
                root.pos[0] + root.size[0] - 6, \\ 
                root.pos[1] + root.size[1] - 24 - 4 
                
    Label:
        text: root.issue_list_label
        size_hint: 1, None
        size: 0, 24
        color: root.header_color
        bold: True

    RecycleView:    
        id: rv
        data: root.entries
        viewclass: 'IssueEntry'
        size_hint: 1, 1
    
        RecycleBoxLayout:
            orientation: 'vertical'
            default_size: 0, 20
            
            

<GtdPage>:
    label: 'system'
    icon: 'assets/icon_gtd.png'

    BoxLayout:
        orientation: 'horizontal'

        Label:
            text: ''
            
        IssueList:
            size_hint: None, 1           
""")

from kivy.properties import StringProperty, ListProperty, ColorProperty
from kivy.uix.boxlayout import BoxLayout


class IssueEntry(BoxLayout):
    issue_label = StringProperty()
    issue_id = StringProperty()

#    id_color = ColorProperty([0 / 256, 0 / 256, 0 / 256, 1])
    id_color = ColorProperty([256 / 256, 256 / 256, 256 / 256, 1])
#    id_background = ColorProperty([0 / 256, 132 / 256, 176 / 256, 1])
    id_background = ColorProperty([24 / 256, 56 / 256, 107 / 256, 1])
    label_color = ColorProperty([256 / 256, 256 / 256, 256 / 256, 1])


class IssueList(BoxLayout):
    issue_list_label = StringProperty("GTD")
    entries = ListProperty()

    border_color = ColorProperty([249 / 256, 176 / 256, 0 / 256, 1])
    header_color = ColorProperty([249 / 256, 176 / 256, 0 / 256, 1])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.issue_list = None
        with open("issuelist.json", "r") as f:
            self.update_issue_list(json.load(f))

    def update_issue_list(self, issue_list):
        self.issue_list = issue_list

        self.issue_list_label = issue_list['label']
        self.entries.clear()

        for issue in issue_list['issues']:
            self.entries.append({
                'opacity': 1,
                'issue_id': str(issue['id']),
                'issue_label': issue['label'],
                'size_hint': [1, None]
            })

        self.entries.append({
            'issue_id': '',
            'issue_label': '',
            'opacity': 0,
            'size_hint': [1, 1]
        })

        Clock.schedule_once(lambda dt: self.ids.rv.refresh_from_data())


class GtdPage(globalcontent.ContentPage):

    mqttc = ObjectProperty(None)


class TabbedPanelApp(App):
    mqtt_icon = ObjectProperty(None)

    mqttc = ObjectProperty(None)

    def __init__(self, mqttc, **kwargs):
        super().__init__(**kwargs)

        self.mqttc = mqttc

        self._pbh = PingBoardHandler(
            f12=partial(self.flash,  1, [1, 6, 0]),
            f11=partial(self.flash, 2, [5, 4, 0]),
            f10=partial(self.flash, 3, [3, 0, 0]),
            f9=partial(self.flash, 4, [0, 1, 12])
        )
        # f9=partial(self.flash, 4, [0, 1, 12])

    def build(self):
        home_page = HomePage()
        system_page = SystemPage()
        gtd_page = GtdPage()
        gtd_page.mqttc = self.mqttc

        ca = globalcontent.GlobalContentArea()
        Clock.schedule_once(lambda dt: ca.register_content(home_page))
        Clock.schedule_once(lambda dt: ca.register_content(system_page))
        Clock.schedule_once(lambda dt: ca.register_content(gtd_page))

        ca.register_status_bar(StatusBar())

        self.mqtt_icon = TrayIcon(label='MQTT', icon="assets/mqtt_icon_64px.png")
        ca.status_bar.tray_bar.register_widget(self.mqtt_icon)

        Clock.schedule_once(lambda dt: ca.set_page(2))

        ca.add_widget(self._pbh)

        return ca

    def flash(self, sw, color):
        succ = self._pbh.set_color(sw, color)
        print(succ)
        if succ:
            Clock.schedule_once(lambda dt: partial(self._pbh.set_color, sw, [0, 0, 0])(),
                                timeout=1)


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
    app = TabbedPanelApp(client)
    app.bind(mqtt_icon=lambda i, v: mqtt.update_tray_icon(client, v))

    app.run()

    client.loop_stop()


if __name__ == '__main__':
    main()
