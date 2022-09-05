""" Module for presence connectivity """

import json
from abc import abstractmethod

from kivy.logger import Logger
from kivy.network.urlrequest import UrlRequest
from kivy.properties import ObjectProperty, StringProperty, ListProperty, DictProperty
from kivy.uix.widget import Widget


# TODO make this a dataclass when we have the required python version available
class Presence(object):
    def __init__(self, handle, status=None, message=None, timestamp=None):
        if not handle:
            raise ValueError("Handle must be provided!")

        self._handle = handle
        self._status = status
        self._message = message
        self._timestamp = timestamp

    @property
    def handle(self):
        return self._handle

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, presence):
        self._status = presence

    @property
    def message(self):
        return self._message

    @message.setter
    def message(self, message):
        self._message = message

    @property
    def timestamp(self):
        return self._timestamp

    @timestamp.setter
    def timestamp(self, timestamp):
        self._timestamp = timestamp


class PresencePublisher(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @abstractmethod
    def post_status(self, status, message=None):
        pass


class MqttPresenceUpdater(PresencePublisher):
    mqttc = ObjectProperty(None, allownone=True)
    topic = StringProperty(None, allownone=True)

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
    svc_conf = ObjectProperty(None, allownone=True)

    emission_result = ObjectProperty(None, allownone=True)
    emission_error = StringProperty(None, allownone=True)

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


class PingTechPresenceReceiver(Widget):
    svc_conf = ObjectProperty(None, allownone=True)

    handle_self = StringProperty(None, allownone=True)
    contacts = DictProperty()

    active_presence = ObjectProperty(None, allownone=True)
    presence_list = ListProperty()

    retrieval_error = ObjectProperty(None, allownone=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def receive_status(self):
        if self.svc_conf is None:
            return

        UrlRequest(url=self.svc_conf.get_endpoint(),
                   req_headers=self.svc_conf.auth_headers(),
                   on_success=self._on_presence_json,
                   on_failure=self._on_failure,
                   on_error=self._on_error,
                   timeout=10
                   )

    def _on_presence_json(self, _request, presence_json):
        self.retrieval_error = None

        presence_list = list()
        active_presence = None

        for e in presence_json.get('entries', []):
            handle = e.get("handle", None)

            contact = self.contacts.get(handle, None)
            if contact:
                status = e.get("status", None)
                message = e.get("message", None)
                timestamp = e.get("timestamp", None)
                p = Presence(handle, status=status, message=message, timestamp=timestamp)
                presence_list.append(p)

                if handle == self.handle_self:
                    active_presence = p

        self.presence_list = presence_list
        self.active_presence = active_presence

    def _on_failure(self, _request, result):
        self._register_error(result)

    def _on_error(self, _request, error):
        self._register_error(str(error))

    def _register_error(self, error):
        self.retrieval_error = error
        self.active_presence = None
        self.presence_list = []
        Logger.error("Presence: Error while fetching presence: " + error)
