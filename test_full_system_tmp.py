"""Test SystemPage complete instantiation"""
import traceback
from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.clock import Clock
import sys

errors = []

class TestApp(App):
    def build(self):
        import globalcontent
        import page_system

        # Simulate what app.py does
        sp = page_system.SystemPage()
        sp.conf_lambda = lambda conf: conf.get("system", dict())
        
        ca = globalcontent.GlobalContentArea()
        ca.size = (800, 480)
        
        Clock.schedule_once(lambda dt: self._register(ca, sp))
        Clock.schedule_once(lambda dt: self._switch(ca, sp), 0.5)
        Clock.schedule_once(lambda dt: self.stop(), 1.5)
        return ca
    
    def _register(self, ca, sp):
        try:
            ca.register_content(sp)
            print("register_content OK")
        except Exception as e:
            print(f"REGISTER ERROR: {type(e).__name__}: {e}")
            traceback.print_exc()
    
    def _switch(self, ca, sp):
        try:
            ca.switch_to_label('system')
            print("switch_to_label OK")
        except Exception as e:
            print(f"SWITCH ERROR: {type(e).__name__}: {e}")
            traceback.print_exc()

TestApp().run()
