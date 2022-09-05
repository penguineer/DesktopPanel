""" Utility functions and classes"""

import dateutil.parser
import datetime


# Based on https://stackoverflow.com/a/26781642/3888050
class HumanizedTimeDisplay(object):
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

    def __init__(self, units='s', max_len=2):
        self._unit = list(map(lambda am: am[1], HumanizedTimeDisplay.NAMES)).index(units)
        self._max_len = max_len

    def convert_amount(self, amount):
        rd = self._partition(int(amount))
        buf = self._format(rd)
        return buf

    def convert_iso8601(self, iso8601):
        dt = dateutil.parser.parse(iso8601)
        dt = HumanizedTimeDisplay._fix_timezone(dt)

        ts = datetime.datetime.now(dt.tzinfo) - dt
        return self.convert_amount(ts.total_seconds())

    @staticmethod
    def _fix_timezone(dt):
        # if the timezone info is missing Python uses local time, and we need to convert manually
        if not dt.tzinfo:
            system_tz = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
            dt = dt.replace(tzinfo=system_tz)
            dt += system_tz.utcoffset(dt)
        return dt

    def _convert_to_seconds(self, amount):
        return amount * HumanizedTimeDisplay.INTERVALS[self._unit]

    def _partition(self, amount):
        result = []

        # Convert to seconds
        amount = self._convert_to_seconds(amount)

        for i in range(len(HumanizedTimeDisplay.NAMES) - 1, -1, -1):
            a = amount // HumanizedTimeDisplay.INTERVALS[i]
            if a > 0:
                result.append((a, HumanizedTimeDisplay.NAMES[i][1 % a]))
                amount -= a * HumanizedTimeDisplay.INTERVALS[i]

        return result

    def _format(self, rd):
        return " ".join(
            map(lambda e: "%d%s" % (e[0], e[1]),
                filter(lambda e: e[0] > 0,
                       rd[0:self._max_len])))
