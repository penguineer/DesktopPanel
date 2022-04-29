import sys

import paho.mqtt.client as mqtt

from kivy import Logger
from kivy.clock import Clock

MQTT_TOPICS = []


def append_topic(topic):
    MQTT_TOPICS.append(topic)


def add_topic_callback(mqttc, topic, cb):
    mqttc.subscribe(topic)
    MQTT_TOPICS.append(topic)

    mqttc.message_callback_add(topic, cb)


def on_connect(mqttc, _userdata, _flags, rc):
    Logger.info("MQTT: Client connected with code %s", rc)
    set_tray_icon_color(_userdata, status="connected")

    for topic in MQTT_TOPICS:
        mqttc.subscribe(topic)


def on_disconnect(mqttc, _userdata, rc):
    Logger.info("MQTT: Client disconnected with code %s", rc)
    set_tray_icon_color(_userdata, status="disconnected")


def create_client(config):
    if "host" not in config:
        raise ValueError("Missing MQTT host configuration! See template for an example.")

    host = config.get("host")

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    try:
        client.connect(host, 1883, 60)
    except ConnectionRefusedError as e:
        Logger.warning("MQTT: Failed to connect to MQTT client, will try again: %s", e)

    client.loop_start()

    return client


def update_tray_icon(mqttc, tray_icon, status=None):
    mqttc.user_data_set(tray_icon)
    if status is None and mqttc.is_connected():
        status = "connected"
    set_tray_icon_color(tray_icon, status)


def set_tray_icon_color(tray_icon, status=None):
    if tray_icon is None:
        return

    if status == "connected":
        schedule_kivy_icon_color(tray_icon, [0 / 256, 163 / 256, 86 / 256, 1])
    elif status == "disconnected":
        schedule_kivy_icon_color(tray_icon, [228 / 256, 5 / 256, 41 / 256, 1])
    else:
        schedule_kivy_icon_color(tray_icon, [77 / 256, 77 / 256, 76 / 256, 1])


def schedule_kivy_icon_color(tray_icon, color):
    Clock.schedule_once(lambda dt: tray_icon.setter('icon_color')(tray_icon, color))


def topic_matches_sub(sub, topic):
    return mqtt.topic_matches_sub(sub, topic)
