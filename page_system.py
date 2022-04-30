""" Module for page System """

from kivy.lang import Builder

import globalcontent

Builder.load_string("""
<SystemPage>:
    label: 'system'
    icon: 'assets/icon_system.png'

    Label:
        text: 'SYSTEM'            
""")


class SystemPage(globalcontent.ContentPage):
    pass
