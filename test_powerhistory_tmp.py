"""Test PowerHistoryGraph instantiation"""
from kivy.app import App
from kivy.uix.widget import Widget

class TestApp(App):
    def build(self):
        from power import PowerHistoryGraph
        try:
            g = PowerHistoryGraph()
            print('Created graph:', g)
            print('width:', g.width, 'height:', g.height)
            # Try redraw
            g.width = 200
            g.height = 40
            print('Size set OK')
            g._redraw()
            print('Redraw OK')
        except Exception as e:
            import traceback
            print(f'ERROR: {type(e).__name__}: {e}')
            traceback.print_exc()
        finally:
            self.stop()
        return Widget()

TestApp().run()
