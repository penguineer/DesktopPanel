""" Pytest tests for the influxdb module """

import threading
import pytest

from influxdb import InfluxDbConfiguration, InfluxDbConnector, HEALTH_CHECK_INTERVAL


class TestInfluxDbConfiguration:
    def test_no_config(self):
        assert InfluxDbConfiguration.from_json_cfg(None) is None

    def test_empty_config(self):
        assert InfluxDbConfiguration.from_json_cfg(dict()) is None

    def test_no_url(self):
        cfg = {
            "influxdb": {}
        }
        with pytest.raises(ValueError) as e:
            InfluxDbConfiguration.from_json_cfg(cfg)
        assert "URL must be provided" in str(e.value)

    def test_no_token(self):
        cfg = {
            "influxdb": {
                "url": "http://localhost:8086"
            }
        }
        with pytest.raises(ValueError) as e:
            InfluxDbConfiguration.from_json_cfg(cfg)
        assert "token must be provided" in str(e.value)

    def test_no_org(self):
        cfg = {
            "influxdb": {
                "url": "http://localhost:8086",
                "token": "mytoken"
            }
        }
        with pytest.raises(ValueError) as e:
            InfluxDbConfiguration.from_json_cfg(cfg)
        assert "org must be provided" in str(e.value)

    def test_required_fields_no_bucket(self):
        cfg = {
            "influxdb": {
                "url": "http://localhost:8086",
                "token": "mytoken",
                "org": "myorg"
            }
        }
        influx_cfg = InfluxDbConfiguration.from_json_cfg(cfg)

        assert influx_cfg.url() == "http://localhost:8086"
        assert influx_cfg.token() == "mytoken"
        assert influx_cfg.org() == "myorg"
        assert influx_cfg.bucket() is None

    def test_all_fields(self):
        cfg = {
            "influxdb": {
                "url": "http://influx.example.com:8086",
                "token": "secret-token",
                "org": "myorg",
                "bucket": "mybucket"
            }
        }
        influx_cfg = InfluxDbConfiguration.from_json_cfg(cfg)

        assert influx_cfg.url() == "http://influx.example.com:8086"
        assert influx_cfg.token() == "secret-token"
        assert influx_cfg.org() == "myorg"
        assert influx_cfg.bucket() == "mybucket"

    def test_direct_construction_missing_url(self):
        with pytest.raises(ValueError) as e:
            InfluxDbConfiguration(url=None, token="t", org="o")
        assert "URL must be provided" in str(e.value)

    def test_direct_construction_missing_token(self):
        with pytest.raises(ValueError) as e:
            InfluxDbConfiguration(url="http://localhost:8086", token=None, org="o")
        assert "token must be provided" in str(e.value)

    def test_direct_construction_missing_org(self):
        with pytest.raises(ValueError) as e:
            InfluxDbConfiguration(url="http://localhost:8086", token="t", org=None)
        assert "org must be provided" in str(e.value)


# ---------------------------------------------------------------------------
# Helpers for InfluxDbConnector tests
# ---------------------------------------------------------------------------

class _MockClockEvent:
    """Minimal stand-in for a Kivy Clock interval event handle."""

    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class _MockClock:
    """Captures scheduled Clock calls without running them."""

    def __init__(self):
        self.once_calls = []       # list of (callback, delay, event)
        self.interval_calls = []   # list of (callback, interval)
        self._interval_event = _MockClockEvent()

    def schedule_once(self, callback, delay=0):
        event = _MockClockEvent()
        self.once_calls.append((callback, delay, event))
        return event

    def schedule_interval(self, callback, interval):
        self.interval_calls.append((callback, interval))
        return self._interval_event


class _FakeHealth:
    def __init__(self, status="pass"):
        self.status = status


class _FakeQueryApi:
    def __init__(self, tables=None, error=None):
        self._tables = tables or []
        self._error = error

    def query(self, flux_query, org=None):
        if self._error is not None:
            raise self._error
        return self._tables


class _FakeInfluxDBClient:
    def __init__(self, health_status="pass", query_error=None, query_tables=None):
        self._health_status = health_status
        self._query_error = query_error
        self._query_tables = query_tables or []
        self.closed = False

    def health(self):
        return _FakeHealth(self._health_status)

    def query_api(self):
        return _FakeQueryApi(tables=self._query_tables, error=self._query_error)

    def close(self):
        self.closed = True


class _FakeTrayIcon:
    def __init__(self):
        self.icon_color = None

    def setter(self, prop):
        def _set(_instance, value):
            setattr(self, prop, value)
        return _set


def _join_daemon_threads(timeout=2):
    """Wait for all non-main daemon threads to finish."""
    for t in threading.enumerate():
        if t.daemon and t is not threading.main_thread():
            t.join(timeout=timeout)


