""" Module for power display """

import time as _time

import isodate

from kivy import Logger
from kivy.clock import Clock
from kivy.graphics import Color, Line, Rectangle
from kivy.lang import Builder
from kivy.properties import ObjectProperty, DictProperty, NumericProperty, ListProperty
from kivy.uix.label import Label
from kivy.uix.relativelayout import RelativeLayout


class Colors:
    # Base color definitions
    COLOR_BLACK = [0, 0, 0, 1]
    COLOR_WHITE = [1, 1, 1, 1]
    COLOR_GREY = [77 / 256, 77 / 256, 76 / 256, 1]
    COLOR_GREEN = [0 / 256, 163 / 256, 86 / 256, 1]
    COLOR_YELLOW = [249 / 256, 176 / 256, 0 / 256, 1]
    COLOR_RED = [228 / 256, 5 / 256, 41 / 256, 1]


def parse_duration_seconds(value) -> float:
    """Parse a duration value to seconds.

    Accepts:

    * A number — interpreted as **seconds** directly.
    * An ISO 8601 duration string (e.g. ``"PT5M"``, ``"PT1H"``,
      ``"PT30S"``) — parsed via :mod:`isodate` and converted to seconds.

    :raises ValueError: if the value cannot be parsed.
    """
    if isinstance(value, (int, float)):
        return float(value)
    try:
        duration = isodate.parse_duration(str(value))
        return duration.total_seconds()
    except isodate.isoerror.ISO8601Error as e:
        raise ValueError(f"Cannot parse duration value: {value!r}") from e


def compute_energy_segments(points):
    """Convert sorted (timestamp, cumulative_energy_wmin) pairs to energy segments.

    Returns a list of (t_start, t_end, energy_wmin) tuples representing the
    energy consumed in each interval.  Intervals where the cumulative energy
    value decreases (wrap-around or device reset) are skipped.

    :param points: Sorted list of (unix_timestamp, cumulative_wmin) pairs.
    :return: List of (t_start, t_end, delta_wmin) tuples.
    """
    segments = []
    for i in range(1, len(points)):
        t0, e0 = points[i - 1]
        t1, e1 = points[i]
        dt = t1 - t0
        if dt <= 0:
            continue
        de = e1 - e0
        if de < 0:
            # wrap-around or device reset – skip this interval
            continue
        segments.append((t0, t1, de))
    return segments


def compute_bar_values(segments, n_bars, bar_duration, now=None):
    """Distribute energy segments into fixed-width time bars.

    Each bar covers *bar_duration* seconds.  The energy values from the Shelly
    Plug are cumulative watt-minutes (Wmin).  The returned value is the average
    power in watts for the bar's time window:

        watts = watt_minutes_in_bar * 60 / bar_duration_seconds

    bars[0] is the oldest (leftmost), bars[n_bars-1] is the newest (rightmost).

    :param segments: List of (t_start, t_end, delta_wmin) from
        :func:`compute_energy_segments`.
    :param n_bars: Number of bars to compute.
    :param bar_duration: Duration covered by each bar in seconds.
    :param now: Reference timestamp (Unix epoch).  Defaults to the current time.
    :return: List of *n_bars* float values representing average watts per bar.
    """
    if now is None:
        now = _time.time()

    bars = []
    for i in range(n_bars):
        bar_end = now - (n_bars - 1 - i) * bar_duration
        bar_start = bar_end - bar_duration

        energy = 0.0
        for seg_start, seg_end, seg_energy in segments:
            overlap_start = max(bar_start, seg_start)
            overlap_end = min(bar_end, seg_end)
            if overlap_end > overlap_start:
                seg_dur = seg_end - seg_start
                overlap_dur = overlap_end - overlap_start
                energy += seg_energy * (overlap_dur / seg_dur)

        bars.append(energy * 60 / bar_duration)

    return bars


Builder.load_string("""
#:import Colors power.Colors

<PowerWidget>:
    size_hint: None, None
    height: 50
    width: 110

    Label:
        id: _num_label
        text: '---' if root.power is None else "%d" % root.power
        font_size: 32
        font_name: 'assets/FiraMono-Regular.ttf'
        size_hint: None, None
        size: self.texture_size
        x: root.width / 2 - (self.width + _unit_label.width + 2) / 2
        y: 0
        color: Colors.COLOR_RED if root.value_error else \
               Colors.COLOR_GREY if root.power is None else \
               Colors.COLOR_WHITE

    Label:
        id: _unit_label
        text: 'W'
        font_size: 16
        font_name: 'assets/FiraMono-Regular.ttf'
        size_hint: None, None
        size: self.texture_size
        x: _num_label.right + 2
        y: _num_label.y + 0.9 * (_num_label.height - _unit_label.height)
        color: Colors.COLOR_RED if root.value_error else \
               Colors.COLOR_GREY if root.power is None else \
               Colors.COLOR_WHITE
""")


