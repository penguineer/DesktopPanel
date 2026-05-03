""" Module for page Presence """

from kivy.lang import Builder
from kivy.properties import ObjectProperty, StringProperty, ListProperty, DictProperty

import globalcontent

Builder.load_string("""
#:import PresenceHistoryList presence_ui.PresenceHistoryList
#:import PresenceSelector presence_ui.PresenceSelector

<PresencePage>:
    label: 'presence'
    icon: 'assets/icon_presence.png'

    AnchorLayout:
        anchor_x: 'left'
        anchor_y: 'top'
        padding: [8, 8, 8, 8]

        PresenceHistoryList:
            size: 350, 400
            size_hint: None, 1
            tracked_entries: root.tracked_entries

    AnchorLayout:
        anchor_x: 'right'
        anchor_y: 'bottom'
        padding: [8, 8]

        PresenceSelector:
            id: ps
            size_hint: [None, None]
            active_status: root.active_presence.status if root.active_presence else "unknown"
            requested_status: root.requested_status
            request_callback: root.request_callback if root.request_callback else lambda *a: None
""")


class PresencePage(globalcontent.ContentPage):
    active_presence = ObjectProperty(None, allownone=True)
    requested_status = StringProperty(None, allownone=True)

    handle_self = StringProperty(None, allownone=True)
    contacts = DictProperty()
    presence_list = ListProperty()
    tracked_entries = ListProperty()

    request_callback = ObjectProperty(None, allownone=True)
