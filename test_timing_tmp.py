"""Determine when _on_size is called relative to drawing"""
import traceback
from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.graphics import Color, Line
from kivy.clock import Clock
from kivy.lang import Builder
import globalcontent
from kivy.properties import ObjectProperty, DictProperty
from kivy.core.window import Window

draw_call_count = [0]
on_size_call_count = [0]

original_on_draw = None

Builder.load_string("""
<TestPage2>:
    label: 'test'
    icon: 'assets/icon_system.png'
    BoxLayout:
        size_hint_x: 1
        TimingWidget:
            size_hint: 1, 1
""")

class TimingWidget(RelativeLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(size=self._on_size)
    
    def _on_size(self, *args):
        on_size_call_count[0] += 1
        print(f"  _on_size #{on_size_call_count[0]}, draw_count={draw_call_count[0]}, size={self.size}")
        # The crash happens here:
        self.canvas.before.clear()
        w, h = self.width, self.height
        if w <= 0 or h <= 0:
            return
        with self.canvas.before:
            Color(0.3, 0.3, 0.3, 1)
            Line(points=[0, 0, w-1, 0], width=1)
        print(f"  canvas.before updated OK")

class TestPage2(globalcontent.ContentPage):
    conf = DictProperty(None, allownone=True)
    def on_active(self, _instance, active):
        super().on_active(_instance, active)

class TestApp(App):
    def build(self):
        sp = TestPage2()
        ca = globalcontent.GlobalContentArea()
        ca.size = (800, 480)
        
        # Patch Window.on_draw to count draws
        orig_on_draw = Window.on_draw
        def patched_on_draw(self_win):
            draw_call_count[0] += 1
            return orig_on_draw(self_win)
        Window.on_draw = patched_on_draw
        
        def run(dt):
            print(f"Before register_content: draw_count={draw_call_count[0]}")
            try:
                ca.register_content(sp)
                print(f"After register_content: draw_count={draw_call_count[0]}")
            except Exception as e:
                print(f"ERROR: {type(e).__name__}: {e}")
                traceback.print_exc()
        
        Clock.schedule_once(run, 0.1)
        Clock.schedule_once(lambda dt: self.stop(), 2)
        return ca

TestApp().run()
