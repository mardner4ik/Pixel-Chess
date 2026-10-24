"""Result handling and new-game selection flow."""

import time

import chess
from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.widget import Widget

from chess_app.core.engine import ChessEngine
from chess_app.ui.widgets import PixelButton, RoundCard, SettingsIcon


class GameFlowMixin:
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
        advanced = PixelButton(text="Advanced", size_hint_y=None, height=dp(48),
                               corner_radius=dp(14), font_size="14sp")
        advanced_icon = SettingsIcon(icon="settings", size_hint=(None, None),
                                     size=(dp(20), dp(20)), tint=self.accent_color)
        advanced_indicator = SettingsIcon(icon="down", size_hint=(None, None),
                                          size=(dp(16), dp(16)), tint=self.muted_color)
        advanced.add_widget(advanced_icon)
        advanced.add_widget(advanced_indicator)
        def position_advanced_icon(button, *_args):
            advanced_icon.pos = (button.x + dp(14), button.center_y - advanced_icon.height / 2)
            advanced_indicator.pos = (button.right - dp(28),
                                      button.center_y - advanced_indicator.height / 2)
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
        view._advanced_indicator = advanced_indicator
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
        view._advanced_indicator.icon = "up" if expanded else "down"
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
            icon = Image(source=str(asset_path("pieces", icon_name)), fit_mode='contain')
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
        self._last_clock_save = self._last_clock_tick
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

