from kivy.lang import Builder
from kivy.properties import ColorProperty, StringProperty, ListProperty, ObjectProperty
from kivy.uix.relativelayout import RelativeLayout

from dlg import FullscreenTimedModal


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


Builder.load_string("""
<PresenceSelector>:
    #:set selbtn_size 180

    size: [selbtn_size*2, selbtn_size*2 + 20*2]
    size_hint: [None, None]

    canvas:
        Color:
            rgb: root._btn_present_color
        RoundedRectangle:
            pos: self.size[0] - selbtn_size + 8, self.size[1] - selbtn_size + 8 - 20 
            size: selbtn_size - 8, selbtn_size - 8
            radius: [10]

        Color:
            rgb: root._btn_occupied_color
        RoundedRectangle:
            pos: self.size[0] - selbtn_size + 8, 20
            size: selbtn_size - 8, selbtn_size - 8
            radius: [10]

        Color:
            rgb: root._btn_away_color
        RoundedRectangle:
            pos: 0, 20
            size: selbtn_size - 8, selbtn_size - 8
            radius: [10]

        Color:
            rgb: root._btn_absent_color
        RoundedRectangle:
            pos: 0, self.size[1] - selbtn_size - 20 + 8
            size: selbtn_size - 8, selbtn_size - 8
            radius: [10]

        Color:
            rgb: root.present_color_rgba
        Line:
            circle:
                self.size[0] / 2, self.size[1] / 2, \
                selbtn_size*0.5+12, \
                0, 90
            width: 4
        Line:
            rounded_rectangle: 
                self.size[0] / 2 + 10, self.size[0] / 2 + 10 + 20, \
                self.size[0] / 2 - 10, self.size[1] / 2 - 10 - 20, \
                10
            width: 2

        Color:
            rgb: root.occupied_color_rgba
        Line:
            circle:
                self.size[0] / 2, self.size[1] / 2, \
                selbtn_size*0.5+12, \
                90, 180
            width: 4
        Line:
            rounded_rectangle: 
                self.size[0] / 2 + 10, 20, \
                self.size[0] / 2 - 10, self.size[1] / 2 - 10 - 20, \
                10
            width: 2

        Color:
            rgb: root.away_color_rgba
        Line:
            circle:
                self.size[0] / 2, self.size[1] / 2, \
                selbtn_size*0.5+12, \
                180, 270
            width: 4
        Line:
            rounded_rectangle: 
                0, 20, \
                self.size[0] / 2 - 10, self.size[1] / 2 - 10 - 20, \
                10
            width: 2

        Color:
            rgb: root.absent_color_rgba
        Line:
            circle:
                self.size[0] / 2, self.size[1] / 2, \
                selbtn_size*0.5+12, \
                270, 360
            width: 4
        Line:
            rounded_rectangle: 
                0, self.size[0] / 2 + 10 + 20, \
                self.size[0] / 2 - 10, self.size[1] / 2 - 10 - 20, \
                10
            width: 2


        Color:
            rgb: root.background_color
        Line:
            points:
                self.size[0] / 2, 0, \
                self.size[0] / 2, self.size[1]
            width: 8     
            cap: 'none'
        Line:
            points:
                0, self.size[1] / 2, \
                self.size[0], self.size[1] / 2
            width: 8     
            cap: 'none'
        Line:
            circle:
                self.size[0] / 2, self.size[1] / 2, \
                selbtn_size*0.5
            width: 12

        Color:
            rgb: root._ind_circle_color
        Ellipse:
            pos: selbtn_size*0.5+4, selbtn_size*0.5+4+20
            size: selbtn_size*1-8, selbtn_size*1-8




    BoxLayout:
        orientation: 'vertical'

        BoxLayout:
            orientation: 'horizontal'
            size_x: 20
            padding: [10, 0, 10, 0]

            Label:
                text: 'Absent'
                halign: 'left'
                text_size: self.size
                color: root.text_color

            Label:
                text: 'Present'
                halign: 'right'
                text_size: self.size
                color: root.text_color

        BoxLayout:
            orientation: 'horizontal'
            size_hint: [None, None]
            size: [selbtn_size*2, selbtn_size]

            Button:
                id: btn_absent
                #text: 'Absent'
                background_normal: ''
                background_down: ''
                background_color: 0, 0, 0, 0
                on_press: root.requested_presence = "absent"

            Button:
                id: btn_present
                #text: 'Present'
                background_normal: ''
                background_down: ''
                background_color: 0, 0, 0, 0
                on_press: root.requested_presence = "present"

        BoxLayout:
            orientation: 'horizontal'
            size_hint: [None, None]
            size: [selbtn_size*2, selbtn_size]

            Button:
                id: btn_away
                #text: 'Away'
                background_normal: ''
                background_down: ''
                background_color: 0, 0, 0, 0
                on_press: root.requested_presence = "away"

            Button:
                id: btn_occupied
                #text: 'Occupied'
                background_normal: ''
                background_down: ''
                background_color: 0, 0, 0, 0
                on_press: root.requested_presence = "occupied"

        BoxLayout:
            orientation: 'horizontal'
            padding: [10, 0, 10, 0]

            Label:
                text: 'Away'
                halign: 'left'
                text_size: self.size
                color: root.text_color

            Label:
                text: 'Occupied'
                halign: 'right'
                text_size: self.size
                color: root.text_color
""")


