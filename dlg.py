from kivy.lang import Builder
from kivy.properties import ColorProperty, StringProperty, ObjectProperty
from kivy.uix.modalview import ModalView

Builder.load_string("""
<FullscreenTimedModal>:
    #:set button_size 48

    canvas.before:
        Color:
            rgba: root.background_color
        Rectangle:
            pos: self.pos
            size: self.size

    canvas:
        #:set button_radius 5
        Color:
            rgba: root.border_color
        Line:
            rounded_rectangle: self.pos[0]+2, self.pos[1]+2, self.size[0]-4, self.size[1]-4, 5, 100

        Line:
            points: 
                self.size[0]-8-button_size, self.size[1]-8, \
                self.size[0]-8-button_size, self.size[1]-8-button_size+button_radius
            width: 1
            cap: 'none'

        Line:
            points: 
                self.size[0]-8-button_size+button_radius, self.size[1]-8-button_size, \
                self.size[0]-8, self.size[1]-8-button_size
            width: 1
            cap: 'none'

        Line:
            circle:
                self.size[0]-8-button_size+button_radius, self.size[1]-8-button_size+button_radius,\
                button_radius, \
                180, 270, \
                4
            width: 1
            cap: 'none'
    
        Line:
            points: 
                8, self.size[1]-8-button_size, \
                self.size[0]-button_size-12, self.size[1]-8-button_size
            width: 1
            cap: 'none'
    
    AnchorLayout:
        anchor_x: 'right'
        anchor_y: 'top'
        padding: 4
    
        Button:
            id: CloseBtn
            text: ''
            size: [button_size, button_size]
            size_hint: [None, None]
            
            background_normal: ''
            background_down: ''
            background_color: 0, 0, 0, 0
            
            Image:
                source: 'assets/close.png'
                x: self.parent.x + (button_size/4) - 2
                y: self.parent.y + (button_size/4) - 2
                size: (button_size/2, button_size/2)
                color: root.text_color

    AnchorLayout:
        anchor_x: 'center'
        anchor_y: 'top'
        padding: -20
        
        Label:
            size_hint: [1, None]
            text: root.title
            color: root.text_color
            valign: 'middle'
            font_size: 24
""")


class FullscreenTimedModal(ModalView):
    background_color = ColorProperty([0, 0, 0, 1])
    """Background color, in the format (r, g, b, a).

    :attr:`background_color` is a :class:`~kivy.properties.ColorProperty` and
    defaults to [1, 1, 1, 1].
    """

    border_color = ColorProperty([77 / 256, 77 / 256, 76 / 256, 1])
    """Border color, in the format (r, g, b, a).

    :attr:`border_color` is a :class:`~kivy.properties.ColorProperty` and
    defaults to [77 / 256, 77 / 256, 76 / 256, 1].
    """

    text_color = ColorProperty([249 / 256, 176 / 256, 0 / 256, 1])
    """Border color, in the format (r, g, b, a).

    :attr:`text_color` is a :class:`~kivy.properties.ColorProperty` and
    defaults to [249 / 256, 176 / 256, 0 / 256, 1].
    """

    title = StringProperty("")

    screensaver = ObjectProperty(None, allownone=True)
    """ Expects a screensaver instance. If set, the dialog will disable the screensaver
        while it is open.
    """

    def __init__(self, title=None, **kwargs):
        super(FullscreenTimedModal, self).__init__(**kwargs)

        self.ids.CloseBtn.bind(on_press=self.dismiss)

        self.bind(on_open=self._on_open)
        self.bind(on_dismiss=self._on_dismiss)

        if title is not None:
            self.title = title

    def is_inactive(self):
        return self._window is None

    def _on_open(self, _e):
        if self.screensaver:
            self.screensaver.disabled = True

    def _on_dismiss(self, _e):
        if self.screensaver:
            self.screensaver.disabled = False

        # return False to actually dismiss the window
        return False
