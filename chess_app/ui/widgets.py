from kivy.animation import Animation
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import ListProperty, NumericProperty, BooleanProperty, StringProperty
from kivy.graphics import Color, Rectangle, Line, Triangle, Ellipse
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
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
        self._pressed_touch = None
        self._ripple_fade_event = None

    def on_touch_down(self, touch):
        # ButtonBehavior still grabs touches for disabled buttons in some Kivy
        # versions. Return early so collapsed picker controls cannot sit on top
        # of the Advanced button and swallow its touch.
        if self.disabled:
            return False
        if self._pressed_touch is not None and self._pressed_touch is not touch:
            return False
        if self.collide_point(*touch.pos):
            # Cancel before resetting the animated properties. Resetting first
            # lets the previous ripple frame overwrite the new touch position.
            Animation.cancel_all(self, "ripple_radius", "ripple_alpha")
            if self._ripple_fade_event is not None:
                self._ripple_fade_event.cancel()
                self._ripple_fade_event = None
            self._pressed_touch = touch
            self.ripple_x, self.ripple_y = touch.pos
            self.ripple_radius = 0
            self.ripple_alpha = .30
            farthest = max(((x - self.ripple_x) ** 2 + (y - self.ripple_y) ** 2) ** .5
                           for x, y in ((self.x, self.y), (self.right, self.y),
                                        (self.x, self.top), (self.right, self.top)))
            Animation(ripple_radius=farthest, duration=.24, t="out_quad").start(self)
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        result = super().on_touch_up(touch)
        if self._pressed_touch is touch:
            self._pressed_touch = None
            if self._ripple_fade_event is not None:
                self._ripple_fade_event.cancel()
            self._ripple_fade_event = Clock.schedule_once(self._fade_ripple, .08)
        return result

    def _fade_ripple(self, *_):
        self._ripple_fade_event = None
        Animation.cancel_all(self, "ripple_alpha")
        Animation(ripple_alpha=0, duration=.16, t="out_quad").start(self)


class FlatPixelButton(Button):
    """ScrollView-safe button with no stencil canvas inherited from PixelButton."""

    ripple_x = NumericProperty(0)
    ripple_y = NumericProperty(0)
    ripple_radius = NumericProperty(0)
    ripple_alpha = NumericProperty(0)
    ripple_color = ListProperty([.72, .48, .37, 1])
    fill_color = ListProperty([.85, .83, .79, 1])
    text_color = ListProperty([.12, .12, .12, 1])
    corner_radius = NumericProperty(dp(24))

    def on_touch_down(self, touch):
        if self.disabled:
            return False
        if self.collide_point(*touch.pos):
            self._pressed_touch = touch
            self._start_ripple(*touch.pos)
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        handled = super().on_touch_up(touch)
        if getattr(self, '_pressed_touch', None) is touch:
            self._pressed_touch = None
            if getattr(self, '_ripple_fade_event', None):
                self._ripple_fade_event.cancel()
            self._ripple_fade_event = Clock.schedule_once(self._fade_ripple, .08)
        return handled

    def _start_ripple(self, x, y):
        Animation.cancel_all(self, 'ripple_radius', 'ripple_alpha')
        if getattr(self, '_ripple_fade_event', None):
            self._ripple_fade_event.cancel()
            self._ripple_fade_event = None
        self.ripple_x, self.ripple_y = x, y
        self.ripple_radius = 0
        self.ripple_alpha = .30
        edge_clearance = min(x - self.x, self.right - x, y - self.y, self.top - y)
        max_radius = max(0, edge_clearance - dp(2))
        Animation(ripple_radius=max_radius, duration=.28, t='out_quad').start(self)

    def _fade_ripple(self, *_):
        self._ripple_fade_event = None
        Animation.cancel_all(self, 'ripple_alpha')
        Animation(ripple_alpha=0, duration=.18, t='out_quad').start(self)


class MenuIconButton(PixelButton):
    pass


class AccentChoiceButton(PixelButton):
    selected = BooleanProperty(False)


class RoomEntryButton(FlatPixelButton):
    """ScrollView-safe room row button, without PixelButton's nested stencil."""

    fill_color = ListProperty([.90, .89, .86, 1])
    text_color = ListProperty([.12, .12, .12, 1])
    corner_radius = NumericProperty(dp(14))


