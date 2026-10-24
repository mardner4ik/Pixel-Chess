from __future__ import annotations

import time
from pathlib import Path

import chess
from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import ListProperty, StringProperty, NumericProperty, BooleanProperty, ColorProperty
from kivy.uix.floatlayout import FloatLayout

from chess_app.core.engine import ChessEngine
from chess_app.paths import asset_path
from chess_app.ui.system_theme import is_dark_mode
from chess_app.ui.board import ChessBoard
from chess_app.ui.appearance import AppearanceMixin
from chess_app.ui.game_flow import GameFlowMixin
from chess_app.ui.navigation import GameNavigationMixin
from chess_app.ui.bot_thinking import BotThinkingMixin
from chess_app.ui.dialogs import GameDialogsMixin
from chess_app.ui.session import GameSessionMixin
from chess_app.ui.soundtracks import SOUNDTRACKS_BY_ID

class GameScreen(BotThinkingMixin, AppearanceMixin, GameNavigationMixin, GameFlowMixin,
                  GameDialogsMixin, GameSessionMixin, FloatLayout):
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
        self._menu_button_home_y = None
        self._menu_button_home_window = None
        self._toast_message = None
        self._toast_event = None
        self._game_generation = 0
        self._bot_cancel_event = None
        self._bot_think_started_at = None
        self._bot_timer_event = None
        app = App.get_running_app()
        self.accent_mode = (app.config.get("appearance", "accent_mode")
                            if app is not None else "system")
        self.dark_mode = is_dark_mode()
        self._apply_theme(self.dark_mode, animate=False)
        self._theme_poll = Clock.schedule_interval(self._poll_theme, 4)
        self._background_music = None
        self._move_sound = None
        self._game_started = False
        self._multiplayer_active = False
        self._mp_room = None
        self._mp_poll_event = None
        self._mp_seq = 0
        self._mp_local_token = None
        self._mp_room_finished = False
        self.difficulty = app.config.getdefault("game", "difficulty", "normal") if app is not None else "normal"
        self.time_control = app.config.getint("game", "time_control") if app is not None and app.config.has_option("game", "time_control") else 0
        self.bot_thinking_delay = app.config.getboolean("game", "bot_thinking_delay") if app is not None and app.config.has_option("game", "bot_thinking_delay") else True
        self.board_palette = app.config.getdefault("game", "board_palette", "sage") if app is not None else "sage"
        self.piece_style = app.config.getdefault("game", "piece_style", "pixel") if app is not None else "pixel"
        saved_track = app.config.getdefault("game", "soundtrack", "friday_morning") if app is not None else "friday_morning"
        self.soundtrack_id = saved_track if saved_track in SOUNDTRACKS_BY_ID else "friday_morning"
        self.remaining_time = {chess.WHITE: 0.0, chess.BLACK: 0.0}
        self._clock_event = None
        self._last_clock_tick = time.monotonic()
        self._last_clock_save = self._last_clock_tick
        self._session_path = Path(app.user_data_dir) / "saved_game.json" if app is not None else None
        self._side_picker = None
        if app is not None:
            self.master_volume = app.config.getfloat("audio", "master_volume")
        self._volume_save_trigger = Clock.create_trigger(self._save_volume_setting, .5)
        Clock.schedule_once(self._start_audio, .8)
        self.menu_button = self.ids.menu_button
        self.menu_button.bind(on_release=self._open_about_menu)
        self.board_widget = ChessBoard(self, size_hint=(None, None))
        self.ids.board_container.add_widget(self.board_widget)
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.label import Label
        from chess_app.ui.widgets import CountryFlag, DeviceIcon
        self._opponent_identity = BoxLayout(orientation='horizontal', spacing=dp(7),
                                            size_hint=(None, None), size=(dp(198), dp(25)),
                                            opacity=0)
        self._opponent_flag = CountryFlag(country='ZZ', size_hint=(None, None), size=(dp(29), dp(19)))
        self._opponent_device = DeviceIcon(device='mobile', tint=self.muted_color,
                                           size_hint=(None,None), size=(dp(18),dp(22)))
        self._opponent_name = Label(text='', color=self.text_color, font_size='12sp', bold=True,
                                    halign='left', valign='middle', size_hint_x=None, width=dp(132))
        self._opponent_name.bind(size=lambda w, s: setattr(w, 'text_size', s))
        self._opponent_identity.add_widget(self._opponent_flag)
        self._opponent_identity.add_widget(self._opponent_device)
        self._opponent_identity.add_widget(self._opponent_name)
        self.add_widget(self._opponent_identity)
        self.bind(size=self._fit_board)
        Clock.schedule_once(self._fit_board, 0)
        self.bind(size=self._position_opponent_identity)
        self._position_opponent_identity()
        self._build_main_menu()
        self._show_main_menu()
        self._restore_saved_game()
        self.refresh()

    def _fit_board(self, *_):
        if not hasattr(self, "board_widget") or "board_container" not in self.ids:
            return
        box = self.ids.board_container
        side = min(box.width, box.height)
        self.board_widget.size = (side, side)
        self.board_widget.pos = (box.center_x - side / 2, box.center_y - side / 2)

    def _position_opponent_identity(self, *_):
        if hasattr(self, '_opponent_identity'):
            self._opponent_identity.pos = (dp(14), self.height - dp(36))

    def choose_square(self, square):
        if not self._game_started or getattr(self, '_mp_move_pending', False):
            return
        board = self.engine.board
        if board.turn != self.player_color:
            return
        if self.selection is not None:
            candidates = [m for m in self.engine.legal_moves_from(self.selection) if m.to_square == square]
            if candidates:
                move = next((m for m in candidates if m.promotion == chess.QUEEN), candidates[0])
                if self._multiplayer_active:
                    self.selection = None
                    self.board_widget.selected = []
                    self.board_widget.targets = []
                    self._send_multiplayer_move(move)
                    return
                self.engine.play(move)
                self._play_move_sound()
                self._consume_clock(chess.WHITE if self.player_color else chess.BLACK)
                self._save_game()
                self.selection = None
                self.board_widget.selected = []
                self.board_widget.targets = []
                drop_start = self.board_widget._drop_start_pos
                self.board_widget._drop_start_pos = None
                self.board_widget.animate_move(move, start_pos=drop_start)
                self.refresh()
                if (not self._multiplayer_active and self.engine.board.turn != self.player_color
                        and not self.engine.status()[1]):
                    Clock.schedule_once(self._start_bot, .30)
                elif not self._multiplayer_active:
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

    def refresh(self, redraw_board=True):
        status, finished = self.engine.status()
        if not finished and status != "CHECK":
            status = "YOUR TURN" if self.engine.board.turn == self.player_color else "OPPONENT THINKING"
            if self.engine.board.turn != self.player_color and self._bot_think_started_at is not None:
                elapsed = max(0, int(time.monotonic() - self._bot_think_started_at))
                status = f"OPPONENT THINKING · {elapsed // 60:02}:{elapsed % 60:02}"
        if self.time_control and self._game_started and not finished:
            side = self.engine.board.turn
            status = f"{status}  •  {self._clock_text(side)}"
        self.status_text = status
        if redraw_board and hasattr(self, "board_widget"):
            last = self.engine.board.peek() if self.engine.board.move_stack else None
            self.board_widget.last_move = [last.from_square, last.to_square] if last else []
            self.board_widget.check_square = chess.square_name(self.engine.board.king(self.engine.board.turn)) if self.engine.board.is_check() else ""
            self.board_widget.redraw()
        self.result_visible = self.engine.status()[1]
        if self.result_visible:
            self._finish_round()
