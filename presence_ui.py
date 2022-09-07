""" Module for presence UI """

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import ColorProperty, StringProperty, ListProperty, ObjectProperty, DictProperty
from kivy.uix.relativelayout import RelativeLayout

import util
from dlg import FullscreenTimedModal
from presence_conn import PresenceSvcCfg


class Contact(object):
    def __init__(self, handle, view_name=None, avatar=None):
        if not handle:
            raise ValueError("Handle must be provided!")

        self._handle = handle
        self._view_name = view_name
        self._avatar = avatar

    @property
    def handle(self):
        return self._handle

    @property
    def view_name(self):
        return self._view_name

    @property
    def avatar_url(self):
        return self._avatar


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
            rgba: root._presence_color
        Line:
            rounded_rectangle: 
                0, 0, \
                self.size[0], self.size[1], \
                5

    BoxLayout:
        padding: [2, 2, 8, 2]
        spacing: 16

        AsyncImage:
            source: root.contact.avatar_url if root.contact and root.contact.avatar_url else '' 
            size: 48, 48
            size_hint: None, None
            color: root._presence_color 

        BoxLayout:
            orientation: 'vertical'
            padding: 2
            spacing: 4
            
            Label:
                text: root.contact.view_name if root.contact and root.contact.view_name else '<None>' 
                font_size: 18
                halign: 'left'
                valign: 'center'
                font_name: 'assets/FiraMono-Regular.ttf'
                text_size: self.size
                color: root._presence_color
                size_hint_y: 1
                
            BoxLayout:
                orientation: 'horizontal'
                size_hint_y: 0.5
                
                Label:
                    text: root._displayed_presence.message \
                        if root._displayed_presence and root._displayed_presence.message else ''
                    font_size: 12
                    text_size: self.size
                    size_hint_x: 0.8
                    shorten: True
                    halign: 'left'
                    color: root._presence_color
            
                Label:
                    text: root._presence_since if root._presence_since else ''
                    font_size: 12
                    text_size: self.size
                    size_hint_x: 0.2
                    halign: 'right'
                    color: root._presence_color
                    
""")


class PresenceListItem(RelativeLayout):
    INACTIVE_COLOR = [177 / 256, 77 / 256, 76 / 256, 1]
    HDISP = util.HumanizedTimeDisplay(units='s', max_len=2)

    _presence_color = ColorProperty([177 / 256, 77 / 256, 76 / 256, 1])
    _presence_since = StringProperty(None, allownone=True)

    contact = ObjectProperty(None, allownone=True)
    presence_list = ListProperty()

    _displayed_presence = ObjectProperty(None, allownone=True)

    def __init__(self, **kwargs):
        super(PresenceListItem, self).__init__(**kwargs)

        self.bind(contact=self._on_data)
        self.bind(presence_list=self._on_data)
        self.bind(_displayed_presence=self._on_displayed_presence)

        self._update_clock = Clock.schedule_interval(lambda dt: self._display_presence_since(),
                                                     timeout=1)

    def __del__(self):
        if self._update_clock:
            self._update_clock.cancel()

    def _on_data(self, _instance, _value):
        if self.contact is None:
            self._displayed_presence = None
            return

        self_presence = list(filter(lambda el: el.handle == self.contact.handle, self.presence_list))
        self._displayed_presence = self_presence[0] if self_presence else None

    def _on_displayed_presence(self, _instance, _value):
        if self._displayed_presence is None:
            self._presence_color = PresenceListItem.INACTIVE_COLOR
            return

        c = PresenceColor.color_for(self._displayed_presence.status) if self._displayed_presence else None
        self._presence_color = c if c else PresenceColor.absent_color_rgba

        self._display_presence_since()

    def _display_presence_since(self):
        self._presence_since = PresenceListItem.HDISP.convert_iso8601(self._displayed_presence.timestamp) \
            if self._displayed_presence and self._displayed_presence.timestamp else ""


Builder.load_string("""
<PresenceList>:
    BoxLayout:
        orientation: 'vertical'
        size_hint: 1, 1

        PresenceListItem:
            id: presence_self
            contact: root.contacts.get(root.handle_self, None) if root.contacts and root.handle_self else None
            presence_list: root.presence_list

        Widget:
            size_hint: None, None
            size: 0, 16

        BoxLayout:
            id: presence_others
            orientation: 'vertical'
            spacing: 8

        Widget: 
            size_hint: 1, 1