class PresenceSelector(RelativeLayout, PresenceColor):
    background_color = ColorProperty([0, 0, 0, 1])
    """Background color, in the format (r, g, b, a).

    :attr:`background_color` is a :class:`~kivy.properties.ColorProperty` and
    defaults to [1, 1, 1, 1].
    """

    border_color = ColorProperty([77 / 256, 77 / 256, 76 / 256, 1])
    """Border color, in the format (r, g, b, a).

    :attr:`border_color` is a :class:`~kivy.properties.ColorProperty` and
    defaults to [77 / 256, 77 / 256, 76 / 256, 1].
    """

    text_color = ColorProperty([249 / 256, 176 / 256, 0 / 256, 1])
    """Border color, in the format (r, g, b, a).

    :attr:`text_color` is a :class:`~kivy.properties.ColorProperty` and
    defaults to [249 / 256, 176 / 256, 0 / 256, 1].
    """

    active_presence = StringProperty(None)
    requested_presence = StringProperty(None)

    _ind_circle_color = ColorProperty([0, 0, 0, 1])
    _btn_absent_color = ColorProperty([0, 0, 0, 1])
    _btn_present_color = ColorProperty([0, 0, 0, 1])
    _btn_occupied_color = ColorProperty([0, 0, 0, 1])
    _btn_away_color = ColorProperty([0, 0, 0, 1])

    def __init__(self, **kwargs):
        super(PresenceSelector, self).__init__(**kwargs)

        self.bind(active_presence=self._update_active_presence_color)
        self.bind(requested_presence=self._update_requested_presence_color)

    def _update_active_presence_color(self, instance, value):
        c = self.color_for(value)
        if c is None:
            c = self.background_color
        instance._ind_circle_color = c

    def _update_requested_presence_color(self, instance, value):
        instance._btn_absent_color = [0, 0, 0, 1]
        instance._btn_present_color = [0, 0, 0, 1]
        instance._btn_occupied_color = [0, 0, 0, 1]
        instance._btn_away_color = [0, 0, 0, 1]

        if value == "present":
            instance._btn_present_color = self.present_color_rgba
        elif value == "occupied":
            instance._btn_occupied_color = self.occupied_color_rgba
        elif value == "away":
            instance._btn_away_color = self.away_color_rgba
        elif value == "absent":
            instance._btn_absent_color = self.absent_color_rgba


Builder.load_string("""
<PresenceDlg>:
    title: "Presence"
    requested_presence: ps.requested_presence 

    AnchorLayout:
        anchor_x: 'right'
        anchor_y: 'bottom'

        padding: [8, 8]

        PresenceSelector:        
            id: ps
            size_hint: [None, None]
            active_presence: root.active_presence

    AnchorLayout:
        anchor_x: 'left'
        anchor_y: 'top'

        padding: [8, 70 + 20, 8, 8+20]

        PresenceList:
            size: 350, 400
            size_hint: None, 1
            presence_list: root.presence_list
            handle_self: root.handle_self
            handle_others: root.handle_others
""")


class PresenceDlg(FullscreenTimedModal):
    active_presence = StringProperty(None)
    requested_presence = StringProperty(None)

    handle_self = StringProperty()
    handle_others = ListProperty()
    presence_list = ListProperty()

    def __init__(self, **kwargs):
        super(PresenceDlg, self).__init__(**kwargs)

        self.bind(requested_presence=self._on_requested_presence)

    # noinspection PyMethodMayBeStatic
    def _on_requested_presence(self, instance, value):
        instance.ids.ps.requested_presence = value


Builder.load_string("""
<PresenceTrayWidget>:
    size: 100, 50

    #:set radius 5
    #:set top 6
    #:set bottom 8
    canvas:
        Color:
            rgba: root._presence_color
        Line:
            rounded_rectangle: 
                0, bottom, \
                self.size[0], self.size[1]-top-bottom, \
                radius
            width: 1

    Label:
        text: root._presence_text if root._presence_text is not None else ""
        color: root._presence_color 
        font_name: 'assets/FiraMono-Regular.ttf'
        pos: 0, 0+bottom-top
""")


class PresenceTrayWidget(RelativeLayout):
    active_presence = StringProperty(None)

    _presence_color = ColorProperty(PresenceColor.absent_color_rgba)
    _presence_text = StringProperty(None)

    touch_cb = ObjectProperty(None)

    presence_texts = {
        "absent": "Absent",
        "present": "Present",
        "occupied": "Occupied",
        "away": "Away"
    }

    def __init__(self, **kwargs):
        super(PresenceTrayWidget, self).__init__(**kwargs)
        self.bind(active_presence=self._on_active_presence)

    def _on_active_presence(self, _, value):
        self._presence_color = PresenceColor.color_for(value)
        self._presence_text = self.presence_texts.get(value, PresenceColor.absent_color_rgba)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            if self.touch_cb is not None:
                self.touch_cb()
            return True
        return super(PresenceTrayWidget, self).on_touch_down(touch)
