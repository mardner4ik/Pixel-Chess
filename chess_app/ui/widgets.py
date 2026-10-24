from kivy.animation import Animation
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import ListProperty, NumericProperty, BooleanProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.widget import Widget


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


class ToastMessage(BoxLayout):
    """Small, non-modal confirmation shown briefly above the board."""

    def __init__(self, message, **kwargs):
        super().__init__(orientation="horizontal", **kwargs)
        from kivy.graphics import Color, RoundedRectangle
        from kivy.uix.label import Label

        with self.canvas.before:
            self._toast_color = Color(.16, .16, .15, .96)
            self._toast_shape = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(22)])
        self.bind(pos=self._sync_toast, size=self._sync_toast)
        label = Label(text=message, color=(.97, .96, .93, 1),
                      font_size="15sp", bold=True, halign="center", valign="middle")
        label.bind(size=lambda widget, size: setattr(widget, "text_size", size))
        self.add_widget(label)

    def _sync_toast(self, *_):
        self._toast_shape.pos = self.pos
        self._toast_shape.size = self.size


class SettingsIcon(Widget):
    """Small vector icon drawn with Kivy primitives (independent of font glyphs)."""

    icon = StringProperty("music")
    tint = ListProperty([.65, .40, .31, 1])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._redraw_icon, size=self._redraw_icon,
                  icon=self._redraw_icon, tint=self._redraw_icon)
        self._redraw_icon()

    def _redraw_icon(self, *_):
        from kivy.graphics import Color, Ellipse, Line, RoundedRectangle, Triangle

        self.canvas.clear()
        x, y = self.pos
        w, h = self.size
        if w <= 0 or h <= 0:
            return
        cx, cy = x + w / 2, y + h / 2
        # Keep the glyph comfortably inside its badge; board grid strokes used
        # to extend beyond the circular background on compact settings rows.
        r = min(w, h) * .40
        color = self.tint
        with self.canvas:
            Color(color[0], color[1], color[2], .16)
            Ellipse(pos=(cx-r, cy-r), size=(2*r, 2*r))
            Color(*color)
            width = max(1, dp(1.7))
            if self.icon == "clock":
                Line(circle=(cx, cy, r * .58), width=width)
                Line(points=(cx, cy, cx, cy + r * .34), width=width, cap="round")
                Line(points=(cx, cy, cx + r * .28, cy - r * .12), width=width, cap="round")
                Ellipse(pos=(cx-dp(2), cy-dp(2)), size=(dp(4), dp(4)))
            elif self.icon == "board":
                edge = r * .68
                left, bottom = cx-edge, cy-edge
                Line(rounded_rectangle=(left, bottom, 2*edge, 2*edge, dp(2)), width=width)
                for offset in (-edge/3, edge/3):
                    Line(points=(cx+offset, bottom, cx+offset, bottom+2*edge), width=width)
                    Line(points=(left, cy+offset, left+2*edge, cy+offset), width=width)
            elif self.icon == "piece":
                head = dp(5)
                Ellipse(pos=(cx-head/2, cy+r*.42-head/2), size=(head, head))
                Triangle(points=(cx-r*.34, cy-r*.22, cx+r*.34, cy-r*.22,
                                 cx+r*.18, cy+r*.22))
                RoundedRectangle(pos=(cx-r*.45, cy-r*.47), size=(r*.9, dp(4)), radius=[dp(2)])
            elif self.icon == "palette":
                for ox, oy, scale in ((-.35, .25, .20), (.25, .30, .18),
                                      (-.24, -.28, .19), (.32, -.25, .16)):
                    Ellipse(pos=(cx+ox*r-scale*r, cy+oy*r-scale*r),
                            size=(2*scale*r, 2*scale*r))
            elif self.icon == "volume":
                left = cx-r*.48
                Triangle(points=(left, cy-r*.20, left+r*.42, cy-r*.20, left+r*.42, cy+r*.20))
                RoundedRectangle(pos=(left-r*.12, cy-r*.22), size=(r*.28, r*.44), radius=[dp(1)])
                Line(circle=(cx+r*.05, cy, r*.38, -55, 55), width=width)
                Line(circle=(cx+r*.05, cy, r*.62, -52, 52), width=width)
            else:  # music note
                head = dp(5)
                Ellipse(pos=(cx-r*.44, cy-r*.38), size=(head, head*.72))
                Ellipse(pos=(cx+r*.08, cy-r*.20), size=(head, head*.72))
                Line(points=(cx-r*.30, cy-r*.04, cx-r*.30, cy+r*.48,
                             cx+r*.22, cy+r*.62, cx+r*.22, cy+r*.13),
                     width=width, cap="round", joint="round")


class IconActionButton(PixelButton):
    """A button with a drawn icon, a title, and an optional value subtitle."""

    muted_color = ListProperty([.37, .37, .35, 1])
    icon_color = ListProperty([.65, .40, .31, 1])

    def __init__(self, icon, title, detail="", **kwargs):
        super().__init__(text="", **kwargs)
        from kivy.uix.label import Label

        self.content = BoxLayout(orientation="horizontal", spacing=dp(10),
                                 padding=(dp(10), 0, dp(8), 0))
        self.icon_widget = SettingsIcon(icon=icon, tint=self.icon_color,
                                        size_hint=(None, None), size=(dp(22), dp(22)))
        self.title_label = Label(text=title, color=self.text_color,
                                 font_size="14sp", bold=True, halign="left",
                                 valign="bottom", shorten=True, shorten_from="right")
        self.detail_label = Label(text=detail, color=self.muted_color,
                                  font_size="12sp", halign="left", valign="top",
                                  shorten=True, shorten_from="right")
        self.text_stack = BoxLayout(orientation="vertical", spacing=-dp(1))
        self.text_stack.add_widget(self.title_label)
        self.text_stack.add_widget(self.detail_label)
        self.arrow_label = Label(text="›", color=self.muted_color,
                                 font_size="22sp", size_hint_x=None, width=dp(18))
        self.content.add_widget(self.icon_widget)
        self.content.add_widget(self.text_stack)
        self.content.add_widget(self.arrow_label)
        self.add_widget(self.content)
        self.bind(pos=self._layout_content, size=self._layout_content,
                  text_color=self._sync_content_colors,
                  muted_color=self._sync_content_colors,
                  icon_color=self._sync_content_colors)
        self._layout_content()
        self._sync_content_colors()

    def _layout_content(self, *_):
        if not hasattr(self, "content"):
            return
        self.content.pos = self.pos
        self.content.size = self.size

    def _sync_content_colors(self, *_):
        if not hasattr(self, "title_label"):
            return
        self.title_label.color = self.text_color
        self.detail_label.color = self.muted_color
        self.arrow_label.color = self.muted_color
        self.icon_widget.tint = self.icon_color
