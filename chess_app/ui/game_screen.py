from __future__ import annotations

import time
import random
import threading
import math
from pathlib import Path

import chess
from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.animation import Animation
from kivy.properties import ListProperty, StringProperty, NumericProperty, BooleanProperty, ColorProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.widget import Widget
from kivy.uix.modalview import ModalView
from kivy.uix.label import Label
from kivy.uix.image import Image

from chess_app.core.engine import ChessEngine
from chess_app.ui.system_theme import get_system_accent_color, is_dark_mode
from chess_app.ui.widgets import (PixelButton, MenuIconButton, AccentChoiceButton,
                                  MenuPanel, RoundCard, ToastMessage, SettingsIcon)
from chess_app.ui.board import ChessBoard, ACCENT_PALETTES, BOARD_PALETTES, BOT_POOL
from chess_app.ui.dialogs import GameDialogsMixin
from chess_app.ui.session import GameSessionMixin
from chess_app.ui.soundtracks import SOUNDTRACKS, SOUNDTRACKS_BY_ID

class GameScreen(GameDialogsMixin, GameSessionMixin, FloatLayout):
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
        self._bot_think_deadline = None
        self._bot_countdown_event = None
        app = App.get_running_app()
        self.accent_mode = (app.config.get("appearance", "accent_mode")
                            if app is not None else "system")
        self.dark_mode = is_dark_mode()
        self._apply_theme(self.dark_mode, animate=False)
        self._theme_poll = Clock.schedule_interval(self._poll_theme, 4)
        self._background_music = None
        self._move_sound = None
        self._game_started = False
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
        self._session_path = Path(app.user_data_dir) / "saved_game.json" if app is not None else None
        self._side_picker = None
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
        self._build_main_menu()
        self._show_main_menu()
        self._restore_saved_game()
        self.refresh()

    def _build_main_menu(self):
        self.main_menu = MenuPanel(orientation='vertical', spacing=dp(12),
                                   padding=(dp(16), dp(16)), size_hint=(.90, None),
                                   height=dp(470), pos_hint={'center_x': .5, 'center_y': .5})
        self.main_menu_card = RoundCard(orientation='vertical', spacing=dp(8),
                                        padding=(dp(20), dp(18)),
                                        fill_color=(.16, .16, .15, 1) if self.dark_mode else (.99, .98, .95, 1),
                                        corner_radius=dp(24))
        self._main_menu_icon = Image(source=("assets/pieces/white-king.png" if self.dark_mode
                                             else "assets/pieces/black-king.png"),
                                     size_hint_y=None, height=dp(72), fit_mode='contain')
        self._main_menu_buttons = []
        self._populate_main_menu("home")
        self.main_menu.add_widget(self.main_menu_card)
        self.add_widget(self.main_menu)

    def _populate_main_menu(self, page):
        self._main_menu_page = page
        self.main_menu_card.clear_widgets()
        self._main_menu_buttons = []
        self._main_menu_title = Label(
            text='Pixel Chess' if page == "home" else "Choose a mode",
            size_hint_y=None, height=dp(40), font_size='29sp', bold=True,
            color=self.text_color)
        self._main_menu_subtitle = Label(
            text='A calm game of chess' if page == "home" else 'Choose how you want to play',
            size_hint_y=None, height=dp(26), font_size='14sp', color=self.muted_color)
        self.main_menu_card.add_widget(self._main_menu_icon)
        self.main_menu_card.add_widget(self._main_menu_title)
        self.main_menu_card.add_widget(self._main_menu_subtitle)
        has_saved_game = self._has_saved_game()
        entries = (((('Continue', self._continue_saved_game, has_saved_game),) if has_saved_game else ()) +
                   (('Play', self._show_play_menu, True),
                    ('Settings', self._show_settings, True),
                    ('About', self._show_about, True)) if page == "home" else
                   (('Singleplayer', self._start_singleplayer, True),
                    ('Multiplayer', None, False),
                    ('Back', self._show_home_menu, True)))
        for caption, action, enabled in entries:
            button = PixelButton(text=caption, size_hint_y=None, height=dp(48),
                                 corner_radius=dp(15))
            button._main_menu_button = True
            button._menu_primary = caption in {'Play', 'Singleplayer'}
            button.ripple_color = (*self.accent_color[:3], .34)
            if button._menu_primary:
                button.fill_color = self.accent_color
                button.text_color = self._accent_text_color(self.accent_color)
                button.ripple_color = (*button.text_color[:3], .36)
            else:
                button.fill_color = (.25, .25, .24, 1) if self.dark_mode else (.88, .87, .84, 1)
                button.text_color = self.text_color
            button.disabled = not enabled
            if not enabled:
                button.opacity = .48
            if action:
                button.bind(on_release=lambda *_args, callback=action: callback())
            self.main_menu_card.add_widget(button)
            self._main_menu_buttons.append(button)

    def _show_play_menu(self):
        Animation.cancel_all(self.main_menu_card, 'opacity')
        fade = Animation(opacity=.25, duration=.08, t='out_quad')
        def switch_page(*_):
            self._populate_main_menu("play")
            Animation(opacity=1, duration=.16, t='out_quad').start(self.main_menu_card)
        fade.bind(on_complete=switch_page)
        fade.start(self.main_menu_card)

    def _show_home_menu(self):
        Animation.cancel_all(self.main_menu_card, 'opacity')
        fade = Animation(opacity=.25, duration=.08, t='out_quad')
        def switch_page(*_):
            self._populate_main_menu("home")
            Animation(opacity=1, duration=.16, t='out_quad').start(self.main_menu_card)
        fade.bind(on_complete=switch_page)
        fade.start(self.main_menu_card)

    def _show_main_menu(self):
        self._in_main_menu = True
        self.main_menu.opacity = 0
        self.main_menu.disabled = False
        self.ids.board_container.opacity = 0
        self.ids.board_container.disabled = True
        self.ids.menu_button.opacity = 0
        self.ids.menu_button.disabled = True
        self.ids.status_label.opacity = 0
        Animation.cancel_all(self.main_menu, 'opacity')
        Animation(opacity=1, duration=.22, t='out_quad').start(self.main_menu)

    def _start_singleplayer(self):
        self._in_main_menu = False
        Animation.cancel_all(self.main_menu, 'opacity')
        fade = Animation(opacity=0, duration=.14, t='out_quad')
        fade.bind(on_complete=lambda *_: self._hide_main_menu())
        fade.start(self.main_menu)
        self.ids.board_container.disabled = False
        self.ids.menu_button.disabled = False
        self.ids.status_label.opacity = 1
        self._side_picker = None
        Clock.schedule_once(self._show_difficulty_picker, .12)

    def _hide_main_menu(self):
        if not self._in_main_menu:
            self.main_menu.disabled = True
            self.ids.board_container.opacity = 1
            self.ids.menu_button.opacity = 1

    def _poll_theme(self, *_):
        dark = is_dark_mode()
        accent = get_system_accent_color(dark) if self.accent_mode == "system" else None
        accent_changed = ((accent is None and getattr(self, "_using_system_accent", False))
                          or (accent is not None and tuple(self.accent_color) != tuple(accent)))
        if dark != self.dark_mode or accent_changed:
            self._apply_theme(dark, system_accent=accent)

    def _start_audio(self, *_):
        # Force SDL2 before Kivy starts so WAV playback does not depend on
        # optional GStreamer decoder plugins installed by the operating system.
        try:
            from kivy.core.audio import SoundLoader
            from kivy.logger import Logger
            from kivy.resources import resource_find

            assets_dir = Path(__file__).resolve().parents[2] / "assets"
            if self._background_music is not None:
                self._background_music.stop()
            if self._move_sound is not None:
                self._move_sound.stop()
            track = SOUNDTRACKS_BY_ID.get(self.soundtrack_id, SOUNDTRACKS[0])
            for filename, target in ((track["file"], "music"), ("move.wav", "move")):
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

    def _apply_theme(self, dark, animate=True, system_accent=None):
        from kivy.core.window import Window

        self.dark_mode = dark
        default_accent = ((.83, .65, .55, 1) if dark else (.65, .40, .31, 1))
        system_accent = (system_accent if system_accent is not None else
                         get_system_accent_color(dark) if self.accent_mode == "system" else None)
        if self.accent_mode == "system":
            selected_accent = system_accent or default_accent
        else:
            selected_accent = ACCENT_PALETTES.get(self.accent_mode, default_accent)
        self._using_system_accent = self.accent_mode == "system" and system_accent is not None
        colors = ({"bg_color": (.10, .10, .10, 1), "surface_color": (.18, .18, .17, 1),
                   "text_color": (.94, .93, .90, 1), "muted_color": (.68, .67, .64, 1),
                   "accent_color": selected_accent} if dark else
                  {"bg_color": (.94, .93, .90, 1), "surface_color": (.88, .87, .83, 1),
                   "text_color": (.12, .12, .12, 1), "muted_color": (.37, .37, .35, 1),
                   "accent_color": selected_accent})
        if animate:
            Animation(**colors, duration=.28, t="out_quad").start(self)
        else:
            for name, value in colors.items():
                setattr(self, name, value)
        Window.clearcolor = colors["bg_color"]
        if hasattr(self, "main_menu_card"):
            self.main_menu_card.fill_color = ((.16, .16, .15, 1) if dark else (.99, .98, .95, 1))
            self._main_menu_icon.source = ("assets/pieces/white-king.png" if dark
                                           else "assets/pieces/black-king.png")
            self._main_menu_title.color = colors["text_color"]
            self._main_menu_subtitle.color = colors["muted_color"]
            for button in self._main_menu_buttons:
                if button._menu_primary:
                    button.fill_color = colors["accent_color"]
                    button.text_color = self._accent_text_color(colors["accent_color"])
                    button.ripple_color = (*button.text_color[:3], .36)
                else:
                    button.fill_color = (.25, .25, .24, 1) if dark else (.88, .87, .84, 1)
                    button.text_color = colors["text_color"]
                    button.ripple_color = (*colors["accent_color"][:3], .34)
        settings_slider = getattr(self, "_settings_slider", None)
        if settings_slider is not None:
            settings_slider.value_track_color = colors["accent_color"]
        for widget in self.walk():
            if isinstance(widget, PixelButton):
                if (getattr(widget, "_main_menu_button", False)
                        or isinstance(widget, AccentChoiceButton)
                        or hasattr(widget, "_difficulty_level")
                        or getattr(widget, "_difficulty_continue", False)):
                    continue
                widget.fill_color = (.31, .31, .30, 1) if dark else (.85, .83, .79, 1)
                widget.text_color = colors["text_color"]
                widget.ripple_color = ((.90, .89, .86, .42) if dark else (.25, .25, .23, .30))
                if hasattr(widget, "_github_icon"):
                    widget._github_icon.source = (
                        "assets/github-mark-light.png" if dark else "assets/github-mark.png")
                    widget._github_label.color = colors["text_color"]
        self._refresh_accent_choices(colors["accent_color"])
        self._refresh_difficulty_choices()
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
                    if getattr(widget, "_result_action", "") == "restart":
                        widget.fill_color = colors["accent_color"]
                        widget.text_color = self._accent_text_color(colors["accent_color"])
                    else:
                        widget.fill_color = (.31, .31, .30, 1) if dark else (.85, .83, .79, 1)
                        widget.text_color = colors["text_color"]
                    widget.ripple_color = ((.90, .89, .86, .42) if dark else (.25, .25, .23, .30))
        if self.menu_popup is not None and hasattr(self.menu_popup, "_surface_color"):
            self.menu_popup._surface_color.rgba = ((.17, .17, .16, 1) if dark else (.98, .97, .94, 1))
            for item in getattr(self.menu_popup, "_items", []):
                item.text_color = colors["text_color"]
        if self.menu_open:
            self._set_menu_button_active(True)

    @staticmethod
    def _accent_text_color(color):
        luminance = .2126 * color[0] + .7152 * color[1] + .0722 * color[2]
        return (.10, .10, .10, 1) if luminance >= .52 else (.99, .98, .95, 1)

    def _refresh_accent_choices(self, active_color=None):
        choices = getattr(self, "_settings_accent_buttons", ())
        system_color = get_system_accent_color(self.dark_mode) or (
            (.83, .65, .55, 1) if self.dark_mode else (.65, .40, .31, 1))
        for button in choices:
            mode = button._accent_mode
            color = (active_color if mode == "system" else ACCENT_PALETTES[mode])
            if mode == "system":
                color = system_color
            button.fill_color = color
            button.text_color = self._accent_text_color(color)
            button.selected = self.accent_mode == mode

    def _set_accent_mode(self, mode):
        self.accent_mode = mode if mode == "system" or mode in ACCENT_PALETTES else "system"
        app = App.get_running_app()
        if app is not None:
            app.config.set("appearance", "accent_mode", self.accent_mode)
            app.config.write()
        self._apply_theme(self.dark_mode, animate=True)

    def _open_about_menu(self, *_):
        if self.menu_open:
            self._close_about_menu()
            return
        from kivy.graphics import Color, RoundedRectangle
        self.menu_open = True
        self.menu_popup = self.ids.popup_layer
        popup_width = min(dp(236), max(dp(200), self.width - dp(32)))
        popup_height = dp(52 * 5)
        self.menu_popup.size = (popup_width, popup_height)
        self.menu_popup.padding = dp(0)
        self.menu_popup.spacing = dp(0)
        self.menu_popup.clear_widgets()
        self.menu_popup.canvas.before.clear()
        with self.menu_popup.canvas.before:
            self.menu_popup._surface_color = Color(*((.17, .17, .16, 1) if self.dark_mode else (.98, .97, .94, 1)))
            self.menu_popup._surface = RoundedRectangle(pos=self.menu_popup.pos, size=self.menu_popup.size,
                                                        radius=[0])
        self.menu_popup.bind(pos=lambda w, p: setattr(w._surface, 'pos', p),
                             size=lambda w, s: setattr(w._surface, 'size', s))
        self.menu_popup._items = []
        for text, callback in (("Settings", self._select_settings),
                               ("About", self._select_about),
                               ("Save", self._select_save),
                               ("Undo move", self._select_undo),
                               ("Resign", self._select_resign)):
            item = PixelButton(text=text, font_size='15sp', size_hint=(1, 1), corner_radius=0,
                               fill_color=(.23, .23, .22, 1) if self.dark_mode else (.91, .90, .87, 1),
                               text_color=self.text_color,
                               ripple_color=(.88, .87, .84, .38) if self.dark_mode else (.24, .23, .21, .24),
                               halign='center', valign='middle', padding=(0, 0))
            if text == "Undo move" and not self.can_undo_move():
                item.disabled = True
                item.opacity = .45
            item.bind(size=lambda w, s: setattr(w, 'text_size', s),
                      on_release=lambda *_args, action=callback: Clock.schedule_once(
                          lambda _dt: action(), .12))
            self.menu_popup._items.append(item)
            self.menu_popup.add_widget(item)
        self._position_about_menu()
        self._set_menu_button_active(True)
        self.menu_popup.opacity = 0
        Animation.cancel_all(self.menu_popup, 'opacity')
        Animation(opacity=1, duration=.18, t='out_quad').start(self.menu_popup)

    def _position_about_menu(self, *_):
        if not self.menu_open or not self.menu_popup:
            return
        button = self.menu_button
        menu = self.menu_popup
        # Both controls are direct children of the screen's FloatLayout.
        x = max(dp(8), min(self.width - menu.width - dp(8), button.right - menu.width))
        y = button.y - menu.height - dp(8)
        if y < dp(8):
            y = button.top + dp(8)
        self.popup_position = [x, y]
        menu._surface.pos = (x, y)
        menu._surface.size = menu.size

    def _close_about_menu(self):
        if self.menu_popup is not None:
            self.menu_popup.clear_widgets()
            self.menu_popup.canvas.before.clear()
        self.menu_popup = None
        self.menu_open = False
        self.ids.popup_layer.size = (0, 0)
        self._set_menu_button_active(False)

    def _set_menu_button_active(self, active):
        button = self.menu_button
        Animation.cancel_all(button, 'y')
        if active:
            if self._menu_button_home_y is None or self._menu_button_home_window != (self.width, self.height):
                self._menu_button_home_y = button.y
                self._menu_button_home_window = (self.width, self.height)
            button.fill_color = self.accent_color
            button.text_color = self._accent_text_color(self.accent_color)
            button.ripple_color = (*self.accent_color[:3], .5)
            Animation(y=self._menu_button_home_y + dp(4), duration=.14,
                      t='out_quad').start(button)
        else:
            button.fill_color = (.31, .31, .30, 1) if self.dark_mode else (.85, .83, .79, 1)
            button.text_color = self.text_color
            button.ripple_color = ((.90, .89, .86, .42) if self.dark_mode
                                   else (.25, .25, .23, .30))
            if self._menu_button_home_y is not None:
                Animation(y=self._menu_button_home_y, duration=.16,
                          t='out_quad').start(button)

    def _select_about(self):
        self._close_about_menu()
        self._show_about()

    def _select_settings(self):
        self._close_about_menu()
        self._show_settings()

    def _select_save(self):
        self._close_about_menu()
        self.save_game()

    def _select_undo(self):
        self._close_about_menu()
        self.undo_move()

    def _select_resign(self):
        self._close_about_menu()
        if self._game_started:
            self._confirm_resignation()

    def _show_toast(self, message):
        if self._toast_event is not None:
            self._toast_event.cancel()
            self._toast_event = None
        if self._toast_message is not None and self._toast_message.parent is self:
            Animation.cancel_all(self._toast_message, "opacity")
            self.remove_widget(self._toast_message)
        toast = ToastMessage(message, size_hint=(None, None),
                             size=(dp(250), dp(48)), opacity=0,
                             pos_hint={"center_x": .5, "y": .025})
        self._toast_message = toast
        self.add_widget(toast)
        Animation(opacity=1, duration=.14, t="out_quad").start(toast)

        def dismiss_toast(_dt):
            fade = Animation(opacity=0, duration=.18, t="out_quad")
            def remove_toast(*_):
                if toast.parent is self:
                    self.remove_widget(toast)
                if self._toast_message is toast:
                    self._toast_message = None
                    self._toast_event = None
            fade.bind(on_complete=remove_toast)
            fade.start(toast)
        self._toast_event = Clock.schedule_once(dismiss_toast, 1.6)




















    def on_touch_down(self, touch):
        if self.menu_open and self.menu_popup and not self.menu_popup.collide_point(*touch.pos):
            self._close_about_menu()
        return super().on_touch_down(touch)



    @staticmethod

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
                self._consume_clock(chess.WHITE if self.player_color else chess.BLACK)
                self._save_game()
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

    def _cancel_bot_thinking(self):
        self._game_generation += 1
        if self._bot_cancel_event is not None:
            self._bot_cancel_event.set()
            self._bot_cancel_event = None
        self._bot_think_deadline = None
        if self._bot_countdown_event is not None:
            self._bot_countdown_event.cancel()
            self._bot_countdown_event = None

    def _start_bot(self, *_):
        if self._game_started and self.engine.board.turn != self.player_color and not self.engine.status()[1]:
            if self._bot_cancel_event is not None:
                return
            snapshot = self.engine.board.copy(stack=True)
            generation = self._game_generation
            cancel_event = threading.Event()
            self._bot_cancel_event = cancel_event
            thinking_time = random.uniform(4.0, 15.0) if self.bot_thinking_delay else 0.0
            if thinking_time:
                self._bot_think_deadline = time.monotonic() + thinking_time
                self._bot_countdown_event = Clock.schedule_interval(self._update_bot_countdown, .25)
                self._update_bot_countdown()
            future = BOT_POOL.submit(self._calculate_bot_move, snapshot, self.difficulty,
                                     thinking_time, cancel_event)
            future.add_done_callback(lambda result: Clock.schedule_once(
                lambda _dt: self._apply_bot_result(result, generation, cancel_event), 0))

    @staticmethod
    def _calculate_bot_move(board, difficulty="normal", thinking_time=None, cancel_event=None):
        engine = ChessEngine()
        engine.board = board
        return engine.bot_move(difficulty, thinking_time, cancel_event)

    def _update_bot_countdown(self, *_):
        if self._bot_think_deadline is None or not self._game_started:
            return False
        remaining = max(0, math.ceil(self._bot_think_deadline - time.monotonic()))
        status = f"OPPONENT THINKING · {remaining}s"
        if self.time_control:
            status += f"  •  {self._clock_text(self.engine.board.turn)}"
        self.status_text = status

    def _apply_bot_result(self, future, generation=None, cancel_event=None):
        if (generation != self._game_generation or cancel_event is not self._bot_cancel_event
                or cancel_event is None or cancel_event.is_set() or not self._game_started
                or self.engine.board.turn == self.player_color or self.engine.status()[1]):
            return
        self._bot_cancel_event = None
        self._bot_think_deadline = None
        if self._bot_countdown_event is not None:
            self._bot_countdown_event.cancel()
            self._bot_countdown_event = None
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

    def refresh(self):
        status, finished = self.engine.status()
        if not finished and status != "CHECK":
            status = "YOUR TURN" if self.engine.board.turn == self.player_color else "OPPONENT THINKING"
            if self.engine.board.turn != self.player_color and self._bot_think_deadline is not None:
                remaining = max(0, math.ceil(self._bot_think_deadline - time.monotonic()))
                status = f"OPPONENT THINKING · {remaining}s"
        if self.time_control and self._game_started and not finished:
            side = self.engine.board.turn
            status = f"{status}  •  {self._clock_text(side)}"
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
        if not self._game_started and self.result_visible:
            return
        self._game_started = False
        self._cancel_bot_thinking()
        status, _ = self.engine.status()
        self.result_title = "Game over"
        self.result_detail = f"{status}   ·   {len(self.engine.board.move_stack)} plies   ·   {self._elapsed_text()}"
        self.result_visible = True
        if self._clock_event is not None:
            self._clock_event.cancel()
            self._clock_event = None
        self._clear_saved_game()

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

            overlay = ModalView(size_hint=(.88, None), height=dp(260), auto_dismiss=False,
                                background='', background_color=(0, 0, 0, 0),
                                overlay_color=(.06, .06, .06, .48))
            content = RoundCard(orientation='vertical', padding=(dp(22), dp(14), dp(22), dp(8)), spacing=dp(12),
                                fill_color=(.15, .15, .14, 1) if self.dark_mode else (.96, .95, .92, 1),
                                corner_radius=dp(28))
            title = Label(color=self.text_color, bold=True, font_size='23sp', size_hint_y=None, height=dp(44))
            detail = Label(color=self.muted_color, font_size='14sp', halign='center')
            detail.bind(size=lambda widget, size: setattr(widget, 'text_size', size))
            actions = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(10))
            home = PixelButton(text='Main menu')
            home._result_action = 'home'
            home.fill_color = (.31, .31, .30, 1) if self.dark_mode else (.85, .83, .79, 1)
            home.text_color = self.text_color
            home.bind(on_release=lambda *_: self._return_to_main_menu())
            restart = PixelButton(text='Restart')
            restart._result_action = 'restart'
            restart.fill_color = self.accent_color
            restart.text_color = self._accent_text_color(self.accent_color)
            restart.ripple_color = (*self.accent_color[:3], .34)
            restart.bind(on_release=lambda *_: self.new_game())
            actions.add_widget(home)
            actions.add_widget(restart)
            content.add_widget(title)
            content.add_widget(detail)
            content.add_widget(actions)
            overlay._result_card = content
            overlay.add_widget(content)
            overlay._title_label = title
            overlay._detail_label = detail
            self.result_overlay = overlay

        self.result_overlay._title_label.text = self.result_title
        self.result_overlay._detail_label.text = self.result_detail
        if not self.result_overlay._is_open:
            self._open_dialog_near_top(self.result_overlay, self.result_overlay._result_card)

    def _return_to_main_menu(self):
        self._cancel_bot_thinking()
        self._game_started = False
        self.selection = None
        self.result_visible = False
        if self.result_overlay is not None:
            self.result_overlay.dismiss()
        self._populate_main_menu("home")
        self._show_main_menu()


    def new_game(self):
        self._cancel_bot_thinking()
        self._game_started = False
        if self.result_overlay is not None:
            self.result_overlay.dismiss()
        self.result_visible = False
        Clock.schedule_once(self._show_difficulty_picker, .12)

    def _show_difficulty_picker(self, *_):
        if getattr(self, "_difficulty_picker", None) is not None and self._difficulty_picker._is_open:
            return
        view = ModalView(size_hint=(.90, None), height=dp(320), auto_dismiss=False,
                         background="", background_color=(0, 0, 0, 0),
                         overlay_color=(0, 0, 0, .42))
        card = RoundCard(orientation="vertical", padding=(dp(20), dp(16)), spacing=dp(12),
                         fill_color=(.16, .16, .15, 1) if self.dark_mode else (.99, .98, .95, 1),
                         corner_radius=dp(26))
        heading = Label(text="Choose difficulty", size_hint_y=None, height=dp(38),
                        bold=True, font_size="22sp", color=self.text_color)
        note = Label(text="Easy is relaxed; Hard spends longer searching", size_hint_y=None,
                     height=dp(26), font_size="14sp", color=self.muted_color)
        choices_row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        choice_buttons = {}
        for level in ("easy", "normal", "hard"):
            button = PixelButton(text=level.title(), corner_radius=dp(14), font_size="14sp")
            button._difficulty_level = level
            button.bind(on_release=lambda *_args, selected=level: self._select_difficulty(selected))
            choice_buttons[level] = button
            choices_row.add_widget(button)
        advanced = PixelButton(text="Advanced  ▾", size_hint_y=None, height=dp(48),
                               corner_radius=dp(14), font_size="14sp")
        advanced_icon = SettingsIcon(icon="settings", size_hint=(None, None),
                                     size=(dp(20), dp(20)), tint=self.accent_color)
        advanced.add_widget(advanced_icon)
        def position_advanced_icon(button, *_args):
            advanced_icon.pos = (button.x + dp(14), button.center_y - advanced_icon.height / 2)
        advanced.bind(pos=position_advanced_icon, size=position_advanced_icon)
        advanced_options = BoxLayout(orientation="vertical", size_hint_y=None,
                                     height=dp(0), spacing=dp(6), opacity=0)
        thinking_toggle = PixelButton(text="Bot thinking: 4–15 seconds", size_hint_y=None,
                                      height=dp(38), corner_radius=dp(12), font_size="13sp")
        thinking_toggle.disabled = True
        thinking_toggle.bind(on_release=lambda *_: self._toggle_bot_thinking(thinking_toggle))
        advanced_options.add_widget(thinking_toggle)
        time_row = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(5))
        time_buttons = {}
        for minutes, caption in ((0, "Off"), (3, "3 min"), (5, "5 min"), (10, "10 min")):
            option = PixelButton(text=caption, corner_radius=dp(11), font_size="12sp")
            option.disabled = True
            option.bind(on_release=lambda *_args, value=minutes: self._set_picker_time(value))
            time_buttons[minutes] = option
            time_row.add_widget(option)
        advanced_options.add_widget(time_row)
        advanced._picker_view = view
        advanced.bind(on_release=self._toggle_advanced_options_from_button)
        actions = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
        back = PixelButton(text="Back", corner_radius=dp(14), font_size="14sp")
        back.bind(on_release=lambda *_: self._cancel_difficulty_picker(view))
        continue_button = PixelButton(text="Choose color", corner_radius=dp(14), font_size="14sp")
        continue_button.fill_color = self.accent_color
        continue_button.text_color = self._accent_text_color(self.accent_color)
        continue_button._difficulty_continue = True
        continue_button.bind(on_release=lambda *_: self._continue_to_side_picker(view))
        actions.add_widget(back)
        actions.add_widget(continue_button)
        card.add_widget(heading)
        card.add_widget(note)
        card.add_widget(choices_row)
        card.add_widget(advanced)
        card.add_widget(advanced_options)
        card.add_widget(actions)
        view.add_widget(card)
        view._difficulty_choices = choice_buttons
        view._difficulty_continue_button = continue_button
        view._difficulty_card = card
        view._advanced_options = advanced_options
        view._advanced_button = advanced
        view._thinking_toggle = thinking_toggle
        view._time_buttons = time_buttons
        view._advanced_controls = [thinking_toggle, *time_buttons.values()]
        self._difficulty_picker = view
        self._refresh_difficulty_choices()
        self._refresh_advanced_picker()
        self._open_dialog_near_top(view, card)
        card.opacity = 0
        Animation(opacity=1, duration=.20, t="out_quad").start(card)

    def _refresh_difficulty_choices(self):
        view = getattr(self, "_difficulty_picker", None)
        if view is None:
            return
        for level, button in view._difficulty_choices.items():
            if level == self.difficulty:
                button.fill_color = self.accent_color
                button.text_color = self._accent_text_color(self.accent_color)
            else:
                button.fill_color = (.31, .31, .30, 1) if self.dark_mode else (.85, .83, .79, 1)
                button.text_color = self.text_color
        continue_button = view._difficulty_continue_button
        continue_button.fill_color = self.accent_color
        continue_button.text_color = self._accent_text_color(self.accent_color)

    def _select_difficulty(self, level):
        self.difficulty = level if level in {"easy", "normal", "hard"} else "normal"
        app = App.get_running_app()
        if app is not None:
            app.config.set("game", "difficulty", self.difficulty)
            app.config.write()
        self._refresh_difficulty_choices()

    def _toggle_advanced_options_from_button(self, button):
        self._toggle_advanced_options(button._picker_view)

    def _toggle_advanced_options(self, view):
        options = view._advanced_options
        expanded = options.height <= dp(1)
        options.height = dp(86) if expanded else dp(0)
        options.opacity = 1 if expanded else 0
        for control in view._advanced_controls:
            control.disabled = not expanded
        view._advanced_button.text = "Advanced  ▴" if expanded else "Advanced  ▾"
        view._difficulty_card.height = dp(410 if expanded else 320)

    def _refresh_advanced_picker(self):
        view = getattr(self, "_difficulty_picker", None)
        if view is None:
            return
        view._thinking_toggle.text = ("Bot thinking: 4–15 seconds" if self.bot_thinking_delay
                                      else "Bot moves instantly")
        for minutes, button in view._time_buttons.items():
            selected = self.time_control == minutes
            button.fill_color = self.accent_color if selected else (
                (.31, .31, .30, 1) if self.dark_mode else (.85, .83, .79, 1))
            button.text_color = self._accent_text_color(self.accent_color) if selected else self.text_color

    def _toggle_bot_thinking(self, button):
        self.bot_thinking_delay = not self.bot_thinking_delay
        app = App.get_running_app()
        if app is not None:
            app.config.set("game", "bot_thinking_delay", str(self.bot_thinking_delay))
            app.config.write()
        self._refresh_advanced_picker()

    def _set_picker_time(self, minutes):
        self.time_control = minutes if minutes in {0, 3, 5, 10} else 0
        app = App.get_running_app()
        if app is not None:
            app.config.set("game", "time_control", str(self.time_control))
            app.config.write()
        self._refresh_advanced_picker()

    def _continue_to_side_picker(self, view):
        view.dismiss()
        Clock.schedule_once(self._show_side_picker, .12)

    def _cancel_difficulty_picker(self, view):
        view.dismiss()
        self._populate_main_menu("home")
        self._show_main_menu()

    def _show_side_picker(self, *_):
        if self._side_picker is not None and self._side_picker._is_open:
            return
        view = ModalView(size_hint=(.82, None), height=dp(200), auto_dismiss=False,
                         background='', background_color=(0, 0, 0, 0),
                         overlay_color=(0, 0, 0, .42))
        card = RoundCard(orientation='vertical', padding=(dp(14), dp(12), dp(14), dp(8)), spacing=dp(8),
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
        self._open_dialog_near_top(view, card)
        card.opacity = 0
        Animation(opacity=1, duration=.20, t='out_quad').start(card)
        Clock.schedule_once(fit_role_cards, 0)

    def _begin_game(self, player_color, view):
        self._cancel_bot_thinking()
        view.dismiss()
        self._side_picker = None
        Animation.cancel_all(self.board_widget)
        self.board_widget.animating = False
        self.board_widget.previous_move = []
        self.board_widget.anim_progress = 1
        self.engine = ChessEngine()
        self.player_color = bool(player_color)
        self.remaining_time = {chess.WHITE: float(self.time_control * 60),
                               chess.BLACK: float(self.time_control * 60)}
        self._last_clock_tick = time.monotonic()
        if self._clock_event is not None:
            self._clock_event.cancel()
        if self.time_control:
            self._clock_event = Clock.schedule_interval(self._tick_clock, .25)
        self.board_widget.flipped = not self.player_color
        self.started_at = time.monotonic()
        self.result_visible = False
        self._game_started = True
        self._save_game()
        self.selection = None
        self.board_widget.selected = []
        self.board_widget.targets = []
        self.refresh()
        if self.engine.board.turn != self.player_color:
            Clock.schedule_once(self._start_bot, .25)

