"""Test SystemPage instantiation and display"""
import traceback
from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.floatlayout import FloatLayout
from kivy.clock import Clock

class TestApp(App):
    def build(self):
        try:
            import page_system
            import globalcontent
            
            sp = page_system.SystemPage()
            print('SystemPage created:', sp)
            print('size:', sp.size)
            
            root = FloatLayout(size=(800, 480))
            root.add_widget(sp)
            print('Added to layout OK')
            sp.size = (800, 420)
            sp.pos = (0, 0)
            print('Size set OK, no crash')
        except Exception as e:
            print(f'ERROR: {type(e).__name__}: {e}')
            traceback.print_exc()
        
        Clock.schedule_once(lambda dt: self.stop(), 1)
        return FloatLayout()

TestApp().run()
