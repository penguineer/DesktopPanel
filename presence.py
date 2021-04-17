class Presence:
    def __init__(self, handle, view_name=None, avatar=None, presence=None):
        self._handle = handle
        self._view_name = view_name
        self._avatar = avatar
        self._presence = presence

    @property
    def handle(self):
        return self._handle

    @property
    def view_name(self):
        return self._view_name

    @property
    def avatar(self):
        return self._avatar

    @property
    def presence(self):
        return self._presence

    @presence.setter
    def presence(self, presence):
        self._presence = presence
