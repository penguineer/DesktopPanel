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
    for topic in MQTT_TOPICS:
        mqttc.subscribe(topic)


def create_client(config):
    if "MQTT" not in config.keys():
        print("Missing MQTT section in configuration. See template for an example.")
        sys.exit(1)

    host = config.get("MQTT", "host")

    client = mqtt.Client()
    client.on_connect = on_connect
    client.connect(host, 1883, 60)
    client.loop_start()

    return client


def topic_matches_sub(sub, topic):
    return mqtt.topic_matches_sub(sub, topic)
