import contextlib
from typing import Any

from kivy.core.window import Window
from kivy.properties import ListProperty, StringProperty
from kivy.uix.widget import Widget

import serial.tools.list_ports
from serial.serialutil import SerialException


def find_arduino():
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        if p.description == "Arduino Micro":
            return p
    return None


class PingBoardHandler(Widget):
    callbacks = ListProperty([None]*4)

    meta = StringProperty("meta")
    keys = ListProperty(['f9', 'f10', 'f11', 'f12'])

    def __init__(self, f9=None, f10=None, f11=None, f12=None, **kwargs):
        super(PingBoardHandler, self).__init__(**kwargs)

        self.callbacks = [f9, f10, f11, f12]

        self._setup_keyboard()

    def _setup_keyboard(self):
        self._keyboard = Window.request_keyboard(self._keyboard_closed, self)
        self._keyboard.bind(on_key_down=self._on_keyboard_down)

    def _keyboard_closed(self):
        self._keyboard.unbind(on_key_down=self._on_keyboard_down)
        self._keyboard = None

        self._setup_keyboard()

    def _on_keyboard_down(self, _keyboard, keycode, _text, modifiers):
        if self.meta in modifiers:
            kc = keycode[1]
            with contextlib.suppress(ValueError):
                idx = self.keys.index(kc)
                cb: Any = self.callbacks[idx]
                if cb is not None:
                    cb()

    def set_color(self, sw, color):
        cmd_string = "COL {0:1d} {1:03d} {2:03d} {3:03d}\n".format(sw, color[0], color[1], color[2])

        try:
            port = find_arduino()

            if port is None:
                print("Arduino could not be found!")
                return False

            ser = serial.Serial(port.device, 115200, timeout=1)
            ser.write(cmd_string.encode())
            res = ser.readline().decode()
            ser.close()

            if res != "OK\n":
                print(res)

            return res == "OK\n"
        except SerialException as e:
            print("Caught serial exception {}".format(e))
            return False