""")


class PresenceList(RelativeLayout):
    handle_self = StringProperty(None, allownone=True)
    contacts = DictProperty(None)

    presence_list = ListProperty([])

    def __init__(self, **kwargs):
        super(PresenceList, self).__init__(**kwargs)

        self.bind(handle_self=self._on_contact_change)
        self.bind(contacts=self._on_contact_change)

    def _on_contact_change(self, _instance, _value):
        if 'presence_others' not in self.ids:
            return

        self.ids.presence_others.clear_widgets()

        if not self.contacts:
            return

        for handle in self.contacts.keys():
            if handle != self.handle_self:
                pi = PresenceListItem()
                pi.contact = self.contacts.get(handle)
                pi.presence_list = self.presence_list
                self.bind(presence_list=pi.setter('presence_list'))
                self.ids.presence_others.add_widget(pi)


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
                on_press: root.request_callback("away")

            Button:
                id: btn_present
                #text: 'Present'
                background_normal: ''
                background_down: ''
                background_color: 0, 0, 0, 0
                on_press: root.request_callback("present")

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
                on_press: root.request_callback("absent")

            Button:
                id: btn_occupied
                #text: 'Occupied'
                background_normal: ''
                background_down: ''
                background_color: 0, 0, 0, 0
                on_press: root.request_callback("occupied")

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

    active_status = StringProperty(None, allownone=True)
    requested_status = StringProperty(None, allownone=True)

    request_callback = ObjectProperty()

    _ind_circle_color = ColorProperty([0, 0, 0, 1])
    _btn_absent_color = ColorProperty([0, 0, 0, 1])
    _btn_present_color = ColorProperty([0, 0, 0, 1])
    _btn_occupied_color = ColorProperty([0, 0, 0, 1])
    _btn_away_color = ColorProperty([0, 0, 0, 1])

    def __init__(self, **kwargs):
        super(PresenceSelector, self).__init__(**kwargs)

        self.bind(active_status=self._update_active_status_color)
        self.bind(requested_status=self._update_requested_status_color)

    def _update_active_status_color(self, _instance, value):
        c = PresenceColor.color_for(value)
        if c is None:
            c = self.background_color
        self._ind_circle_color = c

    def _update_requested_status_color(self, _instance, value):
        for state in ["absent", "present", "occupied", "away"]:
            setattr(self, f"_btn_%s_color" % state,
                    PresenceColor.color_for(value) if state == value else [0, 0, 0, 1])


Builder.load_string("""
<PresenceDlg>:
    title: "Presence"

    AnchorLayout:
        anchor_x: 'right'
        anchor_y: 'bottom'

        padding: [8, 8]

        PresenceSelector:        
            id: ps
            size_hint: [None, None]
            active_status: root.active_presence.status if root.active_presence else "unknown"
            requested_status: root.requested_status
            request_callback: root.request_callback

    AnchorLayout:
        anchor_x: 'left'
        anchor_y: 'top'

        padding: [8, 70 + 20, 8, 8+20]

        PresenceList:
            size: 350, 400
            size_hint: None, 1
            presence_list: root.presence_list
            handle_self: root.handle_self
            contacts: root.contacts
""")


class PresenceDlg(FullscreenTimedModal):
    active_presence = ObjectProperty(None, allownone=True)
    requested_status = StringProperty(None, allownone=True)

    handle_self = StringProperty(None, allownone=True)
    contacts = DictProperty()
    presence_list = ListProperty()

    request_callback = ObjectProperty()

    def __init__(self, **kwargs):
        super(PresenceDlg, self).__init__(**kwargs)


Builder.load_string("""
#:import MqttPresenceUpdater presence_conn.MqttPresenceUpdater
#:import PingTechPresenceUpdater presence_conn.PingTechPresenceUpdater
#:import PingTechPresenceReceiver presence_conn.PingTechPresenceReceiver
#:import PresenceChangeHandler presence_conn.PresenceChangeHandler

