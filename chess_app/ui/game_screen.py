from __future__ import annotations

import chess
import time
import webbrowser
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.animation import Animation
from kivy.properties import ListProperty, StringProperty, NumericProperty, BooleanProperty, ColorProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.uix.modalview import ModalView
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.graphics import Canvas, PushMatrix, PopMatrix, Translate

from chess_app.core.engine import ChessEngine
from chess_app.ui.system_theme import is_dark_mode

class PixelButton(Button):
    ripple_x = NumericProperty(0)
    ripple_y = NumericProperty(0)
    ripple_radius = NumericProperty(0)
    ripple_alpha = NumericProperty(0)
    ripple_color = ListProperty([.72, .48, .37, 1])
    fill_color = ListProperty([.85, .83, .79, 1])
    text_color = ListProperty([.12, .12, .12, 1])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._ripple_fade = None
        self._pressed_touch = None

    def on_press(self):
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
            self.ripple_alpha = .30
        return super().on_touch_down(touch)

    def _fade_ripple(self, *_):
        Animation(ripple_alpha=0, duration=.20, t="out_quad").start(self)


class MenuIconButton(PixelButton):
    pass


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


class ChessBoard(Widget):
    drag_scale = NumericProperty(1.0)
    selected = ListProperty([])
    targets = ListProperty([])
    last_move = ListProperty([])
    check_square = StringProperty("")
    animating = BooleanProperty(False)
    previous_move = ListProperty([])
    flipped = BooleanProperty(False)

    def __init__(self, screen, **kwargs):
        super().__init__(**kwargs)
        self.screen = screen
        self._drag_square = None
        self._drag_piece = None
        self._press_square = None
        self._press_piece = None
        self._drag_touch_offset = (0, 0)
        self._drag_last_pos = None
        self._drag_moved = False
        self._drop_start_pos = None
        self._animation_start_pos = None
        self._drag_translate = None
        self._board_group = Canvas()
        self._static_group = Canvas()
        self._moving_group = Canvas()
        self._move_translation = None
        self._board_dirty = True
        # Coalesce bursts of state changes into a single canvas rebuild per frame.
        self._redraw_trigger = Clock.create_trigger(self._redraw_now, 0)
        self.canvas.add(self._board_group)
        self.canvas.add(self._static_group)
        self.canvas.add(self._moving_group)
        self.bind(pos=self._geometry_changed, size=self._geometry_changed,
                  flipped=self._orientation_changed)
        self.bind(anim_progress=self._update_animated_piece)
        self.redraw()

    def _geometry_changed(self, *_):
        self._board_dirty = True
        self.redraw()

    def _orientation_changed(self, *_):
        self._board_dirty = True
        self.redraw()

    def invalidate_board(self):
        self._board_dirty = True
        self.redraw()

    def square_at(self, pos):
        x, y = pos[0] - self.x, pos[1] - self.y
        size = min(self.width, self.height)
        size /= 8
        ox = (self.width - size * 8) / 2
        oy = (self.height - size * 8) / 2
        x -= ox
        y -= oy
        if size <= 0 or x < 0 or y < 0 or x >= size * 8 or y >= size * 8:
            return None
        file, rank = int(x // size), int(y // size)
        if self.flipped:
            file, rank = 7 - file, 7 - rank
        return chess.square(file, rank)

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        square = self.square_at(touch.pos)
        if square is not None:
            touch.ud["chess_start_square"] = square
            touch.ud["chess_start_pos"] = (touch.x, touch.y)
            board = self.screen.engine.board
            piece = board.piece_at(square)
            can_drag = bool(piece and piece.color == self.screen.player_color
                            and board.turn == self.screen.player_color)
            touch.ud["chess_piece_start"] = can_drag
            self._press_square = square
            self._press_piece = piece if can_drag else None
            self._drag_moved = False
            touch.grab(self)
        return True

    def _touch_offset(self, square, pos):
        size = min(self.width, self.height) / 8
        ox = self.x + (self.width - size * 8) / 2
        oy = self.y + (self.height - size * 8) / 2
        file, rank = chess.square_file(square), chess.square_rank(square)
        if self.flipped:
            file, rank = 7-file, 7-rank
        center = (ox + (file + .5) * size, oy + (rank + .5) * size)
        return pos[0] - center[0], pos[1] - center[1]

    def on_touch_move(self, touch):
        if touch.grab_current is not self:
            return super().on_touch_move(touch)
        start = touch.ud.get("chess_start_pos", (touch.x, touch.y))
        dx, dy = touch.x - start[0], touch.y - start[1]
        if self._drag_piece is None:
            if self._press_piece is None or dx * dx + dy * dy < dp(7) ** 2:
                return True
            # A short movement threshold cleanly separates a tap from a drag.
            # Keep the original touch-to-piece offset, then lift at the finger.
            self._drag_square = self._press_square
            self._drag_piece = self._press_piece
            self._drag_touch_offset = self._touch_offset(self._drag_square, start)
            self._drag_moved = True
            self._drag_last_pos = (touch.x, touch.y)
            self.screen.choose_square(self._drag_square)
        # Follow raw input; easing each pointer event creates visible lag.
        self._drag_last_pos = (touch.x, touch.y)
        self._render_drag_piece()
        return True

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            end_square = self.square_at(touch.pos)
            start_square = touch.ud.get("chess_start_square")
            dragged = self._drag_piece is not None and self._drag_moved
            if dragged and end_square is not None and start_square is not None and end_square != start_square:
                # Preserve the floating sprite's actual centre as the start of
                # the landing animation. It must never jump back to its origin.
                cell = min(self.width, self.height) / 8
                if self._press_piece and self._press_piece.piece_type == chess.PAWN:
                    offset_x, offset_y = self._drag_touch_offset
                else:
                    offset_x = offset_y = 0
                self._drop_start_pos = (
                    touch.x - offset_x - cell / 2,
                    touch.y - offset_y - cell / 2,
                )
            self._drag_piece = None
            self._drag_square = None
            self._drag_last_pos = None
            self._press_square = None
            self._press_piece = None
            self._drag_moved = False
            self._moving_group.clear()
            self._drag_translate = None
            if dragged and end_square is not None and start_square is not None and end_square != start_square:
                if self.screen.selection == start_square:
                    self.screen.choose_square(end_square)
                # A rejected drop must not seed the next move's animation.
                self._drop_start_pos = None
            elif not dragged:
                # A quick press/release is a tap: select a piece or choose its
                # destination without ever lifting or hiding it mid-gesture.
                if start_square is not None:
                    self.screen.choose_square(start_square)
            self.redraw()
            return True
        return super().on_touch_up(touch)

    def redraw(self, *_):
        self._redraw_trigger()

    def _redraw_now(self, *_):
        from kivy.graphics import Color, Rectangle, Ellipse
        from kivy.utils import get_color_from_hex

        self._static_group.clear()
        self._moving_group.clear()
        self._drag_translate = None
        size = min(self.width, self.height) / 8
        ox = self.x + (self.width - size * 8) / 2
        oy = self.y + (self.height - size * 8) / 2
        board = self.screen.engine.board
        selected = set(self.selected)
        targets = set(self.targets)
        last = set(self.last_move)
        king = board.king(board.turn) if board.is_check() else None
        palette = ({"light": "#D7D4CD", "dark": "#777670", "select": "#A98A7B", "check": "#A77965"}
                   if self.screen.dark_mode else
                   {"light": "#F1EEE8", "dark": "#AAA9A3", "select": "#D9B7A8", "check": "#C58E78"})
        if self._board_dirty:
            self._draw_board_background(size, ox, oy, palette)
            self._board_dirty = False
        with self._static_group:
            # Only repaint changed-square overlays, legal targets, and live pieces.
            for square in last:
                self._draw_square_overlay(square, ox, oy, size,
                                          "#D9B7A8" if not self.screen.dark_mode else "#A98A7B")
            for square in selected:
                self._draw_square_overlay(square, ox, oy, size, palette["select"])
            if king is not None:
                self._draw_square_overlay(king, ox, oy, size, palette["check"])
            for square in targets:
                x, y = self._piece_position(square, ox, oy, size)
                Color(0.12, 0.12, 0.12, 0.40)
                Ellipse(pos=(x + size * .39, y + size * .39),
                        size=(size * .22, size * .22))
            for square, piece in board.piece_map().items():
                if square in self.previous_move or square == self._drag_square:
                    continue
                x, y = self._piece_position(square, ox, oy, size)
                self._draw_piece(piece.piece_type, piece.color, x, y, size)
        if self._drag_piece is not None:
            self._render_drag_piece()
        else:
            self._draw_animated_piece()

    def _draw_square_overlay(self, square, ox, oy, size, color):
        from kivy.graphics import Color, Rectangle
        from kivy.utils import get_color_from_hex

        x, y = self._piece_position(square, ox, oy, size)
        with self._static_group:
            Color(*get_color_from_hex(color))
            Rectangle(pos=(x, y), size=(size, size))

    def _draw_board_background(self, size, ox, oy, palette):
        from kivy.graphics import Color, Rectangle, Line
        from kivy.core.text import Label as CoreLabel
        from kivy.graphics import Rectangle as TextureRectangle
        from kivy.utils import get_color_from_hex

        self._board_group.clear()
        with self._board_group:
            for rank in range(8):
                for file in range(8):
                    x, y = ox + file * size, oy + rank * size
                    color = palette["light"] if (file + rank) % 2 == 0 else palette["dark"]
                    Color(*get_color_from_hex(color))
                    Rectangle(pos=(x, y), size=(size, size))
            rail_color = (.28, .28, .27, .72) if self.screen.dark_mode else (.36, .35, .33, .72)
            Color(*rail_color)
            Line(rectangle=(ox, oy, size * 8, size * 8), width=1.15)
            text_color = (.91, .90, .87, .88) if self.screen.dark_mode else (.20, .20, .19, .78)
            for index in range(8):
                file_char = chr(ord('a') + (7-index if self.flipped else index))
                rank_char = str(8-index if not self.flipped else index+1)
                for text, center in ((file_char, (ox+(index+.5)*size, oy-dp(7))),
                                     (rank_char, (ox-dp(7), oy+(7.5-index)*size))):
                    key = (text, round(max(dp(8), size*.105), 2), text_color)
                    texture = _COORD_TEXTURES.get(key)
                    if texture is None:
                        label = CoreLabel(text=text, font_size=key[1], color=text_color)
                        label.refresh()
                        texture = label.texture
                        _COORD_TEXTURES[key] = texture
                    Color(*text_color)
                    TextureRectangle(texture=texture,
                                     pos=(center[0]-texture.width/2, center[1]-texture.height/2),
                                     size=texture.size)

    def _piece_position(self, square, ox, oy, size):
        file, rank = chess.square_file(square), chess.square_rank(square)
        if self.flipped:
            file, rank = 7-file, 7-rank
        return ox + file * size, oy + rank * size

    def _draw_animated_piece(self):
        self._moving_group.clear()
        if len(self.previous_move) == 2 and self.animating:
            self._prepare_animated_piece()

    def _prepare_animated_piece(self):
        size = min(self.width, self.height) / 8
        ox = self.x + (self.width - size * 8) / 2
        oy = self.y + (self.height - size * 8) / 2
        source, destination = self.previous_move
        piece = self.screen.engine.board.piece_at(destination)
        if not piece:
            return
        self._move_start = self._animation_start_pos or self._piece_position(source, ox, oy, size)
        end = self._piece_position(destination, ox, oy, size)
        self._move_delta = (end[0]-self._move_start[0], end[1]-self._move_start[1])
        self._moving_group.add(PushMatrix())
        self._move_translation = Translate(x=self._move_start[0], y=self._move_start[1])
        self._moving_group.add(self._move_translation)
        self._draw_piece(piece.piece_type, piece.color, 0, 0, size, group=self._moving_group)
        self._moving_group.add(PopMatrix())

    def _update_animated_piece(self, *_):
        if len(self.previous_move) != 2 or not self.animating:
            return
        if self._move_translation is None:
            return
        p = self.anim_progress
        self._move_translation.x = self._move_start[0] + self._move_delta[0] * p
        self._move_translation.y = self._move_start[1] + self._move_delta[1] * p

    def _render_drag_piece(self, *_):
        if self._drag_piece is None:
            return
        if self._drag_last_pos is None:
            return
        size = min(self.width, self.height) / 8
        # The tall back-rank silhouettes have an uneven visual mass. Keep
        # their centre directly under the finger; pawns retain the precise
        # grab point, which already feels natural for their compact shape.
        if self._drag_piece.piece_type == chess.PAWN:
            offset_x, offset_y = self._drag_touch_offset
        else:
            offset_x = offset_y = 0
        x = self._drag_last_pos[0] - offset_x - size / 2
        y = self._drag_last_pos[1] - offset_y - size / 2
        # Use absolute board coordinates while dragging. This avoids the
        # canvas matrix offset that can misplace the taller back-rank pieces.
        self._moving_group.clear()
        self._drag_translate = None
        self._draw_piece(self._drag_piece.piece_type, self._drag_piece.color,
                         x, y, size, group=self._moving_group)
    anim_progress = NumericProperty(1)

    def _draw_piece(self, piece_type, white, x, y, size, group=None, pivot=None):
        from kivy.core.image import Image as CoreImage
        from kivy.graphics import Color, Rectangle

        names = {
            chess.PAWN: "pawn",
            chess.KNIGHT: "knight",
            chess.BISHOP: "bishop",
            chess.ROOK: "rook",
            chess.QUEEN: "queen",
            chess.KING: "king",
        }
        key = ("white" if white else "black", names[piece_type])
        texture = _PIECE_TEXTURES.get(key)
        if texture is None:
            project_root = Path(__file__).resolve().parents[2]
            image_path = project_root / "assets" / "pieces" / f"{key[0]}-{key[1]}.png"
            texture = CoreImage(str(image_path), keep_data=False).texture
            _PIECE_TEXTURES[key] = texture
        target = group or self._static_group
        with target:
            Color(1, 1, 1, 1)
            Rectangle(texture=texture, pos=(x, y), size=(size, size))

    def animate_move(self, move, done=None, start_pos=None):
        self.previous_move = [move.from_square, move.to_square]
        self._animation_start_pos = start_pos
        self.anim_progress = 0
        self.animating = True
        Animation.cancel_all(self, "anim_progress")
        self._move_translation = None
        self._prepare_animated_piece()
        animation = Animation(anim_progress=1, duration=.14 if start_pos else .22, t="out_cubic")
        def finish(*_):
            self.animating = False
            self.previous_move = []
            self._animation_start_pos = None
            self.redraw()
            if done:
                done()
        animation.bind(on_complete=finish)
        animation.start(self)


class GameScreen(FloatLayout):
    menu_open = BooleanProperty(False)
    popup_position = ListProperty([0, 0])
    status_text = StringProperty("YOUR TURN")
    result_visible = BooleanProperty(False)
    result_title = StringProperty("")
    result_detail = StringProperty("")
    dark_mode = BooleanProperty(False)
    bg_color = ColorProperty((.94, .93, .90, 1))
    surface_color = ColorProperty((.88, .87, .83, 1))
    text_color = ColorProperty((.12, .12, .12, 1))
    muted_color = ColorProperty((.37, .37, .35, 1))
    accent_color = ColorProperty((.65, .40, .31, 1))
    player_color = BooleanProperty(chess.WHITE)
    master_volume = NumericProperty(.60)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.engine = ChessEngine()
        self.selection = None
        self.started_at = time.monotonic()
        self.result_overlay = None
        self.menu_popup = None
        self._menu_animation = None
        self.dark_mode = is_dark_mode()
        self._apply_theme(self.dark_mode, animate=False)
        self._theme_poll = Clock.schedule_interval(self._poll_theme, 4)
        self._background_music = None
        self._move_sound = None
        self._game_started = False
        self._side_picker = None
        app = App.get_running_app()
        if app is not None:
            self.master_volume = app.config.getfloat("audio", "master_volume")
        self._volume_save_trigger = Clock.create_trigger(self._save_volume_setting, .5)
        Clock.schedule_once(self._start_audio, 0)
        self.menu_button = self.ids.menu_button
        self.menu_button.bind(on_release=self._open_about_menu)
        self.board_widget = ChessBoard(self, size_hint=(None, None))
        self.ids.board_container.add_widget(self.board_widget)
        self.bind(size=self._fit_board)
        Clock.schedule_once(self._fit_board, 0)
        Clock.schedule_once(self._show_side_picker, .1)
        self.refresh()

    def _poll_theme(self, *_):
        dark = is_dark_mode()
        if dark != self.dark_mode:
            self._apply_theme(dark)

    def _start_audio(self, *_):
        # Force SDL2 before Kivy starts so WAV playback does not depend on
        # optional GStreamer decoder plugins installed by the operating system.
        try:
            from kivy.core.audio import SoundLoader
            from kivy.logger import Logger
            from kivy.resources import resource_find

            assets_dir = Path(__file__).resolve().parents[2] / "assets"
            for filename, target in (("ambient.wav", "music"), ("move.wav", "move")):
                bundled_source = assets_dir / filename
                source = str(bundled_source) if bundled_source.is_file() else resource_find(
                    f"assets/{filename}")
                if source is None:
                    Logger.warning(f"PixelChess: assets/{filename} was not found")
                    continue
                sound = SoundLoader.load(source)
                if sound is None:
                    Logger.warning(f"PixelChess: no audio provider could load assets/{filename}")
                    continue
                if target == "music":
                    self._background_music = sound
                    sound.loop = True
                    sound.volume = self.master_volume * .65
                    sound.play()
                else:
                    self._move_sound = sound
                    sound.volume = self.master_volume * .85
        except Exception as error:
            from kivy.logger import Logger
            Logger.warning(f"PixelChess: background music could not start: {error}")
            self._background_music = None

    def _set_master_volume(self, value):
        self.master_volume = max(0.0, min(1.0, value))
        if self._background_music is not None:
            self._background_music.volume = self.master_volume * .65
        if self._move_sound is not None:
            self._move_sound.volume = self.master_volume * .85
        self._volume_save_trigger()

    def _save_volume_setting(self, *_):
        app = App.get_running_app()
        if app is not None:
            app.config.set("audio", "master_volume", f"{self.master_volume:.3f}")
            app.config.write()

    def _play_move_sound(self):
        if self._move_sound is not None and self.master_volume > 0:
            self._move_sound.stop()
            self._move_sound.play()

    def _apply_theme(self, dark, animate=True):
        from kivy.core.window import Window

        self.dark_mode = dark
        colors = ({"bg_color": (.10, .10, .10, 1), "surface_color": (.18, .18, .17, 1),
                   "text_color": (.94, .93, .90, 1), "muted_color": (.68, .67, .64, 1),
                   "accent_color": (.83, .65, .55, 1)} if dark else
                  {"bg_color": (.94, .93, .90, 1), "surface_color": (.88, .87, .83, 1),
                   "text_color": (.12, .12, .12, 1), "muted_color": (.37, .37, .35, 1),
                   "accent_color": (.65, .40, .31, 1)})
        if animate:
            Animation(**colors, duration=.28, t="out_quad").start(self)
        else:
            for name, value in colors.items():
                setattr(self, name, value)
        Window.clearcolor = colors["bg_color"]
        for widget in self.walk():
            if isinstance(widget, PixelButton):
                widget.fill_color = (.31, .31, .30, 1) if dark else (.85, .83, .79, 1)
                widget.text_color = colors["text_color"]
                widget.ripple_color = ((.90, .89, .86, .42) if dark else (.25, .25, .23, .30))
                if hasattr(widget, "_github_icon"):
                    widget._github_icon.source = (
                        "assets/github-mark-light.png" if dark else "assets/github-mark.png")
                    widget._github_label.color = colors["text_color"]
        side_picker = getattr(self, "_side_picker", None)
        if side_picker is not None and side_picker._is_open:
            for button, label in side_picker._role_choices:
                button.fill_color = (.31, .31, .30, 1) if dark else (.85, .83, .79, 1)
                button.text_color = colors["text_color"]
                label.color = colors["text_color"]
        if hasattr(self, "board_widget"):
            self.board_widget.invalidate_board()
        if self.result_overlay is not None:
            self.result_overlay._title_label.color = colors["text_color"]
            self.result_overlay._detail_label.color = colors["muted_color"]
            self.result_overlay._result_card.fill_color = (
                (.15, .15, .14, 1) if dark else (.96, .95, .92, 1))
            for widget in self.result_overlay.walk():
                if isinstance(widget, PixelButton):
                    widget.fill_color = (.31, .31, .30, 1) if dark else (.85, .83, .79, 1)
                    widget.text_color = colors["text_color"]
                    widget.ripple_color = ((.90, .89, .86, .42) if dark else (.25, .25, .23, .30))
        if self.menu_popup is not None and hasattr(self.menu_popup, "_surface_color"):
            self.menu_popup._surface_color.rgba = ((.17, .17, .16, 1) if dark else (.98, .97, .94, 1))
            for item in getattr(self.menu_popup, "_items", []):
                item.text_color = colors["text_color"]

    def _open_about_menu(self, *_):
        if self.menu_open:
            self._close_about_menu()
            return
        from kivy.graphics import Color, RoundedRectangle
        self.menu_open = True
        self.menu_popup = self.ids.popup_layer
        self.menu_popup.size = (dp(190), dp(112))
        self.menu_popup.padding = dp(5)
        self.menu_popup.spacing = dp(3)
        self.menu_popup.clear_widgets()
        self.menu_popup.canvas.before.clear()
        with self.menu_popup.canvas.before:
            self.menu_popup._surface_color = Color(*((.17, .17, .16, 1) if self.dark_mode else (.98, .97, .94, 1)))
            self.menu_popup._surface = RoundedRectangle(pos=self.menu_popup.pos, size=(dp(190), dp(112)),
                                                        radius=[dp(6)])
        self.menu_popup.bind(pos=lambda w, p: setattr(w._surface, 'pos', p),
                             size=lambda w, s: setattr(w._surface, 'size', s))
        self.menu_popup._items = []
        for text, callback in (("Settings", self._select_settings),
                               ("About", self._select_about)):
            item = PixelButton(text=text, font_size='15sp', size_hint=(1, 1),
                               fill_color=(.23, .23, .22, 1) if self.dark_mode else (.91, .90, .87, 1),
                               text_color=self.text_color,
                               ripple_color=(.88, .87, .84, .38) if self.dark_mode else (.24, .23, .21, .24),
                               halign='center', valign='middle', padding=(0, 0))
            item.bind(size=lambda w, s: setattr(w, 'text_size', s),
                      on_release=lambda *_args, action=callback: Clock.schedule_once(
                          lambda _dt: action(), .12))
            self.menu_popup._items.append(item)
            self.menu_popup.add_widget(item)
        Clock.schedule_once(self._position_about_menu, 0)

    def _position_about_menu(self, *_):
        if not self.menu_open or not self.menu_popup:
            return
        button = self.menu_button
        menu = self.menu_popup
        # Both controls are direct children of the screen's FloatLayout.
        x = max(dp(8), button.right - menu.width)
        y = button.y - menu.height - dp(6)
        if y < dp(8):
            y = button.top + dp(6)
        self.popup_position = [x, y]
        menu._surface.pos = (x, y)
        menu._surface.size = (dp(190), dp(112))

    def _close_about_menu(self):
        if self.menu_popup is not None:
            self.menu_popup.clear_widgets()
            self.menu_popup.canvas.before.clear()
        self.menu_popup = None
        self.menu_open = False
        self.ids.popup_layer.size = (0, 0)

    def _select_about(self):
        self._close_about_menu()
        self._show_about()

    def _select_settings(self):
        self._close_about_menu()
        self._show_settings()

    def _show_settings(self):
        from kivy.uix.slider import Slider

        view = ModalView(size_hint=(.90, None), height=dp(250), auto_dismiss=True,
                         background='', background_color=(0, 0, 0, 0),
                         overlay_color=(0, 0, 0, .38))
        card = RoundCard(orientation='vertical', padding=dp(22), spacing=dp(14),
                         fill_color=(.16, .16, .15, 1) if self.dark_mode else (.99, .98, .95, 1),
                         corner_radius=dp(30))
        heading = Label(text='Settings', size_hint_y=None, height=dp(40), bold=True,
                        font_size='22sp', color=self.text_color, halign='left')
        heading.bind(size=lambda widget, size: setattr(widget, 'text_size', size))
        volume_label = Label(text=f'Master volume  {round(self.master_volume * 100)}%',
                             size_hint_y=None, height=dp(28), color=self.text_color,
                             font_size='15sp', halign='left')
        volume_label.bind(size=lambda widget, size: setattr(widget, 'text_size', size))
        slider = Slider(min=0, max=1, value=self.master_volume, size_hint_y=None,
                        height=dp(34), cursor_size=(dp(24), dp(24)))
        slider.bind(value=lambda _slider, value: self._update_volume_controls(
            value, volume_label))
        close = PixelButton(text='Done', size_hint_y=None, height=dp(46))
        close.fill_color = (.31, .31, .30, 1) if self.dark_mode else (.85, .83, .79, 1)
        close.text_color = self.text_color
        close.ripple_color = (*self.accent_color[:3], .34)
        close.bind(on_release=view.dismiss)
        card.add_widget(heading)
        card.add_widget(volume_label)
        card.add_widget(slider)
        card.add_widget(close)
        view.add_widget(card)
        view.open()

    def _update_volume_controls(self, value, label):
        label.text = f'Master volume  {round(value * 100)}%'
        self._set_master_volume(value)

    def on_touch_down(self, touch):
        if self.menu_open and self.menu_popup and not self.menu_popup.collide_point(*touch.pos):
            self._close_about_menu()
        return super().on_touch_down(touch)

    def _show_about(self):
        self.show_info('About Pixel Chess',
                       'A minimalist chess game for focused play. Choose either side to play against the local opponent.\n\n'
                       'HOW TO PLAY\nTap a piece, then tap one of its highlighted legal moves.\n\n'
                       'MUSIC\nFriday Morning — Kevin MacLeod (CC BY 4.0).\n\n'
                       'LICENSE\nGNU General Public License v3 (GPL-3.0).')

    def show_info(self, title, message):
        view = ModalView(size_hint=(.90, None), height=dp(390), auto_dismiss=True,
                         background='', background_color=(0, 0, 0, 0),
                         overlay_color=(0, 0, 0, .38))
        card = RoundCard(orientation='vertical', padding=dp(22), spacing=dp(12),
                         fill_color=(.16, .16, .15, 1) if self.dark_mode else (.99, .98, .95, 1),
                         corner_radius=dp(30))
        heading = Label(text=title, size_hint_y=None, height=dp(42), bold=True,
                        font_size='22sp', color=self.text_color, halign='left')
        heading.bind(size=lambda widget, size: setattr(widget, 'text_size', size))
        body = Label(text=message, color=self.text_color, font_size='14sp',
                     halign='left', valign='top')
        body.bind(size=lambda widget, size: setattr(widget, 'text_size', size))
        github = PixelButton(text='', size_hint_y=None, height=dp(48))
        github_row = BoxLayout(size_hint=(None, None), size=(dp(108), dp(28)),
                               spacing=dp(9), pos_hint={'center_x': .5, 'center_y': .5})
        github_icon = Image(source=("assets/github-mark-light.png" if self.dark_mode
                                    else "assets/github-mark.png"),
                            size_hint=(None, 1), width=dp(26), fit_mode='contain')
        github_label = Label(text='GitHub', color=self.text_color, bold=True,
                             font_size='15sp')
        github_row.add_widget(github_icon)
        github_row.add_widget(github_label)
        github.add_widget(github_row)
        github._github_icon = github_icon
        github._github_label = github_label
        def position_github_contents(_widget, *_args):
            github_row.size = (dp(108), dp(28))
            github_row.pos = (github.x + (github.width - github_row.width) / 2,
                              github.y + (github.height - github_row.height) / 2)
        github.bind(pos=position_github_contents, size=position_github_contents)
        position_github_contents(github)
        github.fill_color = (.31, .31, .30, 1) if self.dark_mode else (.85, .83, .79, 1)
        github.text_color = self.text_color
        github.ripple_color = (*self.accent_color[:3], .34)
        github.bind(on_release=lambda *_: self._open_repository(view))
        close = PixelButton(text='Close', size_hint_y=None, height=dp(48))
        close.fill_color = (.31, .31, .30, 1) if self.dark_mode else (.85, .83, .79, 1)
        close.text_color = self.text_color
        close.ripple_color = (.90, .89, .86, .42) if self.dark_mode else (.25, .25, .23, .30)
        close.bind(on_release=view.dismiss)
        card.add_widget(heading)
        card.add_widget(body)
        card.add_widget(github)
        card.add_widget(close)
        view.add_widget(card)
        view.open()

    @staticmethod
    def _open_repository(view):
        webbrowser.open("https://github.com/mardner4ik/Pixel-Chess")
        view.dismiss()

    def _fit_board(self, *_):
        if not hasattr(self, "board_widget") or "board_container" not in self.ids:
            return
        box = self.ids.board_container
        side = min(box.width, box.height)
        self.board_widget.size = (side, side)
        self.board_widget.pos = (box.center_x - side / 2, box.center_y - side / 2)

    def choose_square(self, square):
        if not self._game_started:
            return
        board = self.engine.board
        if board.turn != self.player_color:
            return
        if self.selection is not None:
            candidates = [m for m in self.engine.legal_moves_from(self.selection) if m.to_square == square]
            if candidates:
                move = next((m for m in candidates if m.promotion == chess.QUEEN), candidates[0])
                self.engine.play(move)
                self._play_move_sound()
                self.selection = None
                self.board_widget.selected = []
                self.board_widget.targets = []
                drop_start = self.board_widget._drop_start_pos
                self.board_widget._drop_start_pos = None
                self.board_widget.animate_move(move, start_pos=drop_start)
                self.refresh()
                if self.engine.board.turn != self.player_color and not self.engine.status()[1]:
                    Clock.schedule_once(self._start_bot, .30)
                else:
                    self._finish_round()
                return
        piece = board.piece_at(square)
        if piece and piece.color == self.player_color and board.turn == self.player_color:
            self.selection = square
            self.board_widget.selected = [square]
            self.board_widget.targets = [move.to_square for move in self.engine.legal_moves_from(square)]
        else:
            self.selection = None
            self.board_widget.selected = []
            self.board_widget.targets = []
        self.board_widget.redraw()

    def _start_bot(self, *_):
        if self._game_started and self.engine.board.turn != self.player_color and not self.engine.status()[1]:
            snapshot = self.engine.board.copy(stack=True)
            future = BOT_POOL.submit(self._calculate_bot_move, snapshot)
            future.add_done_callback(lambda result: Clock.schedule_once(lambda _dt: self._apply_bot_result(result), 0))

    @staticmethod
    def _calculate_bot_move(board):
        engine = ChessEngine()
        engine.board = board
        return engine.bot_move()

    def _apply_bot_result(self, future):
        if not self._game_started or self.engine.board.turn == self.player_color or self.engine.status()[1]:
            return
        try:
            move = future.result()
        except Exception:
            self.status_text = "COULD NOT FIND A MOVE"
            return
        if move is not None:
            self.engine.play(move)
            self._play_move_sound()
            self.board_widget.selected = []
            self.board_widget.targets = []
            self.selection = None
            self.board_widget.animate_move(move)
            self.refresh()
            if self.engine.status()[1]:
                self._finish_round()

    def refresh(self):
        status, finished = self.engine.status()
        if not finished and status != "CHECK":
            status = "YOUR TURN" if self.engine.board.turn == self.player_color else "OPPONENT THINKING"
        self.status_text = status
        if hasattr(self, "board_widget"):
            last = self.engine.board.peek() if self.engine.board.move_stack else None
            self.board_widget.last_move = [last.from_square, last.to_square] if last else []
            self.board_widget.check_square = chess.square_name(self.engine.board.king(self.engine.board.turn)) if self.engine.board.is_check() else ""
            self.board_widget.redraw()
        self.result_visible = self.engine.status()[1]
        if self.result_visible:
            self._finish_round()

    def _finish_round(self):
        status, _ = self.engine.status()
        self.result_title = "Game over"
        self.result_detail = f"{status}   ·   {len(self.engine.board.move_stack)} plies   ·   {self._elapsed_text()}"
        self.result_visible = True

    def on_result_visible(self, _instance, visible):
        if not visible:
            if self.result_overlay is not None:
                self.result_overlay.dismiss()
            return
        Clock.schedule_once(self._show_result, 0)

    def _show_result(self, *_):
        if not self.result_visible:
            return
        if self.result_overlay is None:
            from kivy.uix.modalview import ModalView

            overlay = ModalView(size_hint=(.88, None), height=dp(260), auto_dismiss=False,
                                background='', background_color=(0, 0, 0, 0),
                                overlay_color=(.06, .06, .06, .48))
            content = RoundCard(orientation='vertical', padding=dp(22), spacing=dp(12),
                                fill_color=(.15, .15, .14, 1) if self.dark_mode else (.96, .95, .92, 1),
                                corner_radius=dp(28))
            title = Label(color=(.12, .12, .12, 1), bold=True, font_size='23sp', size_hint_y=None, height=dp(44))
            detail = Label(color=(.34, .34, .32, 1), font_size='14sp', halign='center')
            detail.bind(size=lambda widget, size: setattr(widget, 'text_size', size))
            restart = PixelButton(text='Restart', size_hint_y=None, height=dp(54))
            restart.fill_color = (.31, .31, .30, 1) if self.dark_mode else (.85, .83, .79, 1)
            restart.text_color = self.text_color
            restart.ripple_color = (*self.accent_color[:3], .34)
            restart.bind(on_release=lambda *_: self.new_game())
            content.add_widget(title)
            content.add_widget(detail)
            content.add_widget(restart)
            overlay._result_card = content
            overlay.add_widget(content)
            overlay._title_label = title
            overlay._detail_label = detail
            self.result_overlay = overlay

        self.result_overlay._title_label.text = self.result_title
        self.result_overlay._detail_label.text = self.result_detail
        if not self.result_overlay._is_open:
            self.result_overlay.open()

    def _elapsed_text(self):
        seconds = int(time.monotonic() - self.started_at)
        return f"{seconds // 60:02}:{seconds % 60:02}"

    def new_game(self):
        self._game_started = False
        if self.result_overlay is not None:
            self.result_overlay.dismiss()
        self.result_visible = False
        Clock.schedule_once(self._show_side_picker, .12)

    def _show_side_picker(self, *_):
        if self._side_picker is not None and self._side_picker._is_open:
            return
        view = ModalView(size_hint=(.82, None), height=dp(218), auto_dismiss=False,
                         background='', background_color=(0, 0, 0, 0),
                         overlay_color=(0, 0, 0, .42))
        card = RoundCard(orientation='vertical', padding=dp(14), spacing=dp(10),
                         fill_color=(.16, .16, .15, 1) if self.dark_mode else (.99, .98, .95, 1),
                         corner_radius=dp(26))
        heading = Label(text='Select Role', size_hint_y=None, height=dp(34),
                        bold=True, font_size='19sp', color=self.text_color,
                        halign='center')
        heading.bind(size=lambda widget, size: setattr(widget, 'text_size', size))
        buttons = BoxLayout(size_hint=(None, None), height=dp(124), spacing=dp(12),
                            pos_hint={"center_x": .5})
        choices = []
        for color, title, icon_name in (
                (chess.WHITE, "White", "white-king.png"),
                (chess.BLACK, "Black", "black-king.png")):
            button = PixelButton(text='', size_hint=(None, None))
            button.fill_color = (.31, .31, .30, 1) if self.dark_mode else (.85, .83, .79, 1)
            button.text_color = self.text_color
            button.ripple_color = (*self.accent_color[:3], .34)
            icon = Image(source=f"assets/pieces/{icon_name}", fit_mode='contain')
            label = Label(text=title, color=self.text_color, bold=True, font_size='15sp')
            button.add_widget(icon)
            button.add_widget(label)
            def layout_choice(widget, *_args, piece_icon=icon, piece_label=label):
                icon_size = min(dp(72), widget.width * .62, widget.height * .56)
                piece_icon.size = (icon_size, icon_size)
                piece_icon.pos = (widget.x + (widget.width - icon_size) / 2,
                                  widget.y + widget.height - icon_size - dp(8))
                piece_label.size = (widget.width - dp(12), dp(24))
                piece_label.pos = (widget.x + dp(6), widget.y + dp(6))
            button.bind(pos=layout_choice, size=layout_choice)
            layout_choice(button)
            button.bind(on_release=lambda *_args, side=color: self._begin_game(side, view))
            buttons.add_widget(button)
            choices.append((button, label))
        card.add_widget(heading)
        card.add_widget(buttons)
        view.add_widget(card)
        view._role_choices = choices
        self._side_picker = view
        def fit_role_cards(*_args):
            available = card.width - dp(36)
            side = max(dp(104), min(dp(124), (available - dp(12)) / 2))
            buttons.size = (side * 2 + dp(12), side)
            for button, _label in choices:
                button.size = (side, side)
        card.bind(size=fit_role_cards)
        view.open()
        Clock.schedule_once(fit_role_cards, 0)

    def _begin_game(self, player_color, view):
        view.dismiss()
        self._side_picker = None
        Animation.cancel_all(self.board_widget)
        self.board_widget.animating = False
        self.board_widget.previous_move = []
        self.board_widget.anim_progress = 1
        self.engine = ChessEngine()
        self.player_color = bool(player_color)
        self.board_widget.flipped = not self.player_color
        self.started_at = time.monotonic()
        self.result_visible = False
        self._game_started = True
        self.selection = None
        self.board_widget.selected = []
        self.board_widget.targets = []
        self.refresh()
        if self.engine.board.turn != self.player_color:
            Clock.schedule_once(self._start_bot, .25)

