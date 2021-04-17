from kivy.lang import Builder
from kivy.properties import ColorProperty, StringProperty, ListProperty
from kivy.uix.relativelayout import RelativeLayout


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


Builder.load_string("""
<PresenceListItem>:
    size: 250, 52
    size_hint: 1, None

    canvas:
        Color:
            rgba: root.presence_color
        Line:
            rounded_rectangle: 
                0, 0, \
                self.size[0], self.size[1], \
                5

    BoxLayout:
        padding: 2
        spacing: 16

        AsyncImage:
            source: '' if root.avatar_url is None else root.avatar_url 
            size: 48, 48
            size_hint: None, None
            color: root.presence_color 

        Label:
            text: '<None>' if root.view_name is None else root.view_name
            font_size: 18
            halign: 'left'
            valign: 'center'
            font_name: 'assets/FiraMono-Regular.ttf'
            text_size: self.size
            color: root.presence_color 
""")


class PresenceListItem(RelativeLayout):
    presence_color = ColorProperty([177 / 256, 77 / 256, 76 / 256, 1])

    handle = StringProperty(None)
    presence_list = ListProperty(None)

    view_name = StringProperty(None)
    avatar_url = StringProperty(None)

    def __init__(self, **kwargs):
        super(PresenceListItem, self).__init__(**kwargs)

        self.bind(handle=self._on_presence_update)
        self.bind(presence_list=self._on_presence_update)

    def _on_presence_update(self, _instance, _value):
        if self.presence_list is None:
            self.view_name = self.handle
            self.avatar_url = ''
            return

        for presence in self.presence_list:
            if presence.handle != self.handle:
                continue

            self.view_name = presence.view_name
            self.avatar_url = presence.avatar
            c = PresenceColor.color_for(presence.presence)
            self.presence_color = PresenceColor.absent_color_rgba if c is None else c


Builder.load_string("""
<PresenceList>:
    BoxLayout:
        orientation: 'vertical'
        size_hint: 1, 1

        PresenceListItem:
            handle: root.handle_self
            presence_list: root.presence_list

        Widget:
            size_hint: None, None
            size: 0, 16

        BoxLayout:
            id: others
            orientation: 'vertical'
            spacing: 8

        Widget: 
            size_hint: 1, 1

""")


class PresenceList(RelativeLayout):
    handle_self = StringProperty(None)
    handle_others = ListProperty(None)

    presence_list = ListProperty(None)

    def __init__(self, **kwargs):
        super(PresenceList, self).__init__(**kwargs)

        self.bind(handle_others=self._on_update_others)

    def _on_update_others(self, _instance, _value):
        if self.ids.others is None:
            return

        self.ids.others.clear_widgets()

        for handle in self.handle_others:
            pi = PresenceListItem()
            pi.handle = handle
            pi.presence_list = self.presence_list
            self.bind(presence_list=pi.setter('presence_list'))
            self.ids.others.add_widget(pi)
