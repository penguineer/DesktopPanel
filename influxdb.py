"""InfluxDB connection widget"""

import threading
from typing import Optional, Callable

from influxdb_client import InfluxDBClient
from influxdb_client.client.exceptions import InfluxDBError

from kivy import Logger
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import DictProperty

from tray_icon import TrayIcon


class InfluxDbConfiguration(object):
    """Configuration for InfluxDB 2.x access"""

    @staticmethod
    def from_json_cfg(config: Optional[dict]):
        if config is None:
            return None

        cfg = config.get("influxdb", None)
        if cfg is None:
            return None

        url = cfg.get("url", None)
        if not url:
            raise ValueError("InfluxDB URL must be provided!")

        token = cfg.get("token", None)
        if not token:
            raise ValueError("InfluxDB token must be provided!")

        org = cfg.get("org", None)
        if not org:
            raise ValueError("InfluxDB org must be provided!")

        bucket = cfg.get("bucket", None)

        return InfluxDbConfiguration(url=url, token=token, org=org, bucket=bucket)

    def __init__(self, url: str, token: str, org: str, bucket: Optional[str] = None):
        if not url:
            raise ValueError("InfluxDB URL must be provided!")
        if not token:
            raise ValueError("InfluxDB token must be provided!")
        if not org:
            raise ValueError("InfluxDB org must be provided!")

        self._url = url
        self._token = token
        self._org = org
        self._bucket = bucket

    def url(self) -> str:
        return self._url

    def token(self) -> str:
        return self._token

    def org(self) -> str:
        return self._org

    def bucket(self) -> Optional[str]:
        return self._bucket


class _Colors:
    COLOR_GREY = [77 / 256, 77 / 256, 76 / 256, 1]
    COLOR_GREEN = [0 / 256, 163 / 256, 86 / 256, 1]
    COLOR_RED = [228 / 256, 5 / 256, 41 / 256, 1]


HEALTH_CHECK_INTERVAL = 60  # seconds between periodic health re-checks


class InfluxDbConnector(object):
    """Manages the InfluxDB client lifecycle and executes Flux queries"""

    def __init__(self, cfg: InfluxDbConfiguration):
        if cfg is None:
            raise ValueError("Configuration must be provided!")
        self._cfg = cfg
        self._client = None
        self._tray_icon = None
        self._health_event = None

    def setup(self):
        """Open the client and verify connectivity"""
        self._client = InfluxDBClient(
            url=self._cfg.url(),
            token=self._cfg.token(),
            org=self._cfg.org()
        )
        self._check_health()
        self._health_event = Clock.schedule_interval(
            lambda dt: self._check_health(), HEALTH_CHECK_INTERVAL
        )

    def teardown(self):
        """Close the client"""
        if self._health_event is not None:
            self._health_event.cancel()
            self._health_event = None
        if self._client is not None:
            try:
                self._client.close()
            except Exception as e:
                Logger.warning("InfluxDB: Error closing client: %s", str(e))
            self._client = None
            self._schedule_icon_color(_Colors.COLOR_GREY)

    def update_tray_icon(self, tray_icon=None):
        if tray_icon:
            self._tray_icon = tray_icon

    def query(self, flux_query: str, callback: Callable[[list], None],
              error_callback: Optional[Callable[[Exception], None]] = None) -> None:
        """Execute a Flux query in a background thread.

        :param flux_query: Flux query string to execute.
        :param callback: Called on the Kivy main thread with a list of FluxTable results.
        :param error_callback: Optional callback called on the Kivy main thread with the exception.
        """
        if self._client is None:
            Logger.warning("InfluxDB: Cannot query, client is not connected.")
            return

        def _run():
            try:
                query_api = self._client.query_api()
                tables = query_api.query(flux_query, org=self._cfg.org())
                self._schedule_icon_color(_Colors.COLOR_GREEN)
                Clock.schedule_once(lambda dt: callback(tables))
            except InfluxDBError as e:
                Logger.error("InfluxDB: Query error: %s", str(e))
                self._schedule_icon_color(_Colors.COLOR_RED)
                if error_callback:
                    Clock.schedule_once(lambda dt, _e=e: error_callback(_e))
            except Exception as e:
                Logger.error("InfluxDB: Unexpected query error: %s", str(e))
                self._schedule_icon_color(_Colors.COLOR_RED)
                if error_callback:
                    Clock.schedule_once(lambda dt, _e=e: error_callback(_e))

        threading.Thread(target=_run, daemon=True).start()

    def _check_health(self):
        def _run():
            try:
                health = self._client.health()
                if health.status == "pass":
                    Logger.info("InfluxDB: Connected to %s (status: %s)", self._cfg.url(), health.status)
                    self._schedule_icon_color(_Colors.COLOR_GREEN)
                else:
                    Logger.warning("InfluxDB: Health check returned status: %s", health.status)
                    self._schedule_icon_color(_Colors.COLOR_RED)
            except Exception as e:
                Logger.error("InfluxDB: Health check failed: %s", str(e))
                self._schedule_icon_color(_Colors.COLOR_RED)

        threading.Thread(target=_run, daemon=True).start()

    def _schedule_icon_color(self, color):
        if self._tray_icon:
            Clock.schedule_once(lambda dt: self._tray_icon.setter('icon_color')(self._tray_icon, color))


Builder.load_string("""
<InfluxDbWidget>:
    label: 'Influx'
    icon: 'assets/influxdb_icon_64px.png'
""")


class InfluxDbWidget(TrayIcon):
    """InfluxDB widget that manages the connector lifecycle and reacts to configuration changes"""

    conf = DictProperty(None, allownone=True)

    def __init__(self, **kwargs):
        self._connector = None

        super(InfluxDbWidget, self).__init__(**kwargs)

        self.bind(conf=self._on_conf)

    def query(self, flux_query: str, callback: Callable[[list], None],
              error_callback: Optional[Callable[[Exception], None]] = None) -> None:
        """Execute a Flux query against the configured InfluxDB instance.

        Results are delivered to *callback* on the Kivy main thread as a list
        of FluxTable objects.  If the connector is not yet available (no
        configuration, or configuration error), a warning is logged and no
        callback is invoked.

        :param flux_query: Flux query string.
        :param callback: Called with query results on the main thread.
        :param error_callback: Optional; called with the exception on the main thread.
        """
        if self._connector is None:
            Logger.warning("InfluxDB: No active connector, query skipped.")
            return
        self._connector.query(flux_query, callback, error_callback)

    def teardown(self):
        """Stop the InfluxDB connector if active"""
        if self._connector is not None:
            self._connector.teardown()
            self._connector = None

    def _on_conf(self, _instance, conf):
        if self._connector is not None:
            self._connector.teardown()
            self._connector = None

        if not conf:
            self.icon_color = _Colors.COLOR_GREY
            return

        try:
            cfg = {"influxdb": conf}
            influx_cfg = InfluxDbConfiguration.from_json_cfg(cfg)

            if influx_cfg is None:
                Logger.warning("InfluxDB: Missing configuration, not connecting.")
                self.icon_color = _Colors.COLOR_GREY
                return

            connector = InfluxDbConnector(influx_cfg)
            connector.update_tray_icon(self)
            connector.setup()
            self._connector = connector

        except ValueError as e:
            Logger.error("InfluxDB: Configuration error: %s", str(e))
            self.icon_color = _Colors.COLOR_RED
