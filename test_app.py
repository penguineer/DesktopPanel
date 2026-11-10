"""Tests for DesktopPanel application shutdown."""

from types import SimpleNamespace
from unittest.mock import Mock

import app as app_module


def _app_with_resources(resources):
    return SimpleNamespace(
        _stopped=False,
        config_obs=resources[0],
        gtd_page=resources[1],
        system_page=resources[2],
        mqttc=resources[3],
        amqp_widget=resources[4],
        influxdb_widget=resources[5],
    )


def test_on_stop_tears_down_owned_resources_exactly_once():
    resources = [Mock() for _ in range(6)]
    instance = _app_with_resources(resources)

    app_module.TabbedPanelApp.on_stop(instance)
    app_module.TabbedPanelApp.on_stop(instance)

    for resource in resources:
        resource.teardown.assert_called_once_with()


def test_on_stop_continues_when_a_resource_fails(monkeypatch):
    resources = [Mock() for _ in range(6)]
    resources[1].teardown.side_effect = RuntimeError("observer failed")
    logger = Mock()
    monkeypatch.setattr(app_module, "Logger", logger)
    instance = _app_with_resources(resources)

    app_module.TabbedPanelApp.on_stop(instance)

    for resource in resources:
        resource.teardown.assert_called_once_with()
    logger.exception.assert_called_once()
