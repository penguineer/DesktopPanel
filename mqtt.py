import sys

import paho.mqtt.client as mqtt


MQTT_TOPICS = []


def append_topic(topic):
    MQTT_TOPICS.append(topic)


def add_topic_callback(mqttc, topic, cb):
    mqttc.subscribe(topic)
    MQTT_TOPICS.append(topic)

    mqttc.message_callback_add(topic, cb)


def on_connect(mqttc, _userdata, _flags, rc):
    print("MQTT client connected with code %s" % rc)
    set_tray_icon_color(mqttc, _userdata)

    for topic in MQTT_TOPICS:
        mqttc.subscribe(topic)


def on_disconnect(mqttc, _userdata, rc):
    print("MQTT client disconnected with code %s" % rc)
    set_tray_icon_color(mqttc, _userdata)


def create_client(config):
    if "MQTT" not in config.keys():
        print("Missing MQTT section in configuration. See template for an example.")
        sys.exit(1)

    host = config.get("MQTT", "host")

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.connect(host, 1883, 60)
    client.loop_start()

    return client


def update_tray_icon(mqttc, tray_icon):
    mqttc.user_data_set(tray_icon)
    set_tray_icon_color(mqttc, tray_icon)


def set_tray_icon_color(mqttc, tray_icon):
    if tray_icon is None:
        return

    tray_icon.icon_color = [77 / 256, 77 / 256, 76 / 256, 1]

    if mqttc is None:
        return

    if mqttc.is_connected():
        tray_icon.icon_color = [0 / 256, 163 / 256, 86 / 256, 1]
    else:
        tray_icon.icon_color = [228 / 256, 5 / 256, 41 / 256, 1]


def topic_matches_sub(sub, topic):
    return mqtt.topic_matches_sub(sub, topic)
