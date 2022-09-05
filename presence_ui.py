""" Module for presence UI """

from functools import partial

from kivy import Logger
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import ColorProperty, StringProperty, ListProperty, ObjectProperty, DictProperty
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.widget import Widget

from dlg import FullscreenTimedModal
from presence_conn import PresenceSvcCfg, PingTechPresenceReceiver, PingTechPresenceUpdater


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
            rgb: root._btn_absent_color
        RoundedRectangle:
            pos: 0, 20
            size: selbtn_size - 8, selbtn_size - 8
            radius: [10]

        Color:
            rgb: root._btn_away_color
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
            rgb: root.absent_color_rgba
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
            rgb: root.away_color_rgba
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
                text: 'Away'
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
                id: btn_away
                #text: 'Away'
                background_normal: ''
                background_down: ''
                background_color: 0, 0, 0, 0
                on_press: root.requested_presence = "away"

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
                id: btn_absent
                #text: 'Absent'
                background_normal: ''
                background_down: ''
                background_color: 0, 0, 0, 0
                on_press: root.requested_presence = "absent"

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
                text: 'Absent'
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

    def _update_active_presence_color(self, _instance, value):
        c = PresenceColor.color_for(value)
        if c is None:
            c = self.background_color
        self._ind_circle_color = c

    def _update_requested_presence_color(self, _instance, value):
        for state in ["absent", "present", "occupied", "away"]:
            setattr(self, f"_btn_%s_color" % state,
                    PresenceColor.color_for(value) if state == value else [0, 0, 0, 1])


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
#:import MqttPresenceUpdater presence_conn.MqttPresenceUpdater

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

    MqttPresenceUpdater:
        id: mqtt_presence
        mqttc: root.mqttc
        topic: root.conf.get("mqtt-presence-topic", "") if root.conf else ""
