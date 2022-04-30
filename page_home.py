""" Module for page Home """

from kivy.lang import Builder

import globalcontent

Builder.load_string("""
<HomePage>:
    label: 'home'
    icon: 'assets/icon_home.png'

    Label:
        text: 'HOME'
""")


class HomePage(globalcontent.ContentPage):
    pass