class PowerWidget(RelativeLayout):
    mqttc = ObjectProperty(None)
    conf = DictProperty()

    power = NumericProperty(None, allownone=True)
    value_error = ObjectProperty(None, allownone=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def on_conf(self, _instance, _conf: list) -> None:
        self._update_mqtt()

    def on_mqttc(self, _instance, _mqttc) -> None:
        self._update_mqtt()

    def _update_mqtt(self):
        if not self.conf or not self.mqttc:
            return

        topic = self.conf.get("topic", None)
        self.mqttc.subscribe(topic, self._mqtt_callback)

    def _mqtt_callback(self, _client, _userdata, message):
        payload = message.payload.decode("utf-8")
        Clock.schedule_once(lambda dt: self._update_power(payload))

    def _update_power(self, payload):
        try:
            self.value_error = None
            self.power = float(payload)
        except ValueError as e:
            Logger.error(e)
            self.value_error = e
            self.power = None


def compute_bar_layout(available_px, display_duration_s=None, bar_duration_s=300.0,
                       fallback_bar_width=8):
    """Compute bar layout parameters from available pixel width and durations.

    When *display_duration_s* is provided, bars are sized to fill the full time
    span within the available width.  If the desired number of bars exceeds the
    available pixels, *bar_duration_s* is scaled up so that every bar occupies at
    least one pixel.

    When *display_duration_s* is ``None``, the legacy fallback is used:
    ``floor(available_px / (fallback_bar_width + 1))`` bars.

    :param available_px: Available pixel width (widget width minus frame border).
    :param display_duration_s: Total time span to display in seconds, or ``None``
        for the legacy fixed-width fallback.
    :param bar_duration_s: Desired time covered by each bar in seconds.
    :param fallback_bar_width: Bar width in pixels used when *display_duration_s*
        is ``None``.
    :return: Tuple ``(n_bars, effective_bar_dur_s, slot_width_px, bar_width_px)``.
        *slot_width_px* is the full float width per bar slot (bar + gap).
        *bar_width_px* is the drawable float width of the bar itself.
    """
    if available_px <= 0:
        return 0, float(bar_duration_s), 0.0, 0.0

    if display_duration_s is not None and display_duration_s > 0 and bar_duration_s > 0:
        n_bars = max(1, round(display_duration_s / bar_duration_s))
        # Scale up bar_duration when more bars would be needed than pixels allow
        if n_bars > available_px:
            n_bars = available_px
            bar_duration_s = display_duration_s / n_bars
    else:
        # Legacy mode: fit bars of fallback_bar_width with a 1 px gap
        n_bars = max(0, available_px // (fallback_bar_width + 1))

    if n_bars <= 0:
        return 0, float(bar_duration_s), 0.0, 0.0

    slot_w = available_px / n_bars
    # Keep a 1 px gap between bars when space allows; minimum bar width is 1 px
    bar_w = max(1.0, slot_w - 1.0)

    return n_bars, float(bar_duration_s), slot_w, bar_w


def build_power_flux_query(bucket, measurement, field, n_bars, bar_duration,
                           n_buffer):
    """Build the Flux query string for power history data.

    :param bucket: InfluxDB bucket name.
    :param measurement: InfluxDB measurement name.
    :param field: InfluxDB field name holding cumulative energy values.
    :param n_bars: Number of bars to cover.
    :param bar_duration: Duration of each bar in seconds (int or numeric string).
    :param n_buffer: Extra bars to fetch beyond *n_bars* for boundary accuracy.
    :return: Flux query string.
    """
    time_range = (n_bars + n_buffer) * int(bar_duration)
    lines = [
        f'from(bucket: "{bucket}")',
        f'  |> range(start: -{time_range}s)',
        f'  |> filter(fn: (r) => r._measurement == "{measurement}")',
        f'  |> filter(fn: (r) => r._field == "{field}")',
        f'  |> sort(columns: ["_time"])',
    ]
    return '\n'.join(lines)


class PowerHistoryGraph(RelativeLayout):
    """Bar chart showing power consumption history from InfluxDB.

    Bars are drawn oldest-left / newest-right.  Each bar represents the
    average power (watts = watt_minutes * 60 / bar_duration_seconds) over a
    configurable time window (*bar_duration* seconds).  The widget queries
    InfluxDB periodically and redraws via canvas instructions.

    Configuration keys (``conf`` dict):

    ``bucket``
        InfluxDB bucket name (required).
    ``measurement``
        InfluxDB measurement name (required).
    ``field``
        InfluxDB field name holding cumulative energy in watt-minutes (Wmin) (required).
    ``display_duration``
        Total time span shown by the graph, as an ISO 8601 duration string (e.g.
        ``"PT2H"``) or seconds.  When set, the bar width is calculated automatically.
        Omit to use the legacy fixed-width mode (``BAR_WIDTH`` pixels per bar).
    ``bar_duration``
        Time covered by each bar as an ISO 8601 duration string (e.g. ``"PT5M"``)
        or seconds (default ``"PT5M"`` = 300 s).  If the resulting number of bars
        does not fit on screen, the duration is increased automatically.
    ``update_interval``
        Query/redraw interval as an ISO 8601 duration string or seconds
        (default ``"PT1M"`` = 60 s).
    """

    BAR_WIDTH = 8               # fallback px per bar (used when display_duration is not set)
    BAR_HIGHLIGHT_HEIGHT = 2    # px height of the yellow accent strip on top of each bar
    FRAME_BORDER = 1            # px width of structural frame lines
    # Extra bar slots fetched beyond n_bars to cover boundary conditions
    _QUERY_BUFFER_BARS = 2

    conf = DictProperty(None, allownone=True)
    influxdb_widget = ObjectProperty(None, allownone=True)

    _bars = ListProperty([])
    _max_value = NumericProperty(None, allownone=True)

    def __init__(self, **kwargs):
        self._update_event = None
        self._max_label = None
        super().__init__(**kwargs)

        self._max_label = Label(
            text='',
            font_size=12,
            font_name='assets/FiraMono-Regular.ttf',
            color=Colors.COLOR_WHITE,
            size_hint=(None, None),
            size=(75, 18),
            halign='left',
            valign='top',
            text_size=(75, 18),
        )
        self.add_widget(self._max_label)

        self.bind(conf=self._on_settings_change)
        self.bind(influxdb_widget=self._on_settings_change)
        self.bind(size=self._on_size)
        self.bind(_bars=self._redraw)
        self.bind(_max_value=self._update_max_label)

    def _on_settings_change(self, *args):
        self._stop_updates()
        if self.conf and self.influxdb_widget:
            self._start_updates()

    def _on_size(self, *args):
        self._redraw()
        self._position_max_label()
        # Trigger the initial query once the widget has valid dimensions.
        # This handles the case where _start_updates fired before layout
        # assigned a non-zero width.
        if self._update_event is not None and not self._bars and self._n_bars() > 0:
            self._query_influx()

    def _start_updates(self):
        interval_raw = self.conf.get("update_interval", "PT1M")
        try:
            interval = parse_duration_seconds(interval_raw)
        except ValueError:
            Logger.warning("PowerGraph: Invalid update_interval %r, using 60 s", interval_raw)
            interval = 60.0
        self._update_event = Clock.schedule_interval(
            lambda dt: self._query_influx(), interval)
        # Only fire immediately if the widget already has a valid width;
        # otherwise _on_size will trigger the first query once layout is done.
        if self._n_bars() > 0:
            self._query_influx()

    def _stop_updates(self):
        if self._update_event is not None:
            self._update_event.cancel()
            self._update_event = None

    def _bar_params(self):
        """Return ``(n_bars, bar_dur_s, slot_w_px, bar_w_px)`` for the current config and size.

        Delegates to :func:`compute_bar_layout` after resolving ISO 8601 durations
        from ``self.conf``.
        """
        available = max(0, int(self.width) - self.FRAME_BORDER)
        conf = self.conf or {}

        bar_dur_raw = conf.get("bar_duration", "PT5M")
        try:
            bar_dur = parse_duration_seconds(bar_dur_raw)
        except ValueError:
            Logger.warning("PowerGraph: Invalid bar_duration %r, using 300 s", bar_dur_raw)
            bar_dur = 300.0

        display_dur = None
        display_dur_raw = conf.get("display_duration", None)
        if display_dur_raw is not None:
            try:
                display_dur = parse_duration_seconds(display_dur_raw)
            except ValueError:
                Logger.warning("PowerGraph: Invalid display_duration %r, ignored",
                               display_dur_raw)

        return compute_bar_layout(available, display_dur, bar_dur, self.BAR_WIDTH)

    def _n_bars(self):
        """Return how many bars fit in the current widget width."""
        return self._bar_params()[0]

    def _query_influx(self):
        if not self.conf or not self.influxdb_widget:
            return

        bucket = self.conf.get("bucket", None)
        measurement = self.conf.get("measurement", None)
        field = self.conf.get("field", None)
        if not bucket or not measurement or not field:
            Logger.warning("PowerGraph: 'bucket', 'measurement' and 'field' must be configured")
            return

        n, bar_duration, _, _ = self._bar_params()
        if n <= 0:
            return

        flux_query = build_power_flux_query(
            bucket, measurement, field, n, bar_duration, self._QUERY_BUFFER_BARS)

        self.influxdb_widget.query(
            flux_query, self._on_data, self._on_query_error)

    def _on_data(self, tables):
        points = []
        for table in tables:
            for record in table.records:
                t = record.get_time()
                v = record.get_value()
                if t is not None and v is not None:
                    points.append((t.timestamp(), float(v)))

        points.sort(key=lambda p: p[0])

        if len(points) < 2:
            self._bars = []
            self._max_value = None
            return

        segments = compute_energy_segments(points)
        if not segments:
            self._bars = []
            self._max_value = None
            return

        n, bar_duration, _, _ = self._bar_params()
        now = _time.time()

        bar_watts = compute_bar_values(segments, n, bar_duration, now)

        max_val = max(bar_watts) if bar_watts else 0.0
        if max_val <= 0:
            self._bars = []
            self._max_value = None
            return

        self._max_value = max_val
        self._bars = [w / max_val for w in bar_watts]

    def _on_query_error(self, e):
        Logger.error("PowerGraph: InfluxDB query error: %s", str(e))

    _CANVAS_GROUP = 'phg_frame'

    def _redraw(self, *args):
        # Use remove_group instead of canvas.before.clear() to avoid removing
        # the PushMatrix/Translate instructions that RelativeLayout places in
        # canvas.before (clearing those while PopMatrix remains in canvas.after
        # causes an unbalanced RenderContext pop_state → IndexError).
        self.canvas.before.remove_group(self._CANVAS_GROUP)

        w = self.width
        h = self.height
        if w <= 0 or h <= 0:
            return

        with self.canvas.before:
            # Axis lines: bottom baseline and left y-axis only
            b = self.FRAME_BORDER
            Color(*Colors.COLOR_GREY, group=self._CANVAS_GROUP)
            Line(points=[0, 0, w, 0], width=b, group=self._CANVAS_GROUP)
            Line(points=[0, 0, 0, h], width=b, group=self._CANVAS_GROUP)

            if self._bars:
                n, _, slot_w, bar_w = self._bar_params()
                if n <= 0:
                    return

                for i, normalized in enumerate(self._bars[:n]):
                    bar_h = max(float(b), normalized * (h - b))
                    # Float x-position for visually even distribution across the
                    # full widget width — each bar occupies exactly slot_w pixels.
                    x = float(b) + i * slot_w

                    # Grey body — everything below the yellow top accent
                    grey_h = max(0.0, bar_h - self.BAR_HIGHLIGHT_HEIGHT)
                    if grey_h > 0:
                        Color(*Colors.COLOR_GREY, group=self._CANVAS_GROUP)
                        Rectangle(pos=(x, float(b)), size=(bar_w, grey_h),
                                  group=self._CANVAS_GROUP)

                    # Yellow accent strip — top 2 px of each bar
                    top_h = min(float(self.BAR_HIGHLIGHT_HEIGHT), bar_h)
                    top_y = float(b) + max(0.0, bar_h - self.BAR_HIGHLIGHT_HEIGHT)
                    Color(*Colors.COLOR_YELLOW, group=self._CANVAS_GROUP)
                    Rectangle(pos=(x, top_y), size=(bar_w, top_h),
                              group=self._CANVAS_GROUP)

    def _update_max_label(self, *args):
        if self._max_label is None:
            return
        if self._max_value is not None:
            self._max_label.text = f"{self._max_value:.0f} W"
        else:
            self._max_label.text = ''
        self._position_max_label()

    def _position_max_label(self, *args):
        if self._max_label is None:
            return
        self._max_label.pos = (
            4,
            self.height - self._max_label.height - self.FRAME_BORDER - 1)
