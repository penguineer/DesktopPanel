""" Module for presence connectivity """

import json
from abc import abstractmethod
from functools import partial

from kivy.logger import Logger
from kivy.network.urlrequest import UrlRequest
from kivy.properties import ObjectProperty, StringProperty
from kivy.uix.widget import Widget


class PresencePublisher(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @abstractmethod
    def post_status(self, status, message=None):
        pass


class MqttPresenceUpdater(PresencePublisher):
    mqttc = ObjectProperty()
    topic = StringProperty()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def post_status(self, status, _message=None):
        if self.mqttc and self.topic:
            self.mqttc.publish(self.topic, status, qos=2)


class PresenceSvcCfg(object):
    def __init__(self, svc, handle, token):
        if svc is None:
            raise ValueError("Service URL must be provided")

        if handle is None:
            raise ValueError("Handle must be provided")

        if token is None:
            raise ValueError("Token must be provided")

        self._svc = svc
        self._handle = handle
        self._token = token

    def auth_headers(self):
        return {
            'Authentication': self._token
        }

    def get_endpoint(self):
        return self._svc_endpoint("presence")

    def post_endpoint(self):
        return self._svc_endpoint("presence/" + self._handle)

    def _svc_endpoint(self, endpoint):
        return self._svc + "/" + endpoint


class PingTechPresenceUpdater(PresencePublisher):
    svc_conf = ObjectProperty(None)

    emission_result = ObjectProperty(None)
    emission_error = StringProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def post_status(self, status, message=None):
        if self.svc_conf is None:
            return

        presence = {
            "status": status,
            "message": message if message else ""
        }

        body = json.dumps(presence)

        UrlRequest(url=self.svc_conf.post_endpoint(),
                   method="POST",
                   req_body=body,
                   req_headers=self.svc_conf.auth_headers(),
                   on_success=self._on_success,
                   on_failure=self._on_failure,
                   on_error=self._on_error,
                   timeout=10
                   )

    def _on_success(self, _request, result):
        self.emission_result = result
        self.emission_error = None

    def _on_failure(self, _request, result):
        self._register_error(result)

    def _on_error(self, _request, error):
        self._register_error(str(error))

    def _register_error(self, error):
        self.emission_result = None
        self.emission_error = error
        Logger.error("Presence: Got error on presence update: %s", str(error))


class PingTechPresenceReceiver:
    def __init__(self, svc: PresenceSvcCfg):
        if svc is None:
            raise ValueError("Service configuration must be provided!")
        self._svc = svc

    def receive_status(self,
                       list_handler=None,
                       error_handler=None):
        UrlRequest(url=self._svc.get_endpoint(),
                   req_headers=self._svc.auth_headers(),
                   on_success=partial(PingTechPresenceReceiver._on_presence_json, list_handler),
                   on_failure=partial(PingTechPresenceReceiver._on_failure, error_handler),
                   on_error=partial(PingTechPresenceReceiver._on_error, error_handler),
                   timeout=10
                   )

    @staticmethod
    def _on_presence_json(list_handler, _request, result):
        presence = dict()

        for p in result['entries']:
            handle = p['handle']
            del p['handle']
            presence[handle] = p

        if list_handler:
            list_handler(presence)

    @staticmethod
    def _on_failure(error_handler, _request, result):
        if error_handler:
            error_handler(result)

    @staticmethod
    def _on_error(error_handler, _request, error):
        if error_handler:
            error_handler(str(error))
