#!/usr/bin/python3

# Desktop Panel - Desktop control panel
# with Raspberry Pi and RPi Touch Screen

# Author: Stefan Haun <tux@netz39.de>

import signal
import sys

import json

import mqtt

from kivy.config import Config

running = True


def sigint_handler(_signal, _frame):
    global running

    if running:
        print("SIGINT received. Stopping the queue.")
        running = False
    else:
        print("Receiving SIGINT the second time. Exit.")
        sys.exit(0)


def main():
    signal.signal(signal.SIGINT, sigint_handler)

    Config.set('kivy', 'default_font', [
        ' FiraSans-Regular',
        './resources/FiraSans-Regular.ttf',
        './resources/FiraSans-Regular.ttf',
        './resources/FiraSans-Regular.ttf',
        './resources/FiraSans-Regular.ttf'
    ])

    with open("desktop-panel.cfg", "r") as f:
        config = json.load(f)

    if 'mqtt' not in config:
        raise ValueError("Missing mqtt section in configuration! See template for an example.")
    mqtt_config = config.get('mqtt')
    client = mqtt.create_client(mqtt_config)

    # TODO build and run app

    client.loop_stop()


if __name__ == '__main__':
    main()
