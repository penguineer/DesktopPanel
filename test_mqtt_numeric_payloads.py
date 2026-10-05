"""Regression tests for numeric MQTT payload handling."""

from types import SimpleNamespace

from power import PowerWidget
from temperature import TemperatureView


def test_power_empty_payload_means_unavailable():
    state = SimpleNamespace(power=12.0, value_error=ValueError("old"))

    PowerWidget._update_power(state, "")

    assert state.power is None
    assert state.value_error is None


def test_power_whitespace_payload_means_unavailable():
    state = SimpleNamespace(power=12.0, value_error=ValueError("old"))

    PowerWidget._update_power(state, "  \t\n ")

    assert state.power is None
    assert state.value_error is None


def test_power_nonempty_payload_is_still_validated():
    state = SimpleNamespace(power=None, value_error=None)

    PowerWidget._update_power(state, " 42.5 ")
    assert state.power == 42.5
    assert state.value_error is None

    PowerWidget._update_power(state, "not-a-number")
    assert state.power is None
    assert isinstance(state.value_error, ValueError)


def test_temperature_empty_payload_means_unavailable_without_refreshing_age():
    state = SimpleNamespace(_temp=42.0, value_error=ValueError("old"), measure_instant=123.0)

    TemperatureView._update_temperature(state, "")

    assert state._temp is None
    assert state.value_error is None
    assert state.measure_instant == 123.0


def test_temperature_whitespace_payload_means_unavailable_without_refreshing_age():
    state = SimpleNamespace(_temp=42.0, value_error=ValueError("old"), measure_instant=123.0)

    TemperatureView._update_temperature(state, "  \t\n ")

    assert state._temp is None
    assert state.value_error is None
    assert state.measure_instant == 123.0


def test_temperature_valid_payload_refreshes_measurement_age(monkeypatch):
    state = SimpleNamespace(_temp=None, value_error=None, measure_instant=123.0)
    monkeypatch.setattr("temperature.time.time", lambda: 456.0)

    TemperatureView._update_temperature(state, " 41.5 ")

    assert state._temp == 41.5
    assert state.value_error is None
    assert state.measure_instant == 456.0


def test_temperature_nonempty_invalid_payload_remains_an_error():
    state = SimpleNamespace(_temp=42.0, value_error=None, measure_instant=123.0)

    TemperatureView._update_temperature(state, "not-a-number")

    assert state._temp is None
    assert isinstance(state.value_error, ValueError)
    assert state.measure_instant == 123.0
