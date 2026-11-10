"""Tests for MQTT client lifecycle management."""

from types import SimpleNamespace
from unittest.mock import Mock

import mqtt as mqtt_module


def _mqtt_state(backend, conf=None):
    state = SimpleNamespace(
        backend=backend,
        conf=conf,
        status="connected",
        _on_connect=Mock(),
        _on_disconnect=Mock(),
        _log_error=Mock(),
    )
    state._disconnect = lambda: mqtt_module.MqttClient._disconnect(state)
    return state


def test_mqtt_teardown_disconnects_and_stops_network_thread():
    client = Mock()
    state = _mqtt_state(client)

    mqtt_module.MqttClient.teardown(state)
    mqtt_module.MqttClient.teardown(state)

    assert state.backend is None
    client.disconnect.assert_called_once_with()
    client.loop_stop.assert_called_once_with()


def test_mqtt_disconnect_stops_loop_even_if_disconnect_fails():
    client = Mock()
    client.disconnect.side_effect = OSError("connection lost")
    state = _mqtt_state(client)

    try:
        mqtt_module.MqttClient.teardown(state)
    except OSError:
        pass
    else:
        raise AssertionError("Expected disconnect failure")

    assert state.backend is None
    client.loop_stop.assert_called_once_with()


def test_mqtt_empty_config_closes_existing_client():
    old = Mock()
    state = _mqtt_state(old, conf=None)

    mqtt_module.MqttClient._connect(state)

    old.disconnect.assert_called_once_with()
    old.loop_stop.assert_called_once_with()
    assert state.backend is None


def test_mqtt_reconfiguration_replaces_old_client(monkeypatch):
    old = Mock()
    new = Mock()
    monkeypatch.setattr(mqtt_module.mqtt, "Client", lambda: new)
    state = _mqtt_state(old, conf={"host": "mqtt.example.test"})

    mqtt_module.MqttClient._connect(state)

    old.disconnect.assert_called_once_with()
    old.loop_stop.assert_called_once_with()
    new.connect.assert_called_once_with("mqtt.example.test", 1883, 60)
    new.loop_start.assert_called_once_with()
    assert state.backend is new
