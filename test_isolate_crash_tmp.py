"""Isolate crash - does it happen without SyslogMessagePanel?"""
import traceback
from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.graphics import Color, Line
from kivy.clock import Clock
from kivy.lang import Builder
import globalcontent
from kivy.properties import ObjectProperty, DictProperty

# TEST: SimpleGraphWidget WITHOUT SyslogMessagePanel
Builder.load_string("""
<PageWithoutSyslog>:
    label: 'test'
    icon: 'assets/icon_system.png'
    BoxLayout:
        size_hint_x: 1
        SimpleGraphWidget2:
            size_hint: 1, 1
""")

class SimpleGraphWidget2(RelativeLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(size=self._on_size)
    
    def _on_size(self, *args):
        self.canvas.before.clear()
        w, h = self.width, self.height
        if w <= 0 or h <= 0:
            return
        with self.canvas.before:
            Color(0.3, 0.3, 0.3, 1)
            Line(points=[0, 0, w-1, 0], width=1)

class PageWithoutSyslog(globalcontent.ContentPage):
    conf = DictProperty(None, allownone=True)
    def on_active(self, _instance, active):
        super().on_active(_instance, active)

class TestApp(App):
    def build(self):
        sp = PageWithoutSyslog()
        ca = globalcontent.GlobalContentArea()
        ca.size = (800, 480)
        
        def run(dt):
            try:
                ca.register_content(sp)
                print("register_content OK - without SyslogMessagePanel")
            except Exception as e:
                print(f"ERROR: {type(e).__name__}: {e}")
                traceback.print_exc()
        
        Clock.schedule_once(run, 0.1)
        Clock.schedule_once(lambda dt: self.stop(), 2)
        return ca

TestApp().run()
