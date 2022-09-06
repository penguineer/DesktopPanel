import socket

import paho.mqtt.client as mqtt

from kivy import Logger
from kivy.lang import Builder
from kivy.properties import ObjectProperty, StringProperty

from statusbar import TrayIcon

Builder.load_string("""
<MqttClient>:
    label: "MQTT"        
    icon: "assets/mqtt_icon_64px.png"
""")


class MqttClient(TrayIcon):
    conf = ObjectProperty(None, allownone=True)

    backend = ObjectProperty(None, allownone=True)

    status = StringProperty(None, allownone=True)
    error = StringProperty(None, allownone=True)

    def __init__(self, **kwargs):
        super(MqttClient, self).__init__(**kwargs)

        self.bind(conf=self._on_conf)
        self.bind(status=self._on_status)

        self.subscriptions = dict()

    def __del__(self):
        self._disconnect()

    def _on_conf(self, _instance, _value):
        self._connect()

    def _on_status(self, _instance, _value):
        if self.status == "connected":
            self.icon_color = [0 / 256, 163 / 256, 86 / 256, 1]
        elif self.status == "disconnected":
            self.icon_color = [228 / 256, 5 / 256, 41 / 256, 1]
        else:
            self.icon_color = [77 / 256, 77 / 256, 76 / 256, 1]

    def subscribe(self, topic, cb):
        self.subscriptions[topic] = cb
        self._register_callback(topic, cb)

    def unsubscribe(self, topic):
        if topic in self.subscriptions:
            del self.subscriptions[topic]

    def publish(self, topic, payload, qos=2):
        if self.backend:
            self.backend.publish(topic, payload, qos=qos)

    def _log_error(self, error):
        self.error = error
        if error:
            Logger.warning("MQTT: %s", error)

    def _connect(self):
        self.status = None
        self.backend = None

        if not self.conf:
            self._disconnect()

        host = self.conf.get("host", None)
        if not host:
            self._log_error("Missing MQTT host configuration! See template for an example.")
            return

        client = mqtt.Client()
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        try:
            client.connect(host, 1883, 60)

            client.loop_start()

            self.backend = client
        except ConnectionRefusedError as e:
            self._log_error(f"Failed to connect to MQTT client, will try again: %s" % e)
        except socket.gaierror as e:
            self._log_error(f"Host not found, will try again: %s" % e)

    def _on_connect(self, _backend, _userdata, _flags, rc):
        Logger.info("MQTT: Client connected with code %s", rc)
        self.status = "connected"

        for topic, cb in self.subscriptions.items():
            self._register_callback(topic, cb)

    def _disconnect(self):
        if self.backend:
            self.backend.loop_stop()

    def _on_disconnect(self, _backend, _userdata, rc):
        Logger.info("MQTT: Client disconnected with code %s", rc)
        self.status = "disconnected"

    def _register_callback(self, topic, cb):
        if self.backend:
            self.backend.subscribe(topic)
            self.backend.message_callback_add(topic, cb)

    @staticmethod
    def topic_matches_sub(sub, topic):
        return mqtt.topic_matches_sub(sub, topic)