<PresenceTrayWidget>:
    presence_list: presence_receiver.presence_list
    active_presence: presence_receiver.active_presence    
    
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
        
    PingTechPresenceUpdater:
        id: pingtech_presence        
        svc_conf: root.presence_svc_cfg
        retrieval_trigger: presence_receiver.receive_status
        
    PingTechPresenceReceiver:
        id: presence_receiver        
        svc_conf: root.presence_svc_cfg
        contacts: root.contacts
        handle_self: root.handle_self
        refresh_interval: root.conf.get("refresh-interval", 0) if root.conf else 0
        
    PresenceChangeHandler:
        id: change_handler
        publishers: [pingtech_presence, mqtt_presence]
        active_presence: presence_receiver.active_presence
        retrieval_trigger: root.close_popup
        repost_timeout: 5 #  repost timeout [s] to fix race conditions with multiple clients
""")


class PresenceTrayWidget(RelativeLayout):
    conf = DictProperty(None, allownone=True)
    mqttc = ObjectProperty(None, allownone=True)
    screensaver = ObjectProperty(None, allownone=True)

    active_presence = ObjectProperty(None, allownone=True)

    presence_svc_cfg = ObjectProperty(None, allownone=True)

    handle_self = StringProperty(None, allownone=True)
    handle_others = ListProperty()
    contacts = DictProperty()
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

        self.bind(conf=self._load_presence_config)
        self.bind(mqttc=self._load_presence_config)

        self.bind(active_presence=self._on_active_presence)

        self.pr_sel = None

    def popup_handler(self, _cmd=None, _args=None):
        Clock.schedule_once(lambda dt: self.ids.presence_receiver.receive_status())

        if self.pr_sel is not None and self.pr_sel.is_inactive():
            self.pr_sel = None

        if self.pr_sel is None:
            self.pr_sel = PresenceDlg()

            self.pr_sel.request_callback = self.ids.change_handler.post_status
            # This cannot change

            self.pr_sel.screensaver = self.screensaver
            self.bind(screensaver=self.pr_sel.setter('screensaver'))

            self.pr_sel.handle_self = self.handle_self
            self.bind(handle_self=self.pr_sel.setter('handle_self'))

            self.pr_sel.contacts = self.contacts
            self.bind(contacts=self.pr_sel.setter('contacts'))

            self.pr_sel.presence_list = self.presence_list
            self.bind(presence_list=self.pr_sel.setter('presence_list'))

            self.pr_sel.requested_status = self.ids.change_handler.requested_status
            self.ids.change_handler.bind(requested_status=self.pr_sel.setter('requested_status'))

            self.pr_sel.active_presence = self.active_presence
            self.bind(active_presence=self.pr_sel.setter('active_presence'))

            self.pr_sel.requested_status = self.ids.change_handler.requested_status
            self.pr_sel.bind(requested_status=self.ids.change_handler.setter('requested_status'))

            self.pr_sel.open()
        else:
            self.pr_sel.dismiss()
            self.pr_sel = None

    def close_popup(self):
        Clock.schedule_once(lambda dt: self.pr_sel is None or self.pr_sel.dismiss())

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.popup_handler()
            return True
        return super(PresenceTrayWidget, self).on_touch_down(touch)

    def _on_active_presence(self, _instance, value):
        if self.pr_sel is not None:
            self.pr_sel.active_presence = value

        if value and value.status in self.presence_texts:
            self._presence_color = PresenceColor.color_for(value.status) if value else None
            self._presence_text = self.presence_texts.get(value.status, PresenceColor.absent_color_rgba) if value \
                else None
        else:
            self._presence_color = PresenceColor.color_for("absent")
            self._presence_text = ""

    def _load_presence_config(self, _instance, _value):
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

        contacts = dict()

        cfg_contacts = self.conf.get('people', {})
        if cfg_contacts is not None:
            for p in [self.handle_self] + self.handle_others:
                person = cfg_contacts.get(p, None)
                if person is not None:
                    contact = Contact(handle=p,
                                      view_name=person.get('view_name', None),
                                      avatar=person.get('avatar', None))
                    contacts[p] = contact
        self.contacts = contacts

        self.presence_svc_cfg = PresenceSvcCfg(
            svc=self.conf['svc'],
            handle=self.conf['self'],
            token=self.conf['token']
        )

        Clock.schedule_once(lambda dt: self.ids.presence_receiver.receive_status())
