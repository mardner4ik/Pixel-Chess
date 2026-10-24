"""Background bot-search lifecycle and its player-facing timer."""

import random
import threading
import time

from kivy.clock import Clock

from chess_app.core.engine import ChessEngine
from chess_app.ui.board import BOT_POOL


class BotThinkingMixin:
    def _cancel_bot_thinking(self):
        self._game_generation += 1
        if self._bot_cancel_event is not None:
            self._bot_cancel_event.set()
            self._bot_cancel_event = None
        self._bot_think_started_at = None
        if self._bot_timer_event is not None:
            self._bot_timer_event.cancel()
            self._bot_timer_event = None

    def _start_bot(self, *_):
        if self._game_started and self.engine.board.turn != self.player_color and not self.engine.status()[1]:
            if self._bot_cancel_event is not None:
                return
            snapshot = self.engine.board.copy(stack=True)
            generation = self._game_generation
            cancel_event = threading.Event()
            self._bot_cancel_event = cancel_event
            thinking_time = random.uniform(4.0, 15.0) if self.bot_thinking_delay else 0.0
            self._bot_think_started_at = time.monotonic()
            self._bot_timer_event = Clock.schedule_interval(self._update_bot_timer, .25)
            self._update_bot_timer()
            future = BOT_POOL.submit(self._calculate_bot_move, snapshot, self.difficulty,
                                     thinking_time, cancel_event)
            future.add_done_callback(lambda result: Clock.schedule_once(
                lambda _dt: self._apply_bot_result(result, generation, cancel_event), 0))

    @staticmethod
    def _calculate_bot_move(board, difficulty="normal", thinking_time=None, cancel_event=None):
        engine = ChessEngine()
        engine.board = board
        return engine.bot_move(difficulty, thinking_time, cancel_event)

    def _update_bot_timer(self, *_):
        if self._bot_think_started_at is None or not self._game_started:
            return False
        elapsed = max(0, int(time.monotonic() - self._bot_think_started_at))
        status = f"OPPONENT THINKING · {elapsed // 60:02}:{elapsed % 60:02}"
        if self.time_control:
            status += f"  •  {self._clock_text(self.engine.board.turn)}"
        self.status_text = status

    def _apply_bot_result(self, future, generation=None, cancel_event=None):
        if (generation != self._game_generation or cancel_event is not self._bot_cancel_event
                or cancel_event is None or cancel_event.is_set() or not self._game_started
                or self.engine.board.turn == self.player_color or self.engine.status()[1]):
            return
        self._bot_cancel_event = None
        self._bot_think_started_at = None
        if self._bot_timer_event is not None:
            self._bot_timer_event.cancel()
            self._bot_timer_event = None
        try:
            move = future.result()
        except Exception:
            self.status_text = "COULD NOT FIND A MOVE"
            return
        if move is not None:
            self.engine.play(move)
            self._play_move_sound()
            self._consume_clock(not self.player_color)
            self._save_game()
            self.board_widget.selected = []
            self.board_widget.targets = []
            self.selection = None
            self.board_widget.animate_move(move)
            self.refresh()
            if self.engine.status()[1]:
                self._finish_round()

