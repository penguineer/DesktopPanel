""" SpaceStatus (SpaceAPI) module"""

from typing import Optional

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.logger import Logger
from kivy.network.urlrequest import UrlRequest
from kivy.properties import StringProperty, ColorProperty, DictProperty
from kivy.uix.relativelayout import RelativeLayout


class SpaceApiConfguration(object):
    """Configuration for the SpaceAPI access"""

    INTERVAL_DEFAULT = 60

    @staticmethod
    def from_json_cfg(config: Optional[dict]):
        if config is None:
            return None

        return SpaceApiConfguration(
            url=config.get("url", None),
            logo=config.get("logo", None),
            interval=int(config.get("interval", SpaceApiConfguration.INTERVAL_DEFAULT))
        )

    def __init__(self,
                 url: str,
                 logo: Optional[str] = None,
                 interval: Optional[int] = INTERVAL_DEFAULT):
        if not url:
            raise ValueError("URL must be provided!")

        self._url = url
        self._logo = logo
        self._interval = interval

    def url(self) -> str:
        return self._url

    def logo(self, url: Optional[str] = None) -> Optional[str]:
        return self._logo if self._logo else url

    def interval(self) -> int:
        return self._interval


Builder.load_string("""
#: import ew kivy.uix.effectwidget

<SpaceStatusWidget>:
    size_hint: None, None
    size: 42, 42

    AsyncImage:
        pos: 0, 4
        source: '' if root.icon is None else root.icon 
        keep_ratio: True
        color: root.icon_color
""")


class SpaceStatusWidget(RelativeLayout):
    conf = DictProperty(None)

    icon = StringProperty(None)

    COLOR_NEUTRAL = [77 / 256, 77 / 256, 76 / 256, 0.1]
    COLOR_OPEN = [0 / 256, 163 / 256, 86 / 256, 1]
    COLOR_CLOSED = [228 / 256, 5 / 256, 41 / 256, 1]
    icon_color = ColorProperty(COLOR_NEUTRAL)

    def __init__(self, **kwargs):
        super(SpaceStatusWidget, self).__init__(**kwargs)
        self._api_config = None
        self._clock = None

        self.bind(conf=self._on_conf)

    def _on_conf(self, _instance, conf: dict) -> None:
        if self._clock is not None:
            self._clock.cancel()
            self._clock = None

        self._api_config = SpaceApiConfguration.from_json_cfg(conf)

        if self._api_config:
            Clock.schedule_once(self._load_api)

            if self._api_config.interval() > 0:
                self._clock = Clock.schedule_interval(self._load_api, self._api_config.interval())

    def _update(self, _request, api_result):
        if api_result is None or self._api_config is None:
            return

        logo_url = api_result.get("logo", None)
        self.icon = self._api_config.logo(logo_url)

        state = api_result.get("state", dict()).get("open", None)
        if state is None:
            self.icon_color = SpaceStatusWidget.COLOR_NEUTRAL
        elif state:
            self.icon_color = SpaceStatusWidget.COLOR_OPEN
        else:
            self.icon_color = SpaceStatusWidget.COLOR_CLOSED

    def _load_api(self, _dt):
        if self._api_config is None:
            return
        if self._api_config.url() is None:
            return

        UrlRequest(url=self._api_config.url(),
                   on_success=self._update,
                   on_failure=self._on_failure,
                   on_error=self._on_error,
                   timeout=10
                   )

    def _on_failure(self, _request, _result):
        Logger.error("Failed to load Space API from %s", self._api_config.url())
        self.icon_color = SpaceStatusWidget.COLOR_NEUTRAL

    def _on_error(self, _request, error):
        Logger.error("Failed to load Space API from %s with error: %s", self._api_config.url(), error)
        self.icon_color = SpaceStatusWidget.COLOR_NEUTRAL
