""" Pytest tests for the power module """

import pytest

from power import compute_energy_segments, compute_bar_values, build_power_flux_query


class TestComputeEnergySegments:
    def test_empty_points(self):
        assert compute_energy_segments([]) == []

    def test_single_point_no_segments(self):
        assert compute_energy_segments([(0, 100)]) == []

    def test_two_points_normal(self):
        points = [(0, 0), (10, 100)]
        segments = compute_energy_segments(points)
        assert len(segments) == 1
        t0, t1, de = segments[0]
        assert t0 == 0
        assert t1 == 10
        assert de == 100

    def test_multiple_points(self):
        points = [(0, 0), (10, 50), (20, 150)]
        segments = compute_energy_segments(points)
        assert len(segments) == 2
        assert segments[0] == (0, 10, 50)
        assert segments[1] == (10, 20, 100)

    def test_wrap_around_skipped(self):
        # Energy drops from 1000 to 50: wrap-around, skip that interval
        points = [(0, 500), (10, 1000), (20, 50), (30, 200)]
        segments = compute_energy_segments(points)
        assert len(segments) == 2
        assert segments[0] == (0, 10, 500)
        assert segments[1] == (20, 30, 150)

    def test_flat_value_zero_delta(self):
        # No energy consumed between the two readings
        points = [(0, 100), (10, 100)]
        segments = compute_energy_segments(points)
        assert len(segments) == 1
        assert segments[0] == (0, 10, 0)

    def test_non_monotonic_time_skipped(self):
        # A pair with the same timestamp is skipped; the next pair proceeds normally.
        # points: (0,0)→(0,100) skipped (dt=0); (0,100)→(10,200) kept → de=100
        points = [(0, 0), (0, 100), (10, 200)]
        segments = compute_energy_segments(points)
        assert len(segments) == 1
        assert segments[0] == (0, 10, 100)

    def test_unequal_time_intervals(self):
        points = [(0, 0), (5, 100), (30, 400)]
        segments = compute_energy_segments(points)
        assert len(segments) == 2
        assert segments[0] == (0, 5, 100)
        assert segments[1] == (5, 30, 300)


