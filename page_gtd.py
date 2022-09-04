""" Module for page GTD """

from kivy.lang import Builder
from kivy.properties import ObjectProperty, DictProperty

import globalcontent

Builder.load_string("""
#:import IssueList issues.IssueList

<GtdPage>:
    label: 'system'
    icon: 'assets/icon_gtd.png'

    BoxLayout:
        orientation: 'horizontal'

        Label:
            text: ''

        IssueList:
            id: issuelist
            conf: root.conf.get("issuelist", None) if root.conf else None
            size_hint: None, 1           
""")


class GtdPage(globalcontent.ContentPage):
    conf = DictProperty()
    mqttc = ObjectProperty(None)