class TestInfluxDbConnectorSetup:
    def test_setup_schedules_periodic_health_check(self, monkeypatch):
        import influxdb as influxdb_module

        mock_clock = _MockClock()
        monkeypatch.setattr(influxdb_module, "Clock", mock_clock)
        monkeypatch.setattr(
            influxdb_module, "InfluxDBClient",
            lambda **kwargs: _FakeInfluxDBClient()
        )

        cfg = InfluxDbConfiguration(url="http://localhost:8086", token="t", org="o")
        connector = InfluxDbConnector(cfg)
        connector.setup()
        _join_daemon_threads()

        assert len(mock_clock.interval_calls) == 1
        _callback, interval = mock_clock.interval_calls[0]
        assert interval == HEALTH_CHECK_INTERVAL

    def test_setup_stores_health_event(self, monkeypatch):
        import influxdb as influxdb_module

        mock_clock = _MockClock()
        monkeypatch.setattr(influxdb_module, "Clock", mock_clock)
        monkeypatch.setattr(
            influxdb_module, "InfluxDBClient",
            lambda **kwargs: _FakeInfluxDBClient()
        )

        cfg = InfluxDbConfiguration(url="http://localhost:8086", token="t", org="o")
        connector = InfluxDbConnector(cfg)
        connector.setup()

        assert connector._health_event is mock_clock._interval_event


class TestInfluxDbConnectorTeardown:
    def test_teardown_cancels_health_event(self, monkeypatch):
        import influxdb as influxdb_module

        mock_clock = _MockClock()
        monkeypatch.setattr(influxdb_module, "Clock", mock_clock)
        monkeypatch.setattr(
            influxdb_module, "InfluxDBClient",
            lambda **kwargs: _FakeInfluxDBClient()
        )

        cfg = InfluxDbConfiguration(url="http://localhost:8086", token="t", org="o")
        connector = InfluxDbConnector(cfg)
        connector.setup()

        health_event = mock_clock._interval_event
        assert not health_event.cancelled

        connector.teardown()

        assert health_event.cancelled
        assert connector._health_event is None

    def test_teardown_clears_health_event_when_client_close_raises(self, monkeypatch):
        """After teardown, _health_event is None even if client.close() raises."""
        import influxdb as influxdb_module

        mock_clock = _MockClock()
        monkeypatch.setattr(influxdb_module, "Clock", mock_clock)

        class _ErrorClient(_FakeInfluxDBClient):
            def close(self):
                raise RuntimeError("close error")

        monkeypatch.setattr(
            influxdb_module, "InfluxDBClient",
            lambda **kwargs: _ErrorClient()
        )

        cfg = InfluxDbConfiguration(url="http://localhost:8086", token="t", org="o")
        connector = InfluxDbConnector(cfg)
        connector.setup()
        connector.teardown()  # must not raise

        assert connector._health_event is None


class TestInfluxDbConnectorQueryIconUpdate:
    """Verify that a successful query sets the icon green and a failed query sets it red."""

    def _run_query_and_collect_threads(self, connector):
        """Start a query and return the spawned background thread."""
        spawned = []
        orig_start = threading.Thread.start

        def patched_start(self_thread):
            orig_start(self_thread)
            spawned.append(self_thread)

        threading.Thread.start = patched_start
        try:
            connector.query(
                "from(bucket:\"b\") |> range(start: -1h)",
                callback=lambda tables: None
            )
        finally:
            threading.Thread.start = orig_start

        for t in spawned:
            t.join(timeout=5)

    def _fire_clock_once_calls(self, mock_clock):
        for cb, _delay, _evt in mock_clock.once_calls:
            cb(0)

    def test_successful_query_schedules_green_icon(self, monkeypatch):
        import influxdb as influxdb_module

        mock_clock = _MockClock()
        monkeypatch.setattr(influxdb_module, "Clock", mock_clock)

        cfg = InfluxDbConfiguration(url="http://localhost:8086", token="t", org="o")
        connector = InfluxDbConnector(cfg)
        connector._client = _FakeInfluxDBClient(query_tables=[])
        tray = _FakeTrayIcon()
        connector._tray_icon = tray

        self._run_query_and_collect_threads(connector)
        self._fire_clock_once_calls(mock_clock)

        assert tray.icon_color == influxdb_module._Colors.COLOR_GREEN

    def test_influxdb_error_query_schedules_red_icon(self, monkeypatch):
        import influxdb as influxdb_module
        from influxdb_client.client.exceptions import InfluxDBError

        mock_clock = _MockClock()
        monkeypatch.setattr(influxdb_module, "Clock", mock_clock)

        cfg = InfluxDbConfiguration(url="http://localhost:8086", token="t", org="o")
        connector = InfluxDbConnector(cfg)
        connector._client = _FakeInfluxDBClient(query_error=InfluxDBError(response=None))
        tray = _FakeTrayIcon()
        connector._tray_icon = tray

        self._run_query_and_collect_threads(connector)
        self._fire_clock_once_calls(mock_clock)

        assert tray.icon_color == influxdb_module._Colors.COLOR_RED

    def test_generic_error_query_schedules_red_icon(self, monkeypatch):
        import influxdb as influxdb_module

        mock_clock = _MockClock()
        monkeypatch.setattr(influxdb_module, "Clock", mock_clock)

        cfg = InfluxDbConfiguration(url="http://localhost:8086", token="t", org="o")
        connector = InfluxDbConnector(cfg)
        connector._client = _FakeInfluxDBClient(query_error=RuntimeError("network error"))
        tray = _FakeTrayIcon()
        connector._tray_icon = tray

        self._run_query_and_collect_threads(connector)
        self._fire_clock_once_calls(mock_clock)

        assert tray.icon_color == influxdb_module._Colors.COLOR_RED
