"""Kivy presentation for operational events."""

import datetime
import functools
import json

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import (
    BooleanProperty,
    ColorProperty,
    ListProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.boxlayout import BoxLayout

from operational_events import JarvisAlertEvent, SourceStateEvent, SyslogEvent
from scrollable_list import ScrollableList  # noqa: F401 - used by KV
from timewidget import humanize_duration_millis


class Colors:
    COLOR_WHITE = [1, 1, 1, 1]
    COLOR_GREY = [77 / 256, 77 / 256, 76 / 256, 1]
    COLOR_YELLOW = [249 / 256, 176 / 256, 0 / 256, 1]
    COLOR_RED = [228 / 256, 5 / 256, 41 / 256, 1]


_ENTRY_PADDING_V = 4
_ENTRY_META_HEIGHT = 14
_ENTRY_SPACING = 2
_ENTRY_LINE_HEIGHT = 16
_ENTRY_CHARS_PER_LINE = 50
_ENTRY_DETAILS_LINE_HEIGHT = 14
_ENTRY_DETAILS_PADDING = 4

_CRITICAL_SEVERITIES = frozenset(("critical", "crit", "alert", "emergency", "emerg"))
_ERROR_SEVERITIES = frozenset(("error", "err"))


def _wrapped_lines(text, chars_per_line=_ENTRY_CHARS_PER_LINE):
    if not text:
        return 1
    physical_lines = text.splitlines() or [""]
    return sum(max(1, -(-len(line) // chars_per_line)) for line in physical_lines)


def _formatted_timestamp(timestamp_ns):
    dt = datetime.datetime.fromtimestamp(timestamp_ns / 1_000_000_000)
    now = datetime.datetime.now()
    if dt.date() == now.date():
        return dt.strftime("%H:%M")
    return dt.strftime("%d.%m %H:%M")


def _event_color(event):
    if isinstance(event, SourceStateEvent):
        return Colors.COLOR_RED
    if isinstance(event, (SyslogEvent, JarvisAlertEvent)):
        if event.severity in _CRITICAL_SEVERITIES:
            return Colors.COLOR_RED
        if event.severity in _ERROR_SEVERITIES or event.severity in ("warning", "warn"):
            return Colors.COLOR_YELLOW
    return Colors.COLOR_WHITE


def _event_details(event):
    if isinstance(event, SyslogEvent):
        return json.dumps(dict(event.labels), sort_keys=True, indent=2, ensure_ascii=False)
    if isinstance(event, JarvisAlertEvent):
        payload = {
            "cluster": event.cluster_name,
            "fingerprint": event.fingerprint,
            "status": event.status,
            "startsAt": event.starts_at,
            "resolvedAt": event.resolved_at,
            "stale": event.stale,
            "labels": dict(event.labels),
            "annotations": dict(event.annotations),
        }
        return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False)
    if isinstance(event, SourceStateEvent):
        return "source: %s\nstate: %s" % (event.source, event.state)
    return "source: %s" % event.source


def _combined_operational_events(loki_events, jarvis_events):
    """Return health, actionable Jarvis, then the chronological timeline."""

    source_states = [
        event
        for event in list(loki_events) + list(jarvis_events)
        if isinstance(event, SourceStateEvent)
    ]
    source_rank = {"loki": 0, "jarvis": 1}
    source_states.sort(
        key=lambda event: (
            source_rank.get(event.source, len(source_rank)),
            event.source,
            event.event_id,
        )
    )

    active_jarvis = sorted(
        (
            event
            for event in jarvis_events
            if isinstance(event, JarvisAlertEvent) and event.needs_attention
        ),
        key=lambda event: (-event.starts_at_ns, event.event_id),
    )

    timeline = [
        event
        for event in list(loki_events) + list(jarvis_events)
        if not isinstance(event, SourceStateEvent)
        and not (
            isinstance(event, JarvisAlertEvent)
            and event.needs_attention
        )
    ]
    timeline.sort(key=lambda event: (-event.timestamp_ns, event.event_id))
    return source_states + active_jarvis + timeline


def _entry_height(summary, details="", expanded=False):
    summary_height = _wrapped_lines(summary) * _ENTRY_LINE_HEIGHT
    height = _ENTRY_PADDING_V + _ENTRY_META_HEIGHT + _ENTRY_SPACING + summary_height
    if expanded:
        height += (
            _ENTRY_SPACING
            + _ENTRY_DETAILS_PADDING
            + _wrapped_lines(details) * _ENTRY_DETAILS_LINE_HEIGHT
        )
    return height


Builder.load_string("""
#:import _ENTRY_LINE_HEIGHT operational_event_panel._ENTRY_LINE_HEIGHT
#:import ScrollableList scrollable_list.ScrollableList

<OperationalEventRow>:
    orientation: 'vertical'
    size_hint: 1, None
    padding: [8, 0, 8, 4]
    spacing: 2

    canvas.after:
        Color:
            rgba: 77/256.0, 77/256.0, 76/256.0, 1
        Line:
            points: self.pos[0]+4, self.pos[1]+4, self.pos[0] + self.size[0]-4, self.pos[1]+4

    BoxLayout:
        orientation: 'horizontal'
        size_hint_y: None
        height: 14
        spacing: 4

        Label:
            text: root.event_time
            font_size: 10
            font_name: 'assets/FiraMono-Regular.ttf'
            color: root.entry_color
            halign: 'left'
            valign: 'center'
            text_size: self.size
            size_hint_x: None
            width: 82

        Label:
            text: root.source_annotation
            font_size: 10
            font_name: 'assets/FiraMono-Regular.ttf'
            color: root.entry_color
            halign: 'left'
            valign: 'center'
            text_size: self.size
            size_hint_x: None
            width: 90
            shorten: True
            shorten_from: 'center'

        Label:
            text: root.meta_text
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
        text: root.summary
        font_size: 12
        color: root.entry_color
        halign: 'left'
        valign: 'top'
        text_size: [self.width, self.height]
        size_hint_y: None
        height: root.summary_height

    Label:
        text: root.details
        font_size: 10
        font_name: 'assets/FiraMono-Regular.ttf'
        color: 0.7, 0.7, 0.7, 1
        halign: 'left'
        valign: 'top'
        text_size: [self.width, self.height]
        size_hint_y: None
        height: root.details_height if root.expanded else 0
        opacity: 1 if root.expanded else 0

<OperationalEventPanel>:
    orientation: 'vertical'
    padding: [4, 0, 4, 4]
    spacing: 2

    canvas.before:
        Color:
            rgba: root.border_color
        Line:
            points:
                root.pos[0] + root.size[0] - 2, root.pos[1] + 4, \
                root.pos[0] + root.size[0] - 2, root.pos[1] + root.size[1] - 12

    ScrollableList:
        id: scroll_list
        size_hint: 1, 1

        RecycleView:
            id: rv
            data: root.entries
            viewclass: 'OperationalEventRow'
            size_hint: 1, 1
            bar_width: 0

            RecycleBoxLayout:
                orientation: 'vertical'
                default_size: 0, 36
                default_size_hint: 1, None
                size_hint_y: None
                height: self.minimum_height
""")


class OperationalEventRow(BoxLayout):
    event_time = StringProperty("")
    source_annotation = StringProperty("")
    meta_text = StringProperty("")
    summary = StringProperty("")
    details = StringProperty("")
    summary_height = NumericProperty(_ENTRY_LINE_HEIGHT)
    details_height = NumericProperty(0)
    entry_color = ColorProperty(Colors.COLOR_WHITE)
    expanded = BooleanProperty(False)
    tap_callback = ObjectProperty(None, allownone=True)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos) and self.tap_callback:
            self.tap_callback()
            return True
        return super().on_touch_down(touch)


class OperationalEventPanel(BoxLayout):
    """Combined presentation of independent Loki and Jarvis event stores."""

    entries = ListProperty([])
    store = ObjectProperty(None, allownone=True)
    jarvis_store = ObjectProperty(None, allownone=True)
    border_color = ColorProperty(Colors.COLOR_GREY)

    def __init__(self, **kwargs):
        self._bound_store = None
        self._bound_jarvis_store = None
        self._age_clock = None
        super().__init__(**kwargs)

    def on_kv_post(self, _base_widget):
        self.ids.scroll_list.bind_scroll_view(self.ids.rv)
        self._refresh_entries()

    def on_store(self, _instance, store):
        if self._bound_store is not None:
            self._bound_store.unbind(events=self._on_store_events)
        self._bound_store = store
        if store is not None:
            store.bind(events=self._on_store_events)
        self._refresh_entries()

    def on_jarvis_store(self, _instance, store):
        if self._bound_jarvis_store is not None:
            self._bound_jarvis_store.unbind(events=self._on_store_events)
        self._bound_jarvis_store = store
        if store is not None:
            store.bind(events=self._on_store_events)
        self._refresh_entries()

    def _on_store_events(self, _store, _events):
        self._refresh_entries()

    def _store_for_event(self, event):
        if isinstance(event, JarvisAlertEvent):
            return self.jarvis_store
        if isinstance(event, SourceStateEvent) and event.source == "jarvis":
            return self.jarvis_store
        return self.store

    def _toggle_expanded(self, event):
        store = self._store_for_event(event)
        if store is None:
            return
        store.toggle_expanded(event.event_id)
        self._refresh_entries()

    def _combined_events(self):
        loki_events = list(self.store.events) if self.store is not None else []
        jarvis_events = (
            list(self.jarvis_store.events)
            if self.jarvis_store is not None
            else []
        )
        return _combined_operational_events(loki_events, jarvis_events)

    def _refresh_entries(self):
        if not self.ids:
            self.entries = []
            return

        events = self._combined_events()
        has_active_jarvis = any(
            isinstance(event, JarvisAlertEvent) and event.needs_attention
            for event in events
        )
        if has_active_jarvis and self._age_clock is None:
            self._age_clock = Clock.schedule_interval(
                lambda _dt: self._refresh_entries(),
                1,
            )
        elif not has_active_jarvis and self._age_clock is not None:
            self._age_clock.cancel()
            self._age_clock = None

        data = []
        now_ns = int(datetime.datetime.now().timestamp() * 1_000_000_000)
        for event in events:
            store = self._store_for_event(event)
            expanded = store.is_expanded(event.event_id) if store is not None else False
            details = _event_details(event)
            summary_lines = _wrapped_lines(event.summary)
            detail_lines = _wrapped_lines(details) if expanded else 0

            if isinstance(event, SyslogEvent):
                meta_text = "%s (%s) · %s" % (
                    event.application,
                    event.facility,
                    event.severity,
                )
                event_time = _formatted_timestamp(event.timestamp_ns)
            elif isinstance(event, JarvisAlertEvent):
                stale = " · stale" if event.stale else ""
                meta_text = "%s · %s%s" % (
                    event.status,
                    event.severity or "unknown",
                    stale,
                )
                if event.needs_attention:
                    age_millis = max(0, (now_ns - event.starts_at_ns) // 1_000_000)
                    event_time = humanize_duration_millis(age_millis)
                else:
                    event_time = _formatted_timestamp(event.timestamp_ns)
            elif isinstance(event, SourceStateEvent):
                meta_text = event.state
                event_time = _formatted_timestamp(event.timestamp_ns)
            else:
                meta_text = event.source
                event_time = _formatted_timestamp(event.timestamp_ns)

            data.append({
                "size_hint": [1, None],
                "height": _entry_height(event.summary, details, expanded),
                "event_time": event_time,
                "source_annotation": event.source_annotation,
                "meta_text": meta_text,
                "summary": event.summary,
                "details": details,
                "summary_height": summary_lines * _ENTRY_LINE_HEIGHT,
                "details_height": detail_lines * _ENTRY_DETAILS_LINE_HEIGHT
                                  + (_ENTRY_DETAILS_PADDING if expanded else 0),
                "entry_color": _event_color(event),
                "expanded": expanded,
                "tap_callback": functools.partial(
                    self._toggle_expanded,
                    event,
                ),
            })

        self.entries = data
        Clock.schedule_once(lambda _dt: self._post_refresh())

    def _post_refresh(self):
        rv = self.ids.rv
        rv.refresh_from_data()
        self.ids.scroll_list.update_indicators(rv)
