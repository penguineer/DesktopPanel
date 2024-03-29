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

    timeout = NumericProperty(None, allownone=True)
    """ Overwrite the timeout configuration

        if set to a value, overwrites the timeout configuration,
        if set to None it has no effect
    """

    disabled = BooleanProperty(False)
    """ disable the screensaver (similar to timeout 0)

        this allows to disable the screensaver (i.e. for a modal dialog) without
        changing the timeout settings
    """

    # Start in an active state and wake up immediately
    active = BooleanProperty(True)
    transparency = BoundedNumericProperty(0, min=0, max=1)

    # Signifies if the screen is needed (or can be switched off)
    # Other than the 'active' property this takes animation delay into account
    screen_active = BooleanProperty(False)

    countdown = NumericProperty(None, allownone=True)

    def __init__(self, **kwargs):
        super(ScreenSaver, self).__init__(**kwargs)

        self._anim = None
        self._screen_clock = None

        self.bind(conf=self._on_conf)

        self.bind(timeout=self._on_timeout)
        self.bind(disabled=self._on_disabled)

        self.bind(active=self._on_active)
        Clock.schedule_once(lambda dt: self.wake_up(), timeout=0.5)

        self.bind(countdown=self._on_countdown)
        self._countdown_clock = Clock.schedule_interval(lambda dt: self._on_countdown_clock(),
                                                        timeout=1)

    def __del__(self):
        if self._countdown_clock:
            self._countdown_clock.cancel()
        if self._screen_clock:
            self._screen_clock.cancel()

    def _on_conf(self, _instance, _value):
        self._reset_countdown()

    def _on_timeout(self, _instance, _value):
        if self.timeout is not None and self.timeout == 0:
            self.wake_up()
        elif not self.active:
            self._reset_countdown()

    def _on_disabled(self, _instance, _value):
        self.wake_up()

    def _on_active(self, _instance, _value):
        target_transparency = 0 if self.active else 1
        Clock.schedule_once(lambda dt: self._animate_transparency(target_transparency))

    def _animate_transparency(self, target):
        if self._anim:
            self._anim.cancel(self)

        # Slow fade-out, quick fade-in
        duration = 0.1 if target else 0.5
        self._anim = Animation(transparency=target, duration=duration)
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
        if self.disabled or self.countdown is None or self.countdown > 0:
            return

        self._cancel_countdown()
        self.active = True

    def _on_countdown_clock(self):
        if self.countdown:
            self.countdown = self.countdown - 1

    def _reset_countdown(self):
        # timeout is:
        #   self.timeout, unless None
        #   "timeout" from the configuration, unless None
        #   otherwise 0, i.e. no screensaver
        timeout = self.timeout if self.timeout is not None else int(self.conf.get("timeout", 0) if self.conf else 0)
        self.countdown = timeout if timeout else None

    def _cancel_countdown(self):
        self.countdown = None
