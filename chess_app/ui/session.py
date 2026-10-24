"""Game persistence, clocks, and session actions."""

import json
import time

import chess
from kivy.app import App
from kivy.clock import Clock

from chess_app.core.engine import ChessEngine
from chess_app.ui.board import BOARD_PALETTES
from chess_app.ui.soundtracks import SOUNDTRACKS_BY_ID


class GameSessionMixin:
    def _save_game(self):
        if self._session_path is None or not self._game_started:
            return False
        payload = {"fen": self.engine.board.fen(), "moves": [move.uci() for move in self.engine.board.move_stack],
                   "player_color": bool(self.player_color), "difficulty": self.difficulty,
                   "time_control": self.time_control, "board_palette": self.board_palette,
                   "bot_thinking_delay": self.bot_thinking_delay,
                   "piece_style": self.piece_style, "soundtrack_id": self.soundtrack_id,
                   "remaining": {str(k): v for k, v in self.remaining_time.items()},
                   "saved_at": time.time()}
        try:
            self._session_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = self._session_path.with_suffix(".tmp")
            temporary_path.write_text(json.dumps(payload), encoding="utf-8")
            temporary_path.replace(self._session_path)
            return True
        except OSError:
            return False

    def save_game(self):
        if self._save_game():
            self._show_toast("Game saved")
        else:
            self._show_toast("Could not save game")

    def _clear_saved_game(self):
        if self._session_path is not None:
            try:
                self._session_path.unlink(missing_ok=True)
            except OSError:
                pass

    def _has_saved_game(self):
        return bool(self._session_path and self._session_path.is_file())

    def _restore_saved_game(self):
        if not self._has_saved_game():
            return
        try:
            data = json.loads(self._session_path.read_text(encoding="utf-8"))
            board = chess.Board()
            for uci in data.get("moves", []):
                move = chess.Move.from_uci(uci)
                if move not in board.legal_moves:
                    raise ValueError("Invalid saved move")
                board.push(move)
            if board.fen() != data.get("fen"):
                raise ValueError("Saved position mismatch")
            self._saved_session = data
        except (OSError, ValueError, TypeError, AttributeError, json.JSONDecodeError):
            self._clear_saved_game()
            self._saved_session = None

    def _continue_saved_game(self):
        data = getattr(self, "_saved_session", None)
        if not data:
            return
        self.engine = ChessEngine()
        for uci in data["moves"]:
            self.engine.play(chess.Move.from_uci(uci))
        self.player_color = bool(data.get("player_color", chess.WHITE))
        self.difficulty = data.get("difficulty", "normal")
        self.time_control = int(data.get("time_control", 0))
        self.bot_thinking_delay = bool(data.get("bot_thinking_delay", True))
        self.board_palette = data.get("board_palette", "sage")
        self.piece_style = data.get("piece_style", "pixel")
        track_id = data.get("soundtrack_id", "friday_morning")
        self.soundtrack_id = track_id if track_id in SOUNDTRACKS_BY_ID else "friday_morning"
        self.remaining_time = {chess.WHITE: float(data.get("remaining", {}).get("True", 0)),
                               chess.BLACK: float(data.get("remaining", {}).get("False", 0))}
        self.started_at = time.monotonic()
        self.board_widget.flipped = not self.player_color
        self.board_widget.invalidate_board()
        self._game_started = True
        self._in_main_menu = False
        self.main_menu.opacity = 0
        self.main_menu.disabled = True
        self.ids.board_container.opacity = 1
        self.ids.board_container.disabled = False
        self.ids.menu_button.opacity = 1
        self.ids.menu_button.disabled = False
        self.ids.status_label.opacity = 1
        if self.time_control:
            self._last_clock_tick = time.monotonic()
            self._last_clock_save = self._last_clock_tick
            self._clock_event = Clock.schedule_interval(self._tick_clock, .25)
        self.refresh()
        if self.engine.board.turn != self.player_color:
            Clock.schedule_once(self._start_bot, .25)

    def _set_board_palette(self, name):
        if name not in BOARD_PALETTES:
            return
        self.board_palette = name
        self.board_widget.invalidate_board()
        app = App.get_running_app()
        if app is not None:
            app.config.set("game", "board_palette", self.board_palette)
            app.config.write()
        self._save_game()

    def _set_piece_style(self, style):
        if style not in {"pixel", "vector"}:
            return
        self.piece_style = style
        self.board_widget.redraw()
        app = App.get_running_app()
        if app is not None:
            app.config.set("game", "piece_style", self.piece_style)
            app.config.write()
        self._save_game()

    def _set_soundtrack(self, track_id):
        if track_id not in SOUNDTRACKS_BY_ID:
            return
        self.soundtrack_id = track_id
        app = App.get_running_app()
        if app is not None:
            app.config.set("game", "soundtrack", self.soundtrack_id)
            app.config.write()
        if self._background_music is not None:
            self._background_music.stop()
        self._start_audio()
        self._save_game()

    def _clock_text(self, color):
        seconds = max(0, int(self.remaining_time.get(color, 0)))
        return f"{seconds // 60:02}:{seconds % 60:02}"

    def _tick_clock(self, _dt):
        if not self._game_started or not self.time_control:
            return
        now = time.monotonic()
        side = self.engine.board.turn
        self.remaining_time[side] = max(0, self.remaining_time[side] - (now - self._last_clock_tick))
        self._last_clock_tick = now
        if self.remaining_time[side] <= 0:
            self._cancel_bot_thinking()
            self._game_started = False
            self.status_text = "TIME OUT"
            self.result_title = "Time out"
            self.result_detail = ("Opponent wins" if side == self.player_color else "You win")
            self.result_visible = True
            if self._clock_event is not None:
                self._clock_event.cancel()
                self._clock_event = None
            self._clear_saved_game()
            return
        if now - self._last_clock_save >= 5:
            self._save_game()
            self._last_clock_save = now
        self.refresh(redraw_board=False)

    def _consume_clock(self, color):
        if self.time_control:
            now = time.monotonic()
            self.remaining_time[color] = max(0, self.remaining_time[color] - (now - self._last_clock_tick))
            self._last_clock_tick = now

    def can_undo_move(self):
        if not self._game_started or not self.engine.board.move_stack:
            return False
        board = self.engine.board
        return board.turn != self.player_color or len(board.move_stack) >= 2

    def undo_move(self):
        if not self.can_undo_move():
            return
        self._cancel_bot_thinking()
        board = self.engine.board
        if board.turn != self.player_color:
            # The bot is to move, so the last move is the player's move.
            board.pop()
        else:
            # Only take back a bot reply together with the player's move that
            # preceded it. In particular, keep the bot's opening move intact
            # until the player has actually made a move.
            if len(board.move_stack) < 2:
                return
            board.pop()
            board.pop()
        self.remaining_time[self.player_color] = max(1, self.remaining_time.get(self.player_color, 0))
        self.selection = None
        self.board_widget.selected = []
        self.board_widget.targets = []
        self._last_clock_tick = time.monotonic()
        self._last_clock_save = self._last_clock_tick
        self.refresh()
        self._save_game()

    def _elapsed_text(self):
        seconds = int(time.monotonic() - self.started_at)
        return f"{seconds // 60:02}:{seconds % 60:02}"
