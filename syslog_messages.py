""" Module for syslog message display """

import datetime
from typing import Optional

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import StringProperty, ListProperty, ColorProperty
from kivy.uix.boxlayout import BoxLayout


class Colors:
    COLOR_WHITE = [1, 1, 1, 1]
    COLOR_GREY = [77 / 256, 77 / 256, 76 / 256, 1]
    COLOR_YELLOW = [249 / 256, 176 / 256, 0 / 256, 1]
    COLOR_RED = [228 / 256, 5 / 256, 41 / 256, 1]


_SEVERITY_CRITICAL = frozenset(('crit', 'critical', 'alert', 'emerg', 'panic'))


class SyslogMessage(object):
    """A syslog message received from AMQP.

    syslog-ng's AMQP connector places all message information in the AMQP
    message properties headers; the message body is empty.

    Relevant headers (from syslog-ng):
        DATE, FACILITY, HOST, HOST_FROM, MESSAGE, PID, PRIORITY, PROGRAM,
        SOURCE, SOURCEIP, TAGS, TRANSPORT
    """

    @staticmethod
    def from_amqp(method, properties) -> Optional['SyslogMessage']:
        """Create a SyslogMessage from pika AMQP method and properties.

        :param method: pika Basic.Deliver method frame (routing_key used as host fallback)
        :param properties: pika BasicProperties with a 'headers' dict
        :return: SyslogMessage instance, or None if properties are missing
        """
        if properties is None:
            return None

        headers = getattr(properties, 'headers', None) or {}

        priority = str(headers.get('PRIORITY', '')).lower()
        facility = str(headers.get('FACILITY', ''))
        host = str(headers.get('HOST', headers.get('HOST_FROM', '')))
        program = str(headers.get('PROGRAM', ''))
        message = str(headers.get('MESSAGE', ''))
        date_str = str(headers.get('DATE', ''))

        # Fall back to routing key for host if not present in headers
        if not host and method:
            routing_key = getattr(method, 'routing_key', '') or ''
            host = routing_key.split('.')[-1] if routing_key else ''

        return SyslogMessage(
            priority=priority,
            facility=facility,
            host=host,
            program=program,
            message=message,
            date_str=date_str,
        )

    def __init__(self, priority, facility, host, program, message, date_str):
        self._priority = priority
        self._facility = facility
        self._host = host
        self._program = program
        self._message = message
        self._date_str = date_str
        self._received_at = datetime.datetime.now()

    @property
    def priority(self):
        return self._priority

    @property
    def facility(self):
        return self._facility

    @property
    def host(self):
        return self._host

    @property
    def program(self):
        return self._program

    @property
    def message(self):
        return self._message

    @property
    def date_str(self):
        """The DATE string as reported by syslog-ng (e.g. 'Apr 30 19:37:03')"""
        return self._date_str

    @property
    def received_at(self):
        """datetime when this message was received by DesktopPanel"""
        return self._received_at

    def is_critical(self):
        """True if the syslog priority is critical severity or higher."""
        return self._priority in _SEVERITY_CRITICAL

    def entry_color(self):
        """Return the RGBA display color reflecting severity.

        Returns red for critical-or-higher priorities, yellow for error-level,
        and white for anything else.
        """
        if self.is_critical():
            return Colors.COLOR_RED
        if self._priority in ('error', 'err'):
            return Colors.COLOR_YELLOW
        return Colors.COLOR_WHITE

    def formatted_time(self):
        """Return a formatted time string for display.

        Returns HH:MM for messages received today, or DD.MM HH:MM for older ones.
        """
        now = datetime.datetime.now()
        if self._received_at.date() == now.date():
            return self._received_at.strftime("%H:%M")
        return self._received_at.strftime("%d.%m %H:%M")


Builder.load_string("""
<SyslogEntry>:
    orientation: 'vertical'
    size_hint: 1, None
    height: 44
    padding: [4, 2]
    spacing: 2

    Label:
        text: root.msg_host + '  ' + root.msg_time + '  ' + root.msg_program + ' (' + root.msg_facility + ')'
        font_size: 10
        font_name: 'assets/FiraMono-Regular.ttf'
        color: root.meta_color
        halign: 'left'
        valign: 'center'
        text_size: self.size
        shorten: True
        shorten_from: 'right'
        size_hint_y: None
        height: 18

    Label:
        text: root.msg_text
        font_size: 12
        color: root.entry_color
        halign: 'left'
        valign: 'center'
        text_size: self.size
        shorten: True
        shorten_from: 'right'
        size_hint_y: None
        height: 20

<SyslogMessagePanel>:
    orientation: 'vertical'
    padding: [4, 4, 8, 4]
    spacing: 2

    canvas.before:
        Color:
            rgba: root.border_color
        Line:
            points: 
                root.pos[0] + root.size[0] - 2, root.pos[1] + 4, \\ 
                root.pos[0] + root.size[0] - 2, root.pos[1] + root.size[1] - 4 

    Label:
        text: 'SYSLOG'
        size_hint: 1, None
        size: 0, 24
        color: root.header_color
        bold: True

    RecycleView:
        id: rv
        data: root.entries
        viewclass: 'SyslogEntry'
        size_hint: 1, 1

        RecycleBoxLayout:
            orientation: 'vertical'
            default_size: 0, 44
            default_size_hint: 1, None
            size_hint_y: None
            height: self.minimum_height
""")


class SyslogEntry(BoxLayout):
    msg_time = StringProperty('')
    msg_host = StringProperty('')
    msg_facility = StringProperty('')
    msg_program = StringProperty('')
    msg_text = StringProperty('')
    entry_color = ColorProperty(Colors.COLOR_WHITE)
    meta_color = ColorProperty(Colors.COLOR_GREY)


class SyslogMessagePanel(BoxLayout):
    """Kivy widget that displays a scrollable list of recent syslog messages.

    Call :meth:`add_message` (on the Kivy main thread) to add new entries.
    The panel keeps at most MAX_ENTRIES messages and refreshes time strings
    every 30 seconds.
    """

    entries = ListProperty()
    border_color = ColorProperty(Colors.COLOR_GREY)
    header_color = ColorProperty(Colors.COLOR_GREY)

    MAX_ENTRIES = 50

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._messages = []
        self._refresh_clock = Clock.schedule_interval(
            lambda dt: self._refresh_entries(), 30
        )

    def __del__(self):
        if self._refresh_clock:
            self._refresh_clock.cancel()

    def add_message(self, msg: SyslogMessage):
        """Add a new syslog message to the top of the list.

        Must be called on the Kivy main thread.
        """
        self._messages.insert(0, msg)
        if len(self._messages) > self.MAX_ENTRIES:
            self._messages = self._messages[:self.MAX_ENTRIES]
        self._refresh_entries()

    def _refresh_entries(self):
        """Rebuild the RecycleView data list from stored messages."""
        self.entries = [
            {
                'size_hint': [1, None],
                'msg_time': msg.formatted_time(),
                'msg_host': msg.host,
                'msg_facility': msg.facility,
                'msg_program': msg.program,
                'msg_text': msg.message,
                'entry_color': msg.entry_color(),
            }
            for msg in self._messages
        ]
        Clock.schedule_once(lambda dt: self.ids.rv.refresh_from_data())
