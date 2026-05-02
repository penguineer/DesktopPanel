""" Module for syslog message display """

import datetime
import functools
from typing import Optional

from kivy import Logger
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import StringProperty, ListProperty, ColorProperty, NumericProperty, ObjectProperty
from kivy.uix.boxlayout import BoxLayout

from scrollable_list import ScrollableList  # noqa: F401 - ScrollableList used in KV


class Colors:
    COLOR_WHITE = [1, 1, 1, 1]
    COLOR_GREY = [77 / 256, 77 / 256, 76 / 256, 1]
    COLOR_YELLOW = [249 / 256, 176 / 256, 0 / 256, 1]
    COLOR_RED = [228 / 256, 5 / 256, 41 / 256, 1]


_SEVERITY_CRITICAL = frozenset(('crit', 'critical', 'alert', 'emerg', 'panic'))

# Syslog severity levels: lower number = more severe (follows RFC 5424)
_SEVERITY_ORDER = {
    'emerg': 0, 'panic': 0,
    'alert': 1,
    'crit': 2, 'critical': 2,
    'err': 3, 'error': 3,
    'warning': 4, 'warn': 4,
    'notice': 5,
    'info': 6,
    'debug': 7,
}
_SEVERITY_UNKNOWN = 8  # unknown priorities are treated as below debug


def _passes_filter(priority, min_priority):
    """True if *priority* is at or above (more severe than) *min_priority*.

    Both arguments are lower-cased syslog priority strings.  Unknown priority
    strings are treated as the lowest possible severity and therefore fail any
    filter with a defined min_priority.
    """
    level = _SEVERITY_ORDER.get(priority, _SEVERITY_UNKNOWN)
    threshold = _SEVERITY_ORDER.get(min_priority, _SEVERITY_UNKNOWN)
    return level <= threshold


# Entry layout metrics (used to compute per-entry heights)
_ENTRY_PADDING_V = 4      # total vertical padding per entry (top=0, bottom=4)
_ENTRY_META_HEIGHT = 14   # height of the single metadata row
_ENTRY_SPACING = 2        # vertical spacing between metadata and message
_ENTRY_LINE_HEIGHT = 16   # height per wrapped message line (12 pt font)
_ENTRY_CHARS_PER_LINE = 50  # rough estimate for word-wrap at ~50 % panel width

# Minimum (1-line message) entry height — used as default in KV
_ENTRY_MIN_HEIGHT = (_ENTRY_PADDING_V + _ENTRY_META_HEIGHT
                     + _ENTRY_SPACING + _ENTRY_LINE_HEIGHT)


