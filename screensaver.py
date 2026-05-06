""" Screensaver module """

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import BoundedNumericProperty, BooleanProperty, DictProperty, NumericProperty
from kivy.uix.label import Label


Builder.load_string("""
<ScreenSaver>:
    canvas:
        # Normal screensaver: black overlay that fades in/out.
        # Black is used to fully obscure the screen when the display is idle.
        Color:
            rgba: [0, 0, 0, 1 - root.transparency]
        Rectangle:
            size: root.size
            pos: root.pos
        # Input-block overlay: semi-transparent white (desaturation effect)
        Color:
            rgba: [1, 1, 1, root._block_alpha]
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

    # --- Input-block properties ---

    _blocking = BooleanProperty(False)
    """True while a triggered page-switch input block is active."""

    _block_alpha = NumericProperty(0.0)
    """Alpha of the white desaturation overlay (0 = invisible, 1 = fully white)."""

    block_duration = NumericProperty(1.0)
    """Duration in seconds of the input block triggered by a programmatic page switch.

    Configurable via ``conf["switch_block_duration"]``.  Defaults to 1 second.
    """

    def __init__(self, **kwargs):
        super(ScreenSaver, self).__init__(**kwargs)

        self._anim = None
        self._screen_clock = None
        self._block_event = None
        self._block_anim = None

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
        if self._block_event:
            self._block_event.cancel()

    def _on_conf(self, _instance, _value):
        self._reset_countdown()
        if self.conf:
            self.block_duration = float(self.conf.get("switch_block_duration", 1.0))

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
        # When a triggered input block is active, consume the touch without
        # deactivating the block so that the user cannot dismiss it early.
        if self._blocking:
            return True

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

    def trigger_block(self, duration=None):
        """Block input and show a desaturation overlay for *duration* seconds.

        Called when a page switch is triggered programmatically (e.g. via AMQP)
        so that an unintended user tap on the newly switched page cannot fire.
        A semi-transparent white overlay is animated in to give the user a clear
        visual cue that the screen changed and is momentarily locked.

        :param duration: Block duration in seconds.  Defaults to
            :attr:`block_duration` (configurable via ``conf["switch_block_duration"]``).
        """
        actual_duration = duration if duration is not None else self.block_duration

        # Cancel any in-progress block so we can restart the timer.
        if self._block_event is not None:
            self._block_event.cancel()
            self._block_event = None
        if self._block_anim is not None:
            self._block_anim.cancel(self)
            self._block_anim = None

        self._blocking = True

        # Fade the white overlay in quickly, then schedule fade-out after duration.
        self._block_anim = Animation(_block_alpha=0.3, duration=0.1)
        self._block_anim.start(self)
        self._block_event = Clock.schedule_once(lambda dt: self._end_block(), actual_duration)

    def _end_block(self):
        """Fade out the desaturation overlay and release the input block."""
        self._block_event = None
        if self._block_anim is not None:
            self._block_anim.cancel(self)
        self._block_anim = Animation(_block_alpha=0.0, duration=0.3)
        self._block_anim.bind(on_complete=lambda *_: self._clear_blocking())
        self._block_anim.start(self)

    def _clear_blocking(self):
        self._block_anim = None
        self._blocking = False

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
