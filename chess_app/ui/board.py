from __future__ import annotations

from pathlib import Path
import chess
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import ListProperty, NumericProperty, BooleanProperty, StringProperty
from kivy.uix.widget import Widget
from concurrent.futures import ThreadPoolExecutor

BOT_POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="chess-bot")
_COORD_TEXTURES = {}
_PIECE_TEXTURES = {}
ACCENT_PALETTES = {
    "blue": (.26, .43, .91, 1),
    "green": (.15, .53, .35, 1),
    "violet": (.52, .34, .78, 1),
    "amber": (.76, .43, .04, 1),
}
BOARD_PALETTES = {
    "sage": ("#F1EEE8", "#AAA9A3", "#D7D4CD", "#777670"),
    "green": ("#EEEED2", "#769656", "#C8CBAE", "#596B43"),
    "blue": ("#DEE3E6", "#6C8EBF", "#C3CED5", "#4D6786"),
    "wood": ("#F0D9B5", "#B58863", "#D6BE9E", "#795B42"),
}

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
        self._active_touch = None
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
            self._active_touch = touch
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
        if self._active_touch is not touch and touch.grab_current is not self:
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
        if self._active_touch is touch or touch.grab_current is self:
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
            self._active_touch = None
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
        colors = BOARD_PALETTES.get(self.screen.board_palette, BOARD_PALETTES["sage"])
        light_square, dark_square = colors[2:4] if self.screen.dark_mode else colors[:2]
        palette = {"light": light_square, "dark": dark_square,
                   "select": "#A98A7B" if self.screen.dark_mode else "#D9B7A8",
                   "check": "#A77965" if self.screen.dark_mode else "#C58E78"}
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
        key = (getattr(self.screen, "piece_style", "pixel"), "white" if white else "black", names[piece_type])
        texture = _PIECE_TEXTURES.get(key)
        if texture is None:
            project_root = Path(__file__).resolve().parents[2]
            style = getattr(self.screen, "piece_style", "pixel")
            folder = "vector" if style == "vector" else ""
            image_path = project_root / "assets" / "pieces" / folder / f"{key[1]}-{key[2]}.png"
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