class CountryFlag(Widget):
    """Tiny vector country flag, avoiding missing emoji glyphs in custom fonts."""

    country = StringProperty('UA')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self.redraw, size=self.redraw, country=self.redraw)
        self.redraw()

    def redraw(self, *_):
        self.canvas.clear()
        x, y, w, h = self.x, self.y, self.width, self.height
        if w <= 0 or h <= 0:
            return
        c = self.country.upper()
        if c in {'UN', 'ZZ', ''}:
            with self.canvas:
                Color(.18, .42, .62, 1)
                Ellipse(pos=(x, y), size=(w, h))
                Color(.92, .96, 1, 1)
                Line(ellipse=(x + w*.12, y + h*.08, w*.76, h*.84), width=max(1, w*.035))
                Line(ellipse=(x + w*.34, y + h*.08, w*.32, h*.84), width=max(1, w*.03))
                Line(points=(x+w*.15, y+h*.5, x+w*.85, y+h*.5), width=max(1, w*.03))
            return
        # Main stripe patterns cover countries used in the lobby and common IPs.
        stripes = {
            'UA': ['#0057B7', '#FFD700'], 'PL': ['#FFFFFF', '#DC143C'],
            'DE': ['#000000', '#DD0000', '#FFCE00'], 'FR': ['#0055A4', '#FFFFFF', '#EF4135'],
            'IT': ['#009246', '#FFFFFF', '#CE2B37'], 'NL': ['#AE1C28', '#FFFFFF', '#21468B'],
            'RU': ['#FFFFFF', '#0039A6', '#D52B1E'], 'AT': ['#ED2939', '#FFFFFF', '#ED2939'],
            'HU': ['#CE2939', '#FFFFFF', '#477050'], 'RO': ['#002B7F', '#FCD116', '#CE1126'],
            'ES': ['#AA151B', '#F1BF00', '#AA151B'], 'BG': ['#FFFFFF', '#00966E', '#D62612'],
            'IN': ['#FF9933', '#FFFFFF', '#138808'], 'JP': ['#FFFFFF'],
            'US': ['#B22234', '#FFFFFF', '#B22234', '#FFFFFF', '#B22234', '#FFFFFF', '#B22234'],
            'GB': ['#012169'], 'AU': ['#012169'], 'CA': ['#D80621', '#FFFFFF', '#D80621'],
            'BR': ['#009739'], 'TR': ['#E30A17'], 'CZ': ['#FFFFFF', '#D7141A'],
            'SE': ['#006AA7'], 'NO': ['#BA0C2F'], 'FI': ['#FFFFFF'], 'CH': ['#D52B1E'],
            'GR': ['#0D5EAF', '#FFFFFF', '#0D5EAF', '#FFFFFF', '#0D5EAF'],
            'IE': ['#169B62', '#FFFFFF', '#FF883E'], 'MX': ['#006847', '#FFFFFF', '#CE1126'],
        }
        colors = stripes.get(c, ['#9AA0A6', '#FFFFFF', '#9AA0A6'])
        with self.canvas:
            # White border and rounded-card-like corners are intentionally omitted
            # to keep this lightweight and crisp at small Android sizes.
            Color(1, 1, 1, 1)
            Rectangle(pos=(x, y), size=(w, h))
            if c in {'US'}:
                for i, hex_color in enumerate(colors):
                    Color(*_hex_rgb(hex_color))
                    Rectangle(pos=(x, y + h * (len(colors) - i - 1) / len(colors)), size=(w, h / len(colors) + .5))
                Color(0.08, 0.18, 0.38, 1)
                Rectangle(pos=(x, y + h * .52), size=(w * .46, h * .48))
            elif c in {'FR', 'IT', 'NL', 'CA', 'IE'}:
                for i, hex_color in enumerate(colors):
                    Color(*_hex_rgb(hex_color))
                    Rectangle(pos=(x + w * i / 3, y), size=(w / 3 + .5, h))
            elif c in {'JP', 'BR', 'GB', 'AU', 'TR', 'CZ', 'SE', 'NO', 'CH'}:
                Color(*_hex_rgb(colors[0]))
                Rectangle(pos=(x, y), size=(w, h))
                if c == 'JP':
                    Color(.74, .05, .18, 1)
                    Ellipse(pos=(x + w * .34, y + h * .20), size=(w * .32, h * .60))
                elif c == 'BR':
                    Color(1, .86, .1, 1)
                    Triangle(points=(x+w*.5,y+h*.82,x+w*.88,y+h*.5,x+w*.5,y+h*.18))
                    Color(.05, .23, .55, 1)
                    Ellipse(pos=(x+w*.39,y+h*.31), size=(w*.22,h*.38))
                elif c in {'GB', 'AU'}:
                    Color(1,1,1,1); Line(points=(x,y,x+w,y+h),width=max(1,w*.16)); Line(points=(x,y+h,x+w,y),width=max(1,w*.16))
                    Color(.78,.08,.16,1); Line(points=(x,y,x+w,y+h),width=max(1,w*.07)); Line(points=(x,y+h,x+w,y),width=max(1,w*.07))
                    Color(1,1,1,1); Rectangle(pos=(x+w*.40,y),size=(w*.20,h)); Rectangle(pos=(x,y+h*.40),size=(w,h*.20))
                    Color(.78,.08,.16,1); Rectangle(pos=(x+w*.45,y),size=(w*.10,h)); Rectangle(pos=(x,y+h*.44),size=(w,h*.12))
                elif c == 'CZ':
                    Color(.05,.22,.53,1); Triangle(points=(x,y,x+w*.52,y+h*.5,x,y+h))
                elif c in {'SE','NO','CH'}:
                    Color(1,1,1,1)
                    if c == 'CH':
                        Rectangle(pos=(x+w*.43,y+h*.2),size=(w*.14,h*.6)); Rectangle(pos=(x+w*.2,y+h*.42),size=(w*.6,h*.16))
                    else:
                        Rectangle(pos=(x+w*.30,y),size=(w*.12,h)); Rectangle(pos=(x,y+h*.42),size=(w,h*.16))
                        if c == 'NO':
                            Color(.02,.16,.34,1); Rectangle(pos=(x+w*.27,y),size=(w*.18,h)); Rectangle(pos=(x,y+h*.37),size=(w,h*.26))
                            Color(1,1,1,1); Rectangle(pos=(x+w*.32,y),size=(w*.08,h)); Rectangle(pos=(x,y+h*.43),size=(w,h*.14))
            else:
                for i, hex_color in enumerate(colors):
                    Color(*_hex_rgb(hex_color))
                    Rectangle(pos=(x, y + h * (len(colors) - i - 1) / len(colors)), size=(w, h / len(colors) + .5))
                if c == 'CA':
                    Color(.78, .04, .12, 1)
                    Triangle(points=(x+w*.5,y+h*.68,x+w*.43,y+h*.46,x+w*.5,y+h*.54,x+w*.57,y+h*.46))


