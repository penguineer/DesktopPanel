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


class PresenceColor:
    absent_color_rgba = [77 / 256, 77 / 256, 76 / 256, 1]
    present_color_rgba = [0 / 256, 163 / 256, 86 / 256, 1]
#    away_color_rgba = [249 / 256, 176 / 256, 0 / 256, 1]
    away_color_rgba = [68 / 256, 53 / 256, 126 / 256, 1]
    occupied_color_rgba = [228 / 256, 5 / 256, 41 / 256, 1]

    @staticmethod
    def color_for(value):
        if value == "absent":
            return PresenceColor.absent_color_rgba
        elif value == "present":
            return PresenceColor.present_color_rgba
        elif value == "away":
            return PresenceColor.away_color_rgba
        elif value == "occupied":
            return PresenceColor.occupied_color_rgba

        return None