""")


class PresenceTrayWidget(RelativeLayout):
    conf = DictProperty(None)
    mqttc = ObjectProperty(None)

    active_presence = StringProperty(None)
    requested_presence = StringProperty(None)

    presence_receiver = ObjectProperty(None)

    presence_emitter = ObjectProperty(None)

    handle_self = StringProperty()
    handle_others = ListProperty()
    presence_list = ListProperty()

    _presence_color = ColorProperty(PresenceColor.absent_color_rgba)
    _presence_text = StringProperty(None)

    presence_texts = {
        "absent": "Absent",
        "present": "Present",
        "occupied": "Occupied",
        "away": "Away"
    }

    def __init__(self, **kwargs):
        super(PresenceTrayWidget, self).__init__(**kwargs)

        self.bind(conf=self._on_conf)
        self.bind(mqttc=self._on_mqttc)

        self.bind(active_presence=self._on_active_presence)

        self.pr_sel = None

        self.bind(active_presence=self._on_active_presence)
        self.property('active_presence').dispatch(self)

        self.bind(presence_list=self._on_presence_list)
        self.property('presence_list').dispatch(self)

        self.bind(requested_presence=self._on_presence_request)

    def _on_conf(self, _instance, _conf: list) -> None:
        self._update_configuration()

    def _on_mqttc(self, _instance, _mqttc) -> None:
        self._update_configuration()

    def _update_configuration(self) -> None:
        self._load_presence_config()

    def popup_handler(self, _cmd=None, _args=None):
        Clock.schedule_once(lambda dt: self._presence_load())

        if self.pr_sel is not None and self.pr_sel.is_inactive():
            self.pr_sel = None

        if self.pr_sel is None:
            self.pr_sel = PresenceDlg()

            self.pr_sel.handle_self = self.handle_self
            self.pr_sel.handle_others = self.handle_others
            self.pr_sel.presence_list = self.presence_list

            # Don't do this bind:
            #   self.bind(active_presence=self.pr_sel.setter('active_presence'))
            # This results in dangling property binds and repeated calls of inactive widgets.

            self.pr_sel.active_presence = self.active_presence
            self.pr_sel.requested_presence = self.requested_presence
            self.pr_sel.bind(requested_presence=self.setter('requested_presence'))

            self.pr_sel.open()
        else:
            self.pr_sel.dismiss()
            self.pr_sel = None

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.popup_handler()
            return True
        return super(PresenceTrayWidget, self).on_touch_down(touch)

    def _on_presence_request(self, _instance, value):
        Clock.schedule_once(lambda dt: self.pr_sel is None or self.pr_sel.dismiss(), timeout=0.25)
        Clock.schedule_once(lambda dt: setattr(self, 'active_presence', value))
        Clock.schedule_once(lambda dt: setattr(self.presence_emitter, 'requested_presence', value))

    def _on_active_presence(self, _instance, value):
        if self.presence_list is not None and len(self.presence_list):
            p = self.presence_list[0]
            p.presence = value

        if self.pr_sel is not None:
            self.pr_sel.active_presence = value

        if 'mqtt_presence' in self.ids:
            self.ids.mqtt_presence.post_status(value)

        if value in self.presence_texts:
            self._presence_color = PresenceColor.color_for(value)
            self._presence_text = self.presence_texts.get(value, PresenceColor.absent_color_rgba)
        else:
            self._presence_color = PresenceColor.color_for("absent")
            self._presence_text = ""

    def _on_presence_list(self, _instance, _value):
        if self.pr_sel is not None:
            self.pr_sel.presence_list = []
            self.pr_sel.presence_list = self.presence_list

    def _load_presence_config(self):
        if self.conf is None:
            self.handle_self = ""
            self.handle_others = []
            self.presence_list = []
            self.presence_receiver = None
            self.presence_updater = None
            self.presence_emitter = None
            return

        self.handle_self = self.conf.get('self', None)
        self.handle_others = self.conf.get('others', [])

        pl = []

        people = self.conf.get('people', {})
        if people is not None:
            for p in [self.handle_self] + self.handle_others:
                person = people.get(p, None)
                if person is not None:
                    presence = Presence(handle=p,
                                        view_name=person.get('view_name', None),
                                        avatar=person.get('avatar', None))
                    pl.append(presence)

        self.presence_list = pl

        presence_svc_cfg = PresenceSvcCfg(
            svc=self.conf['svc'],
            handle=self.conf['self'],
            token=self.conf['token']
        )
        self.presence_receiver = PingTechPresenceReceiver(presence_svc_cfg)
        self.presence_updater = PingTechPresenceUpdater(presence_svc_cfg)
        self.presence_emitter = PresencePingTechEmitter(presence_updater=self.presence_updater)

        self._presence_load()

    def _presence_load(self):
        if self.presence_receiver:
            self.presence_receiver.receive_status(self._on_presence_loaded,
                                                  self._on_presence_load_failed)

    def _on_presence_loaded(self, remote_presence):
        for e in self.presence_list:
            presence = remote_presence.get(e.handle)
            if presence is not None:
                e.presence = presence.get('status', "unknown")

            if e.handle == self.handle_self:
                self.active_presence = e.presence

        self.property('presence_list').dispatch(self)

    def _on_presence_load_failed(self, error):
        Logger.error("Presence: Error while fetching presence: " + str(error))
        for e in self.presence_list:
            e.presence = "unknown"


class PresencePingTechEmitter(Widget):
    presence_updater = ObjectProperty(None)

    requested_presence = StringProperty(None)
    emission_result = ObjectProperty(None)
    emission_error = StringProperty(None)

    def __init__(self, presence_updater, **kwargs):
        super(PresencePingTechEmitter, self).__init__(**kwargs)

        if presence_updater is None:
            raise ValueError("Updater must be provided!")

        self.presence_updater = presence_updater

        self.bind(requested_presence=self._on_requested_presence)

    def _on_requested_presence(self, _, value):
        if self.presence_updater:
            Clock.schedule_once(lambda dt: partial(
                self.presence_updater.update_status,
                value,
                None,
                self._on_success,
                self._on_error
            )())

    def _on_success(self, status):
        self.emission_result = status
        self.emission_error = None

    def _on_error(self, error):
        self.emission_error = error
        Logger.error("Presence: Got error on presence update: %s", str(error))
