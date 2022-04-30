""" Module for page GTD """

from kivy.lang import Builder
from kivy.properties import StringProperty, ObjectProperty

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
            issue_list_path: root.issue_list_path
            size_hint: None, 1           
""")


class GtdPage(globalcontent.ContentPage):
    mqttc = ObjectProperty(None)
    issue_list_path = StringProperty(None)
