"""Debug the crash in SystemPage"""
import traceback
from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.clock import Clock
import sys

class TestApp(App):
    def build(self):
        import globalcontent
        import page_system
        import sys
        
        # Monkey-patch to catch the IndexError
        import kivy.graphics.instructions as gi
        original_pop_state = None
        
        sp = page_system.SystemPage()
        sp.conf_lambda = lambda conf: conf.get("system", dict())
        
        ca = globalcontent.GlobalContentArea()
        ca.size = (800, 480)
        
        Clock.schedule_once(lambda dt: self._run(ca, sp))
        Clock.schedule_once(lambda dt: self.stop(), 1.5)
        return ca
    
    def _run(self, ca, sp):
        try:
            ca.register_content(sp)
            print("register_content OK")
            ca.switch_to_label('system')
            print("switch_to_label OK - no immediate crash")
        except Exception as e:
            print(f"ERROR: {type(e).__name__}: {e}")
            traceback.print_exc()

TestApp().run()
