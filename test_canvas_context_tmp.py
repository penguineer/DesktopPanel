"""Identify what causes the RenderContext.pop_state crash"""
import traceback
from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.graphics import Color, Line, Rectangle
from kivy.clock import Clock
import globalcontent

# Test 1: Just a RelativeLayout with canvas.before drawing (no SyslogMessagePanel)
from kivy.lang import Builder
Builder.load_string("""
#:import SyslogMessagePanel syslog_messages.SyslogMessagePanel

<TestPageWithSyslog>:
    label: 'test'
    icon: 'assets/icon_system.png'

    BoxLayout:
        orientation: 'horizontal'
        spacing: 10
        padding: [0, 0, 10, 10]

        SyslogMessagePanel:
            id: syslog_panel
            size_hint_x: 0.5
            amqp_widget: root.amqp_widget
            amqp_queue: ''
            min_priority: 'error'
            acknowledge_after: 3600
            max_entries: 50
            message_callback: root.on_syslog_message

        BoxLayout:
            size_hint_x: 0.5
            orientation: 'horizontal'
            
            SimpleGraphWidget:
                size_hint: 1, 1
""")

from kivy.properties import ObjectProperty, DictProperty

class SimpleGraphWidget(RelativeLayout):
    """Minimal version of PowerHistoryGraph with canvas.before drawing"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(size=self._on_size)
    
    def _on_size(self, *args):
        self._redraw()
    
    def _redraw(self):
        self.canvas.before.clear()
        w, h = self.width, self.height
        if w <= 0 or h <= 0:
            return
        with self.canvas.before:
            Color(0.3, 0.3, 0.3, 1)
            Line(points=[0, 0, w-1, 0], width=1)
            Line(points=[0, h-1, w-1, h-1], width=1)
            Line(points=[0, 0, 0, h-1], width=1)
            Line(points=[w-1, 0, w-1, h-1], width=1)
        print(f"  SimpleGraphWidget._redraw OK ({w}x{h})")

class TestPageWithSyslog(globalcontent.ContentPage):
    amqp_widget = ObjectProperty(None, allownone=True)
    conf = DictProperty(None, allownone=True)
    
    def on_syslog_message(self, msg):
        pass
    
    def on_active(self, _instance, active):
        super().on_active(_instance, active)
        if active:
            self.notification = "None"

class TestApp(App):
    def build(self):
        sp = TestPageWithSyslog()
        sp.conf_lambda = lambda conf: conf.get("system", dict())
        
        ca = globalcontent.GlobalContentArea()
        ca.size = (800, 480)
        
        def run(dt):
            try:
                ca.register_content(sp)
                print("register_content OK")
            except Exception as e:
                print(f"ERROR: {type(e).__name__}: {e}")
                traceback.print_exc()
        
        Clock.schedule_once(run, 0.1)
        Clock.schedule_once(lambda dt: self.stop(), 2)
        return ca

TestApp().run()