def _msg_lines(text):
    """Estimate wrapped line count for a message, capped at 3."""
    if not text:
        return 1
    return min(3, max(1, -(-len(text) // _ENTRY_CHARS_PER_LINE)))


def _entry_height(text):
    """Total pixel height for an entry given its message text."""
    return (_ENTRY_PADDING_V + _ENTRY_META_HEIGHT
            + _ENTRY_SPACING + _msg_lines(text) * _ENTRY_LINE_HEIGHT)


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
        self._acknowledged = False

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

    def acknowledge(self):
        """Mark the message as acknowledged; it will be displayed in grey."""
        self._acknowledged = True

    @property
    def is_acknowledged(self):
        """True once the message has been acknowledged (manually or by timeout)."""
        return self._acknowledged

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

    def display_color(self):
        """Return the color to use for rendering this entry.

        Returns grey when the message has been acknowledged; otherwise
        delegates to :meth:`entry_color`.
        """
        if self._acknowledged:
            return Colors.COLOR_GREY
        return self.entry_color()

    def formatted_time(self):
        """Return a formatted time string for display.

        Returns HH:MM for messages received today, or DD.MM HH:MM for older ones.
        """
        now = datetime.datetime.now()
        if self._received_at.date() == now.date():
            return self._received_at.strftime("%H:%M")
        return self._received_at.strftime("%d.%m %H:%M")


Builder.load_string("""
#:import _ENTRY_MIN_HEIGHT syslog_messages._ENTRY_MIN_HEIGHT
#:import _ENTRY_LINE_HEIGHT syslog_messages._ENTRY_LINE_HEIGHT
#:import ScrollableList scrollable_list.ScrollableList
<SyslogEntry>:
    orientation: 'vertical'
    size_hint: 1, None
    height: _ENTRY_MIN_HEIGHT
    padding: [8, 0, 8, 4]  # top=0: flush list; bottom=4: space after divider line
    spacing: 2

    canvas.after:
        Color:
            rgba: 77/256.0, 77/256.0, 76/256.0, 1
        Line:
            points: self.pos[0]+4, self.pos[1], self.pos[0] + self.size[0]-4, self.pos[1]

    BoxLayout:
        orientation: 'horizontal'
        size_hint_y: None
        height: 14
        spacing: 4

        Label:
            text: root.msg_time
            font_size: 10
            font_name: 'assets/FiraMono-Regular.ttf'
            color: root.entry_color
            halign: 'left'
            valign: 'center'
            text_size: self.size
            size_hint_x: None
            width: 82

        Label:
            text: root.msg_host
            font_size: 10
            font_name: 'assets/FiraMono-Regular.ttf'
            color: root.entry_color
            halign: 'left'
            valign: 'center'
            text_size: self.size
            size_hint_x: 1
            shorten: True
            shorten_from: 'right'

        Label:
            text: root.msg_program + ' (' + root.msg_facility + ')'
            font_size: 10
            font_name: 'assets/FiraMono-Regular.ttf'
            color: root.entry_color
            halign: 'right'
            valign: 'center'
            text_size: self.size
            size_hint_x: 1
            shorten: True
            shorten_from: 'left'

    Label:
        text: root.msg_text
        font_size: 12
        color: root.entry_color
        halign: 'left'
        valign: 'top'
        text_size: [self.width, self.height]
        size_hint_y: None
        height: root.msg_text_height

<SyslogMessagePanel>:
    orientation: 'vertical'
    padding: [4, 0, 4, 4]
    spacing: 2

    canvas.before:
        Color:
            rgba: root.border_color
        Line:
            points: 
                root.pos[0] + root.size[0] - 2, root.pos[1] + 4, \\ 
                root.pos[0] + root.size[0] - 2, root.pos[1] + root.size[1] - 12

    # ScrollableList overlays ▲/▼ arrows on the RecycleView without consuming
    # any vertical space of their own.
    ScrollableList:
        id: scroll_list
        size_hint: 1, 1

        RecycleView:
            id: rv
            data: root.entries
            viewclass: 'SyslogEntry'
            size_hint: 1, 1
            bar_width: 0

            RecycleBoxLayout:
                orientation: 'vertical'
                default_size: 0, _ENTRY_MIN_HEIGHT
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
    msg_text_height = NumericProperty(_ENTRY_LINE_HEIGHT)
    entry_color = ColorProperty(Colors.COLOR_WHITE)
    tap_callback = ObjectProperty(None, allownone=True)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos) and self.tap_callback:
            self.tap_callback()
            return True
        return super().on_touch_down(touch)


class SyslogMessagePanel(BoxLayout):
    """Kivy widget that displays a scrollable list of recent syslog messages.

    Assign :attr:`amqp_widget` and :attr:`amqp_queue` to let the panel
    subscribe to the AMQP queue and receive messages autonomously.  No
    syslog-specific code is needed in the host page or in ``amqp.py``.

    Only messages whose priority is at or above :attr:`min_priority` are shown.
    Messages that do not pass the filter are **discarded on arrival** so that
    a flood of low-priority messages can never displace high-priority ones from
    the list.  Set ``min_priority`` to a standard syslog level name (e.g.
    ``'error'``, ``'warning'``, ``'info'``) to control which messages appear.

    Messages turn grey (acknowledged) automatically after :attr:`acknowledge_after`
    seconds (0 = disabled).  Tapping an entry immediately acknowledges it.
    Acknowledged messages remain in the list — they are **never** removed by
    time alone.

    The display is capped at :attr:`max_entries` messages (default: 50).
    Messages are removed only when a new message would exceed this limit,
    starting with the oldest entry.

    Set :attr:`message_callback` to a callable ``(SyslogMessage) -> None`` to
    be notified of each newly received message (e.g. to update tab notifications
    in the host page).
    """

    entries = ListProperty()
    border_color = ColorProperty(Colors.COLOR_GREY)
    min_priority = StringProperty('error')
    acknowledge_after = NumericProperty(3600)  # seconds; 0 = never auto-acknowledge
    max_entries = NumericProperty(50)          # maximum number of messages displayed

    amqp_widget = ObjectProperty(None, allownone=True)
    amqp_queue = StringProperty('')
    message_callback = ObjectProperty(None, allownone=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._messages = []
        self._refresh_clock = Clock.schedule_interval(
            lambda dt: self._refresh_entries(), 30
        )

    def __del__(self):
        if self._refresh_clock:
            self._refresh_clock.cancel()

    def on_kv_post(self, base_widget):
        """Bind scroll-position tracking after KV rules are applied."""
        self.ids.scroll_list.bind_scroll_view(self.ids.rv)

    def on_amqp_widget(self, _instance, _value):
        """Subscribe to the AMQP queue when the widget becomes available."""
        self._update_amqp_subscription()

    def on_amqp_queue(self, _instance, _value):
        """Subscribe (or re-subscribe) when the queue name changes."""
        self._update_amqp_subscription()

    def _update_amqp_subscription(self):
        """Register this panel as a consumer on the configured AMQP queue."""
        if self.amqp_widget and self.amqp_queue:
            self.amqp_widget.register_queue_consumer(
                self.amqp_queue, self._on_amqp_message
            )

    def _on_amqp_message(self, channel, method, properties, _body):
        """Raw pika consumer callback — parses the message and dispatches to the UI thread.

        :param channel: Pika channel used to ACK the delivery.
        :param method: pika Basic.Deliver frame; routing_key is used as host fallback.
        :param properties: pika BasicProperties; syslog-ng places message data in headers.
        :param _body: Message body (empty for syslog-ng AMQP messages; unused).
        """
        try:
            msg = SyslogMessage.from_amqp(method, properties)
            if msg:
                Clock.schedule_once(lambda dt: self.add_message(msg))
            channel.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            Logger.error("Syslog: Error processing AMQP message: %s", str(e))
            channel.basic_ack(delivery_tag=method.delivery_tag)

    def on_min_priority(self, _instance, _value):
        """Re-render when the severity filter changes."""
        self._refresh_entries()

    def on_acknowledge_after(self, _instance, _value):
        """Re-render when the auto-acknowledge timeout changes."""
        self._refresh_entries()

    def on_max_entries(self, _instance, value):
        """Trim the message store and re-render when the limit is reduced."""
        limit = int(value)
        if len(self._messages) > limit:
            self._messages = self._messages[:limit]
        self._refresh_entries()

    def add_message(self, msg: SyslogMessage):
        """Add a new syslog message to the internal buffer and update the display.

        Messages that do not pass the current :attr:`min_priority` filter are
        discarded immediately so that high-priority messages are never displaced
        from the visible list by a flood of low-priority ones.

        The buffer is capped at :attr:`max_entries`; the oldest message is
        dropped when the limit would be exceeded.

        Must be called on the Kivy main thread.
        """
        if not _passes_filter(msg.priority, self.min_priority):
            return
        self._messages.insert(0, msg)
        limit = int(self.max_entries)
        if len(self._messages) > limit:
            self._messages = self._messages[:limit]
        self._refresh_entries()

        if self.message_callback:
            self.message_callback(msg)

    def _acknowledge_message(self, msg: SyslogMessage):
        """Acknowledge a message and refresh the display."""
        msg.acknowledge()
        self._refresh_entries()

    def _refresh_entries(self):
        """Rebuild the RecycleView data list from stored messages."""
        if self.acknowledge_after > 0:
            cutoff = datetime.datetime.now() - datetime.timedelta(
                seconds=self.acknowledge_after
            )
            for msg in self._messages:
                if msg.received_at < cutoff:
                    msg.acknowledge()

        self.entries = [
            {
                'size_hint': [1, None],
                'height': _entry_height(msg.message),
                'msg_time': msg.formatted_time(),
                'msg_host': msg.host,
                'msg_facility': msg.facility,
                'msg_program': msg.program,
                'msg_text': msg.message,
                'msg_text_height': _msg_lines(msg.message) * _ENTRY_LINE_HEIGHT,
                'entry_color': msg.display_color(),
                'tap_callback': functools.partial(self._acknowledge_message, msg),
            }
            for msg in self._messages
        ]
        Clock.schedule_once(lambda dt: self._do_post_refresh())

    def _do_post_refresh(self):
        """Refresh the RecycleView data and update scroll indicators."""
        rv = self.ids.rv
        rv.refresh_from_data()
        self.ids.scroll_list.update_indicators(rv)