def _hex_rgb(value):
    value = value.lstrip('#')
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)) + (1,)


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
        from math import cos, radians, sin

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
            elif self.icon == "settings":
                Ellipse(pos=(cx-r*.30, cy-r*.30), size=(r*.60, r*.60))
                for angle in range(0, 360, 45):
                    start = radians(angle)
                    Line(points=(cx+cos(start)*r*.34, cy+sin(start)*r*.34,
                                 cx+cos(start)*r*.72, cy+sin(start)*r*.72),
                         width=width*1.3, cap="round")
            elif self.icon == "chevron":
                Line(points=(cx-r*.20, cy+r*.38, cx+r*.18, cy,
                             cx-r*.20, cy-r*.38), width=width, cap="round",
                     joint="round")
            elif self.icon in {"down", "up"}:
                points = ((cx-r*.40, cy+r*.18, cx, cy-r*.18, cx+r*.40, cy+r*.18)
                          if self.icon == "down" else
                          (cx-r*.40, cy-r*.18, cx, cy+r*.18, cx+r*.40, cy-r*.18))
                Line(points=points, width=width, cap="round", joint="round")
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

        self.content = FloatLayout()
        self.icon_widget = SettingsIcon(icon=icon, tint=self.icon_color,
                                        size_hint=(None, None), size=(dp(22), dp(22)))
        self.title_label = Label(text=title, color=self.text_color,
                                 font_size="14sp", bold=True, halign="left",
                                 valign="middle",
                                 size_hint=(None, None))
        self.title_label.bind(size=lambda widget, size: setattr(widget, "text_size", size))
        self.detail_label = Label(text=detail, color=self.muted_color,
                                  font_size="12sp", halign="left", valign="middle",
                                  size_hint=(None, None))
        self.detail_label.bind(size=lambda widget, size: setattr(widget, "text_size", size))
        self.arrow_label = SettingsIcon(icon="chevron", tint=self.muted_color,
                                        size_hint=(None, None), size=(dp(16), dp(16)))
        self.content.add_widget(self.icon_widget)
        self.content.add_widget(self.title_label)
        self.content.add_widget(self.detail_label)
        self.content.add_widget(self.arrow_label)
        self.add_widget(self.content)
        self._layout_trigger = Clock.create_trigger(self._layout_content, 0)
        self.bind(pos=self._layout_trigger, size=self._layout_trigger,
                  x=self._layout_trigger, y=self._layout_trigger,
                  width=self._layout_trigger, height=self._layout_trigger,
                  parent=self._layout_trigger,
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
        inset = dp(12)
        icon_size = min(dp(22), max(dp(18), self.height - dp(16)))
        self.icon_widget.size = (icon_size, icon_size)
        self.icon_widget.pos = (self.x + inset, self.center_y - icon_size / 2)
        arrow_width = dp(16)
        self.arrow_label.pos = (self.right - dp(10) - arrow_width,
                                self.center_y - self.arrow_label.height / 2)
        text_x = self.icon_widget.right + dp(9)
        text_right = self.arrow_label.x - dp(6)
        text_width = max(dp(20), text_right - text_x)
        self.title_label.pos = (text_x, self.center_y + dp(1))
        self.title_label.size = (text_width, dp(19))
        self.detail_label.pos = (text_x, self.center_y - dp(19))
        self.detail_label.size = (text_width, dp(17))

    def _sync_content_colors(self, *_):
        if not hasattr(self, "title_label"):
            return
        self.title_label.color = self.text_color
        self.detail_label.color = self.muted_color
        self.arrow_label.tint = self.muted_color
        self.icon_widget.tint = self.icon_color
