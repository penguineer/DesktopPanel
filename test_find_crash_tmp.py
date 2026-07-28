"""Find root cause of RenderContext.pop_state IndexError"""
import traceback
from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.clock import Clock

# Monkey-patch pop_state to log when it fails
import kivy.graphics.instructions as gi

class TestApp(App):
    def build(self):
        import globalcontent
        import page_system
        
        sp = page_system.SystemPage()
        sp.conf_lambda = lambda conf: conf.get("system", dict())
        
        ca = globalcontent.GlobalContentArea()
        ca.size = (800, 480)
        
        def run(dt):
            try:
                ca.register_content(sp)
                print("register_content OK - system page should be shown")
            except Exception as e:
                print(f"ERROR: {type(e).__name__}: {e}")
                traceback.print_exc()
        
        Clock.schedule_once(run, 0.1)
        Clock.schedule_once(lambda dt: self.stop(), 2)
        return ca

TestApp().run()
