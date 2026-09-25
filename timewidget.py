""" Module for widgets around time"""

from kivy.clock import Clock
from kivy.properties import NumericProperty, StringProperty, ListProperty, BooleanProperty
from kivy.uix.label import Label

import dateutil.parser
import datetime
import isodate

INTERVALS = [1, 60,
             60 * 60,
             60 * 60 * 24,
             60 * 60 * 24 * 7,
             60 * 60 * 24 * 7 * 4,
             60 * 60 * 24 * 7 * 4 * 12]

NAMES = [('s', 's'),
         ('m', 'm'),
         ('h', 'h'),
         ('d', 'd'),
         ('w', 'w'),
         ('mo', 'mos'),
         ('yr', 'yrs')]


def parse_iso8601_duration(value) -> float:
    """Parse an ISO 8601 duration string and return seconds.

    Numeric values are deliberately rejected so callers do not accidentally
    invent unit conventions around a shared helper.
    """
    if not isinstance(value, str):
        raise ValueError(f"ISO 8601 duration must be a string: {value!r}")
    try:
        duration = isodate.parse_duration(value)
    except (isodate.isoerror.ISO8601Error, ValueError, TypeError) as exc:
        raise ValueError(f"Cannot parse ISO 8601 duration: {value!r}") from exc

    if isinstance(duration, isodate.duration.Duration) and (duration.years or duration.months):
        raise ValueError(f"Calendar-dependent duration is not supported: {value!r}")

    return duration.total_seconds()


def humanize_duration_millis(millis, elements=2):
    """Format milliseconds using the same compact units as HumanizedDurationLabel."""

    amount = int(millis / 1000)
    partitions = []
    for i in range(len(NAMES) - 1, -1, -1):
        value = amount // INTERVALS[i]
        name = NAMES[i][1] if value == 0 else NAMES[i][1 % value]
        partitions.append((value, name))
        amount -= value * INTERVALS[i]

    idx = next(
        (i for i, item in enumerate(partitions) if item[0] != 0),
        len(partitions) - 1,
    )
    return " ".join(
        "%d%s" % (item[0], item[1])
        for item in partitions[idx:idx + elements]
    )


class HumanizedDurationLabel(Label):
    """ Show a label with N consecutive duration parts, such as `1h 5m` """

    elements = NumericProperty(2)
    """ How many time elements to show """

    update = BooleanProperty(False)
    """ Setting update to True will update the duration_millis (and display) based on the time delta to iso_instant """

    iso_instant = StringProperty(None, allownone=True)
    """ Set an ISO8601 timestamp. This is needed for constants updates! """

    # Seems that parsing ISO8601 durations is not part of Python?

    duration_millis = NumericProperty(None, allownone=True)
    """ Set a duration in milliseconds. This is updated by iso_instant and the Clock if updates is True. """

    _partitions = ListProperty(None, allownone=True)
    """ Normalized time as yrs, mos, w, d, h, m, s in a list, see NAMES"""

    def __init__(self, **kwargs):
        super(HumanizedDurationLabel, self).__init__(**kwargs)

        self._update_clock = None

    def on_elements(self, _instance, _value):
        # Update the display
        self.property("_partitions").dispatch(self)

    def on_update(self, _instance, _value):
        if self._update_clock:
            self._update_clock.cancel()
            self._update_clock = None

        if self.update:
            self._update_clock = Clock.schedule_interval(lambda dt: self.property("iso_instant").dispatch(self),
                                                         timeout=1)

    def on_iso_instant(self, _instance, _value):
        if self.iso_instant is None:
            self.duration_millis = None
            return

        dt = dateutil.parser.parse(self.iso_instant)
        dt = HumanizedDurationLabel.fix_timezone(dt)

        ts = datetime.datetime.now(dt.tzinfo) - dt
        ms = ts.total_seconds() * 1000

        self.duration_millis = int(ms)

    @staticmethod
    def fix_timezone(dt):
        # if the timezone info is missing Python uses local time, and we need to convert manually
        if not dt.tzinfo:
            system_tz = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
            dt = dt.replace(tzinfo=system_tz)
            dt += system_tz.utcoffset(dt)
        return dt

    def on_duration_millis(self, _instance, millis):
        if self.duration_millis is None:
            self.text = ''
            return

        # normalize time
        amount = int(millis / 1000)

        partitions = []
        for i in range(len(NAMES) - 1, -1, -1):
            a = amount // INTERVALS[i]
            name = NAMES[i][1] if a == 0 else NAMES[i][1 % a]
            partitions.append((a, name))
            amount -= a * INTERVALS[i]

        self._partitions = partitions

    def on__partitions(self, _instance, _value):
        self.text = humanize_duration_millis(
            self.duration_millis,
            elements=self.elements,
        )
