"""Issue handling"""

from kivy import Logger
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import StringProperty, ListProperty, ColorProperty, DictProperty
from kivy.uix.boxlayout import BoxLayout

from reloadable_json import JsonObserver

Builder.load_string("""
<IssueEntry>
    orientation: 'horizontal'
    size_hint: 1, None
    spacing: 4

    Label:
        text: root.issue_id
        size: 50, 0
        size_hint_x: None
        text_size: self.size[0]-12, self.size[1]
        halign: 'right'
        valign: 'center'
        font_size: 14
        font_name: 'assets/FiraMono-Regular.ttf'
        color: root.id_color

        canvas.before:
            Color:
                rgba: root.id_background
            RoundedRectangle:
                pos: self.pos[0] + 2, self.pos[1] + 1                
                size: self.size[0] - 4, self.size[1] - 2
                radius: [5,5]        

    Label:
        text: root.issue_label
        text_size: self.size[0], self.size[1]
        halign: 'left'
        valign: 'center'
        font_size: 14
        color: root.label_color

<IssueList>
    orientation: 'vertical'
    size: 300, 300
    padding: 4
    spacing: 4

    canvas.before:
        Color:
            rgba: root.border_color
        Line:
            rounded_rectangle: self.pos[0]+2, self.pos[1]+2, self.size[0]-4, self.size[1]-4, 5, 100
        Line:
            points: 
                root.pos[0] + 6, \\ 
                root.pos[1] + root.size[1] - 24 - 4, \\ 
                root.pos[0] + root.size[0] - 6, \\ 
                root.pos[1] + root.size[1] - 24 - 4 

    Label:
        text: root.conf.get('label', 'GTD') if root.conf else "GTD"
        size_hint: 1, None
        size: 0, 24
        color: root.header_color
        bold: True

    RecycleView:    
        id: rv
        data: root.entries
        viewclass: 'IssueEntry'
        size_hint: 1, 1

        RecycleBoxLayout:
            orientation: 'vertical'
            default_size: 0, 20
""")


class IssueEntry(BoxLayout):
    issue_label = StringProperty()
    issue_id = StringProperty()

#    id_color = ColorProperty([0 / 256, 0 / 256, 0 / 256, 1])
    id_color = ColorProperty([256 / 256, 256 / 256, 256 / 256, 1])
#    id_background = ColorProperty([0 / 256, 132 / 256, 176 / 256, 1])
    id_background = ColorProperty([24 / 256, 56 / 256, 107 / 256, 1])
    label_color = ColorProperty([256 / 256, 256 / 256, 256 / 256, 1])


class IssueList(BoxLayout):
    conf = DictProperty(None)

    entries = ListProperty()

    border_color = ColorProperty([249 / 256, 176 / 256, 0 / 256, 1])
    header_color = ColorProperty([249 / 256, 176 / 256, 0 / 256, 1])

    issue_list_path = StringProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.issue_list = None

        self._observer = None

        self.bind(conf=self._on_conf)
        self.property('conf').dispatch(self)

    def __del__(self):
        if self._observer is not None:
            self._observer.teardown()

    def _on_conf(self, _instance, conf: dict) -> None:
        if self._observer:
            self._observer.teardown()

        path = conf.get("path", None) if conf else None

        if path is not None:
            self._observer = JsonObserver(path,
                                          self.update_issue_list,
                                          self._border_mark)
            try:
                self._observer.setup()
                self._observer.on_modified(None)
            except FileNotFoundError as e:
                Logger.warning("Issues: %s", e)
                self._border_mark(failed=True)

    def update_issue_list(self, issue_list):
        self.issue_list = issue_list

        self.entries.clear()

        for issue in issue_list['issues']:
            self.entries.append({
                'opacity': 1,
                'issue_id': str(issue['id']),
                'issue_label': issue['label'],
                'size_hint': [1, None]
            })

        self.entries.append({
            'issue_id': '',
            'issue_label': '',
            'opacity': 0,
            'size_hint': [1, 1]
        })

        Clock.schedule_once(lambda dt: self.ids.rv.refresh_from_data())

    def _border_mark(self, failed: bool) -> None:
        if failed:
            self.border_color = [228 / 256, 5 / 256, 41 / 256, 1]
            self.header_color = [228 / 256, 5 / 256, 41 / 256, 1]
        else:
            self.border_color = [249 / 256, 176 / 256, 0 / 256, 1]
            self.header_color = [249 / 256, 176 / 256, 0 / 256, 1]
