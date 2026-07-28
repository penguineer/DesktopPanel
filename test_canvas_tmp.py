"""Test canvas.before.clear() and with canvas.before: pattern"""
import traceback
from kivy.app import App
from kivy.uix.relativelayout import RelativeLayout
from kivy.graphics import Color, Line, Rectangle
from kivy.clock import Clock
from kivy.uix.floatlayout import FloatLayout

class TestWidget(RelativeLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(size=self._on_size)
        
    def _on_size(self, *args):
        print(f"_on_size called: {self.size}")
        self._redraw()
    
    def _redraw(self):
        print(f"  _redraw() called, size={self.size}")
        self.canvas.before.clear()
        w = self.width
        h = self.height
        if w <= 0 or h <= 0:
            print(f"  skipping (size={w}x{h})")
            return
        with self.canvas.before:
            Color(0.3, 0.3, 0.3, 1)
            Line(points=[0, 0, w-1, 0], width=1)
            Line(points=[0, h-1, w-1, h-1], width=1)
        print(f"  _redraw() completed OK")

class TestApp(App):
    def build(self):
        root = FloatLayout()
        
        def start(dt):
            try:
                w = TestWidget(size=(200, 40), size_hint=(None, None), pos=(100, 200))
                root.add_widget(w)
                print("Widget added OK")
            except Exception as e:
                print(f"ERROR adding widget: {e}")
                traceback.print_exc()
        
        Clock.schedule_once(start, 0.1)
        Clock.schedule_once(lambda dt: self.stop(), 2)
        return root

TestApp().run()
