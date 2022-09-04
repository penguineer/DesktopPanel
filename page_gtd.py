""" Module for page GTD """

from kivy.lang import Builder

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
            conf: root.conf.get("issuelist", {}) if root.conf else {}
            size_hint: None, 1           
""")


class GtdPage(globalcontent.ContentPage):
    pass
