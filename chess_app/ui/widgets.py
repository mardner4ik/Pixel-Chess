from kivy.animation import Animation
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import ListProperty, NumericProperty, BooleanProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button


class PixelButton(Button):
    ripple_x = NumericProperty(0)
    ripple_y = NumericProperty(0)
    ripple_radius = NumericProperty(0)
    ripple_alpha = NumericProperty(0)
    ripple_color = ListProperty([.72, .48, .37, 1])
    fill_color = ListProperty([.85, .83, .79, 1])
    text_color = ListProperty([.12, .12, .12, 1])
    corner_radius = NumericProperty(dp(24))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._ripple_fade = None
        self._pressed_touch = None

    def on_press(self):
        # Touch feedback is drawn with the shared ripple. Do not animate the
        # button's base fill: menu actions may replace that fill while release
        # callbacks are running (for example, the active menu state).
        pass

    def on_release(self):
        pass

    def on_touch_up(self, touch):
        result = super().on_touch_up(touch)
        if self._pressed_touch is touch:
            self._pressed_touch = None
            if self._ripple_fade is not None:
                self._ripple_fade.cancel()
            self._ripple_fade = Clock.schedule_once(self._fade_ripple, .18)
        return result

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos) and self.disabled is False:
            self._pressed_touch = touch
            if self._ripple_fade is not None:
                self._ripple_fade.cancel()
            self.ripple_x, self.ripple_y = touch.pos
            corners = ((self.x, self.y), (self.right, self.y), (self.x, self.top), (self.right, self.top))
            self.ripple_radius = 0
            self.ripple_alpha = 0
            Animation.cancel_all(self, "ripple_radius", "ripple_alpha")
            radius = max(((x - self.ripple_x) ** 2 + (y - self.ripple_y) ** 2) ** .5 for x, y in corners)
            # Keep the effect short and property-light so touch feedback never
            # competes with board updates on low-end Android GPUs.
            Animation(ripple_radius=radius, duration=.20, t="out_quad").start(self)
            self.ripple_alpha = .42
        return super().on_touch_down(touch)

    def _fade_ripple(self, *_):
        Animation(ripple_alpha=0, duration=.20, t="out_quad").start(self)


class MenuIconButton(PixelButton):
    pass


class AccentChoiceButton(PixelButton):
    selected = BooleanProperty(False)


class MenuPanel(BoxLayout):
    """A faded-out menu must let board touches pass through while disabled."""

    def on_touch_down(self, touch):
        if self.opacity <= .01:
            return False
        return super().on_touch_down(touch)


class RoundCard(BoxLayout):
    fill_color = ListProperty([.98, .97, .94, 1])
    corner_radius = NumericProperty(dp(28))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from kivy.graphics import Color, RoundedRectangle
        with self.canvas.before:
            self._fill_instruction = Color(*self.fill_color)
            self._shape_instruction = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[self.corner_radius])
        self.bind(pos=self._sync_shape, size=self._sync_shape,
                  fill_color=self._sync_fill, corner_radius=self._sync_shape)

    def _sync_shape(self, *_):
        self._shape_instruction.pos = self.pos
        self._shape_instruction.size = self.size
        self._shape_instruction.radius = [self.corner_radius]

    def _sync_fill(self, *_):
        self._fill_instruction.rgba = self.fill_color


BOT_POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="chess-bot")
_COORD_TEXTURES = {}
_PIECE_TEXTURES = {}
ACCENT_PALETTES = {
    "blue": (.26, .43, .91, 1),
    "green": (.15, .53, .35, 1),
    "violet": (.52, .34, .78, 1),
    "amber": (.76, .43, .04, 1),
}
