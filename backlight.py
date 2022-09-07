""" Backlight control module """

from contextlib import nullcontext

from kivy.clock import Clock
from kivy.properties import BoundedNumericProperty, DictProperty, BooleanProperty, ObjectProperty
from kivy.uix.widget import Widget
from rpi_backlight import Backlight
from rpi_backlight.utils import detect_board_type, FakeBacklightSysfs


class BacklightControl(Widget):
    conf = DictProperty(None, allownone=True)

    brightness = BoundedNumericProperty(1, min=0, max=1)
    power = BooleanProperty(None)

    _backlight = ObjectProperty(None, allownone=True)

    def __init__(self, **kwargs):
        super(BacklightControl, self).__init__(**kwargs)

        # Store the maximal brightness to avoid looking up the dict every time the brightness changes
        self._max_br = 100
        self._backlight_clock = None
        self.ctx = None

        self.bind(conf=self._on_conf)
        self.bind(brightness=self._on_brightness)
        self.bind(power=self._on_power)

        self.bind(_backlight=self._on_backlight)

        Clock.schedule_once(lambda dt: self._setup())

    def __del__(self):
        self._cancel_backlight_clock()
        if self.ctx:
            self.ctx.__exit__()

    def _on_conf(self, _instance, _value):
        # cache maximal brightness setting
        self._max_br = min(100, self.conf.get("brightness", 100) if self.conf else 100)
        # update, if switched on
        if self.power:
            self._on_brightness(_instance, _value)

    def _on_brightness(self, _instance, _value):
        if self._backlight:
            # Assume maximum brightness if none is set
            br = self.brightness if self.brightness else 100
            self._backlight.brightness = int(self._max_br * br)

    def _on_power(self, _instance, _value):
        if not self._backlight:
            return

        if self.power:
            self._cancel_backlight_clock()
            self._backlight.power = True
            self._backlight.fade_duration = 0.1
        else:
            self._backlight.fade_duration = 0.7
            self._backlight_clock = Clock.schedule_once(lambda dt: self._power_off(), timeout=0.75)

        self._backlight.brightness = self._max_br if self.power else 0

    def _power_off(self):
        self.power = False

    def _cancel_backlight_clock(self):
        if self._backlight_clock:
            self._backlight_clock.cancel()
            self._backlight_clock = None

    def _on_backlight(self, _instance, _value):
        if self._backlight:
            # Dispatch the other properties
            for p in ['brightness', 'power']:
                self.property(p).dispatch(self)

    def _setup(self):
        bt = detect_board_type()
        # This allows us to fake a Raspberry Pi
        if bt is None:
            self.ctx = FakeBacklightSysfs()
            self.ctx.__enter__()
            self._backlight = Backlight(backlight_sysfs_path=self.ctx.path)
        else:
            self.ctx = nullcontext()
            self.ctx.__enter__()
            self._backlight = Backlight()