class TestComputeBarValues:
    def test_empty_segments_returns_zeros(self):
        bars = compute_bar_values([], n_bars=3, bar_duration=10, now=100)
        assert len(bars) == 3
        assert all(w == 0.0 for w in bars)

    def test_zero_bars(self):
        segments = [(0, 10, 100)]
        bars = compute_bar_values(segments, n_bars=0, bar_duration=10, now=100)
        assert bars == []

    def test_single_bar_full_coverage(self):
        # Segment exactly covers the bar window
        # bar: [90, 100], segment: [90, 100], energy 100 Wmin, duration 10 s
        # 100 Wmin * 60 / 10 s = 600 W
        segments = [(90, 100, 100)]
        bars = compute_bar_values(segments, n_bars=1, bar_duration=10, now=100)
        assert len(bars) == 1
        assert abs(bars[0] - 600.0) < 1e-9

    def test_single_bar_real_world(self):
        # Real-world sanity check: 200 W for 5 minutes = 1000 Wmin over 300 s
        # 1000 Wmin * 60 / 300 s = 200 W
        segments = [(0, 300, 1000)]
        bars = compute_bar_values(segments, n_bars=1, bar_duration=300, now=300)
        assert len(bars) == 1
        assert abs(bars[0] - 200.0) < 1e-9

    def test_segment_partial_overlap(self):
        # bar window [90, 100], segment [85, 100] – overlap is [90, 100] = 10 s out of 15 s
        # Energy proportion: 200 * (10/15) = 133.33 Wmin → 133.33 * 60 / 10 = 800 W
        segments = [(85, 100, 200)]
        bars = compute_bar_values(segments, n_bars=1, bar_duration=10, now=100)
        assert abs(bars[0] - (200 * (10 / 15) * 60 / 10)) < 1e-9

    def test_two_bars_ordering(self):
        # bars[0] is oldest, bars[1] is newest
        # now=20, bar_duration=10:  bar0=[0,10], bar1=[10,20]
        # segment [0, 10, 50] covers bar0; segment [10, 20, 150] covers bar1
        # 50 Wmin * 60 / 10 s = 300 W;  150 Wmin * 60 / 10 s = 900 W
        segments = [(0, 10, 50), (10, 20, 150)]
        bars = compute_bar_values(segments, n_bars=2, bar_duration=10, now=20)
        assert abs(bars[0] - 300.0) < 1e-9
        assert abs(bars[1] - 900.0) < 1e-9

    def test_no_data_for_oldest_bars(self):
        # Segment only covers the newest bar; older bars have zero watts
        # now=30, bar_duration=10, n_bars=3: bar0=[0,10], bar1=[10,20], bar2=[20,30]
        # 60 Wmin * 60 / 10 s = 360 W
        segments = [(20, 30, 60)]
        bars = compute_bar_values(segments, n_bars=3, bar_duration=10, now=30)
        assert bars[0] == 0.0
        assert bars[1] == 0.0
        assert abs(bars[2] - 360.0) < 1e-9

    def test_watt_hours_per_hour_equivalence(self):
        # Same average power produces the same watt value regardless of bar duration.
        # 100 Wmin in 10 s → 100*60/10 = 600 W; same rate as 200 Wmin in 20 s → 200*60/20 = 600 W
        segments_a = [(0, 10, 100)]
        bars_a = compute_bar_values(segments_a, n_bars=1, bar_duration=10, now=10)
        segments_b = [(0, 20, 200)]
        bars_b = compute_bar_values(segments_b, n_bars=1, bar_duration=20, now=20)
        assert abs(bars_a[0] - bars_b[0]) < 1e-9

    def test_custom_now(self):
        # Verify that 'now' is used as the reference time
        # 100 Wmin * 60 / 10 s = 600 W
        now = 1_000_000
        segments = [(now - 10, now, 100)]
        bars = compute_bar_values(segments, n_bars=1, bar_duration=10, now=now)
        assert abs(bars[0] - 600.0) < 1e-9


class TestBuildPowerFluxQuery:
    def test_basic_query_structure(self):
        q = build_power_flux_query("mybucket", "myms", "myfield", 10, 300, 2)
        lines = q.splitlines()
        assert lines[0] == 'from(bucket: "mybucket")'
        assert lines[1] == '  |> range(start: -3600s)'  # (10+2)*300 = 3600
        assert lines[2] == '  |> filter(fn: (r) => r._measurement == "myms")'
        assert lines[3] == '  |> filter(fn: (r) => r._field == "myfield")'
        assert lines[-1] == '  |> sort(columns: ["_time"])'

    def test_measurement_before_field_filter(self):
        # Measurement filter must precede field filter (bucket→measurement→field order)
        q = build_power_flux_query("mybucket", "myms", "myfield", 10, 300, 2)
        lines = q.splitlines()
        ms_idx = next(i for i, l in enumerate(lines) if 'r._measurement' in l)
        field_idx = next(i for i, l in enumerate(lines) if 'r._field' in l)
        assert ms_idx < field_idx

    def test_string_bar_duration_produces_correct_range(self):
        # bar_duration configured as a JSON string ("300") must not cause
        # Python string multiplication that inflates the range value.
        q = build_power_flux_query("mybucket", "myms", "myfield", 10, "300", 2)
        assert '  |> range(start: -3600s)' in q

    def test_buffer_adds_to_range(self):
        # n_buffer extra bars are included in the time range query
        q_no_buf = build_power_flux_query("b", "myms", "f", 10, 60, 0)
        q_buf = build_power_flux_query("b", "myms", "f", 10, 60, 2)
        assert '|> range(start: -600s)' in q_no_buf   # 10*60
        assert '|> range(start: -720s)' in q_buf      # 12*60

