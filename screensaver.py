""" Screensaver module """

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import BoundedNumericProperty, BooleanProperty, DictProperty, NumericProperty
from kivy.uix.label import Label


Builder.load_string("""
<ScreenSaver>:
    canvas:
        Color:
            rgba: [0, 0, 0, 1 - root.transparency]  # Is black really the best resting color?
            
        Rectangle:
            size: root.size
            pos: root.pos
""")


class ScreenSaver(Label):
    conf = DictProperty(None, allownone=True)

    # Start in an active state and wake up immediately
    active = BooleanProperty(True)
    transparency = BoundedNumericProperty(0, min=0, max=1)

    # Signifies if the screen is needed (or can be switched off)
    # Other than the 'active' property this takes animation delay into account
    screen_active = BooleanProperty(False)

    countdown = NumericProperty(None, allownone=True)

    def __init__(self, **kwargs):
        super(ScreenSaver, self).__init__(**kwargs)

        self.bind(conf=self._on_conf)

        self._anim = None

        self.bind(active=self._on_active)
        Clock.schedule_once(lambda dt: self.wake_up(), timeout=0.5)

        self.bind(countdown=self._on_countdown)
        self._countdown_clock = Clock.schedule_interval(lambda dt: self._on_countdown_clock(),
                                                        timeout=1)

        self._screen_clock = None

    def __del__(self):
        if self._countdown_clock:
            self._countdown_clock.cancel()
        if self._screen_clock:
            self._screen_clock.cancel()

    def _on_conf(self, _instance, _value):
        self._reset_countdown()

    def _on_active(self, _instance, _value):
        target_transparency = 0 if self.active else 1
        Clock.schedule_once(lambda dt: self._animate_transparency(target_transparency))

    def _animate_transparency(self, target):
        if self._anim:
            self._anim.cancel(self)

        self._anim = Animation(transparency=target, duration=0.5)
        self._anim.bind(on_complete=lambda e, i: self._animation_complete())

        self._anim.start(self)

    def _animation_complete(self):
        self._anim = None

        if self.active:
            self._screen_clock = Clock.schedule_once(lambda dt: self.setter('screen_active')(self, False),
                                                     timeout=0.5)

    def wake_up(self):
        current_state = self.active

        if self._screen_clock:
            self._screen_clock.cancel()
            self._screen_clock = None
        self.screen_active = True

        self.active = False
        self._reset_countdown()

        # returns True when the screensaver was activated
        # This allows to directly block touch events on an active screen saver
        return current_state

    def _on_countdown(self, _instance, _value):
        if self.countdown is None or self.countdown > 0:
            return

        self.countdown = None
        self.active = True

    def _on_countdown_clock(self):
        if self.countdown:
            self.countdown = self.countdown - 1

    def _reset_countdown(self):
        timeout = int(self.conf.get("timeout", 0) if self.conf else 0)
        self.countdown = timeout if timeout else None
