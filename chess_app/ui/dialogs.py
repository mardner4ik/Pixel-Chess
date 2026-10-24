"""Modal dialogs and settings controls for the main game screen."""

from kivy.animation import Animation
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.modalview import ModalView
import webbrowser

from chess_app.paths import asset_path
from chess_app.ui.board import ACCENT_PALETTES, BOARD_PALETTES
from chess_app.ui.soundtracks import SOUNDTRACKS, SOUNDTRACKS_BY_ID
from chess_app.ui.widgets import (PixelButton, RoundCard,
                                  IconActionButton, SettingsIcon)


class GameDialogsMixin:
    def _confirm_resignation(self):
        view = ModalView(size_hint=(.90, None), height=dp(156), auto_dismiss=True,
                         background='', background_color=(0, 0, 0, 0),
                         overlay_color=(0, 0, 0, .42))
        card = RoundCard(orientation='vertical', padding=(dp(20), dp(10)), spacing=dp(8),
                         fill_color=(.16, .16, .15, 1) if self.dark_mode else (.99, .98, .95, 1),
                         corner_radius=dp(24))
        heading = Label(text='Resign this game?', size_hint_y=None, height=dp(32),
                        bold=True, font_size='21sp', color=self.text_color, halign='left')
        heading.bind(size=lambda widget, size: setattr(widget, 'text_size', size))
        message = Label(text='Your opponent wins.',
                        size_hint_y=None, height=dp(30), color=self.muted_color,
                        font_size='15sp', halign='left')
        message.bind(size=lambda widget, size: setattr(widget, 'text_size', size))
        actions = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        actions.add_widget(Widget())
        keep = PixelButton(text='Cancel', size_hint=(None, 1), width=dp(112),
                           corner_radius=dp(12), font_size='14sp')
        keep.fill_color = (.31, .31, .30, 1) if self.dark_mode else (.85, .83, .79, 1)
        keep.text_color = self.text_color
        keep.bind(on_release=view.dismiss)
        resign = PixelButton(text='Resign', size_hint=(None, 1), width=dp(96),
                             corner_radius=dp(12), font_size='14sp')
        resign.fill_color = self.accent_color
        resign.text_color = self._accent_text_color(self.accent_color)
        resign.bind(on_release=lambda *_: self._accept_resignation(view))
        actions.add_widget(keep)
        actions.add_widget(resign)
        card.add_widget(heading)
        card.add_widget(message)
        card.add_widget(actions)
        view.add_widget(card)
        self._open_dialog_near_top(view, card)
        card.opacity = 0
        Animation(opacity=1, duration=.20, t='out_quad').start(card)

    def _accept_resignation(self, view):
        view.dismiss()
        self._cancel_bot_thinking()
        if getattr(self, '_multiplayer_active', False) and getattr(self, '_mp_room', None):
            room = self._mp_room
            self._mp_async(lambda: self._mp_client.resign(room['code'], room['token']))
            self._mp_room_finished = True
            if self._mp_poll_event:
                self._mp_poll_event.cancel()
                self._mp_poll_event = None
            self._multiplayer_active = False
        self._game_started = False
        if self._clock_event is not None:
            self._clock_event.cancel()
            self._clock_event = None
        if not getattr(self, '_mp_room', None):
            self._clear_saved_game()
        self.status_text = 'YOU RESIGNED'
        self.result_title = 'You resigned'
        self.result_detail = f'Opponent wins   ·   {len(self.engine.board.move_stack)} plies   ·   {self._elapsed_text()}'
        self.result_visible = True

    def _open_dialog_near_top(self, view, card):
        """Open a centered card, safely detaching it when a dialog is reopened."""
        old_container = getattr(view, "_dialog_container", None)
        parent = card.parent
        if parent is not None:
            parent.remove_widget(card)
        if old_container is not None and old_container.parent is view:
            view.remove_widget(old_container)

        # ModalView expands to the window when opened. Keep the original card
        # dimensions so reopening a dialog does not turn its card full-screen.
        if not hasattr(view, "_dialog_card_width_hint"):
            view._dialog_card_width_hint = view.size_hint_x or .90
            view._dialog_card_height = view.height
        width_hint = view._dialog_card_width_hint
        card_height = view._dialog_card_height
        view.size_hint = (1, 1)
        card.size_hint = (width_hint, None)
        card.height = card_height
        card.pos_hint = {"center_x": .5, "center_y": .5}
        container = FloatLayout(size_hint=(1, 1))
        container.add_widget(card)
        view.add_widget(container)
        view._dialog_container = container
        view.open()

    def _show_settings(self, *_):
        from kivy.uix.slider import Slider

        view = ModalView(size_hint=(.94, None), height=dp(382), auto_dismiss=True,
                         background="", background_color=(0, 0, 0, 0),
                         overlay_color=(0, 0, 0, .38))
        card = RoundCard(orientation="vertical", padding=(dp(20), dp(12)), spacing=dp(6),
                         fill_color=(.16, .16, .15, 1) if self.dark_mode else (.99, .98, .95, 1),
                         corner_radius=dp(28))
        heading = Label(text="Settings", size_hint_y=None, height=dp(34),
                        bold=True, font_size="24sp", color=self.text_color, halign="left")
        heading.bind(size=lambda widget, size: setattr(widget, "text_size", size))

        def section(title):
            label = Label(text=title, size_hint_y=None, height=dp(16),
                          color=self.muted_color, font_size="12sp", bold=True,
                          halign="left", valign="middle")
            label.bind(size=lambda widget, size: setattr(widget, "text_size", size))
            return label

        surface = (.29, .29, .28, 1) if self.dark_mode else (.90, .89, .86, 1)
        volume_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(10))
        volume_icon_holder = FloatLayout(size_hint=(None, 1), width=dp(36))
        volume_icon = SettingsIcon(icon="volume", tint=self.accent_color,
                                   size_hint=(None, None), size=(dp(24), dp(24)),
                                   pos_hint={"center_x": .5, "center_y": .5})
        volume_icon_holder.add_widget(volume_icon)
        volume_text = BoxLayout(orientation="vertical", spacing=-dp(2),
                                size_hint_x=None, width=dp(105))
        volume_title = Label(text="Master volume", color=self.text_color,
                             font_size="14sp", bold=True, halign="left", valign="bottom")
        volume_label = Label(text=f"{round(self.master_volume * 100)}%",
                             color=self.muted_color, font_size="12sp", halign="left", valign="top")
        volume_text.add_widget(volume_title)
        volume_text.add_widget(volume_label)
        volume_slider = Slider(min=0, max=1, value=self.master_volume,
                               cursor_size=(dp(24), dp(24)))
        volume_slider.value_track = True
        volume_slider.value_track_color = self.accent_color
        self._settings_slider = volume_slider
        volume_slider.bind(value=lambda _slider, value: self._update_volume_controls(
            value, volume_label))
        volume_row.add_widget(volume_icon_holder)
        volume_row.add_widget(volume_text)
        volume_row.add_widget(volume_slider)

        track = SOUNDTRACKS_BY_ID.get(self.soundtrack_id, SOUNDTRACKS[0])
        soundtrack_button = IconActionButton(
            icon="music", title="Background music", detail=track["title"],
            size_hint_y=None, height=dp(52), corner_radius=dp(14),
            fill_color=surface, text_color=self.text_color,
            muted_color=self.muted_color, icon_color=self.accent_color)
        soundtrack_button.bind(on_release=lambda *_: self._show_setting_choices(
            "Background music", [(track["id"], track["title"]) for track in SOUNDTRACKS],
            self.soundtrack_id, lambda value: self._choose_soundtrack(value, soundtrack_button), view))

        appearance_row = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(10))
        board_button = IconActionButton(
            icon="board", title="Board", detail=self.board_palette.title(),
            corner_radius=dp(14), fill_color=surface, text_color=self.text_color,
            muted_color=self.muted_color, icon_color=self.accent_color)
        pieces_button = IconActionButton(
            icon="piece", title="Pieces",
            detail="Vector" if self.piece_style == "vector" else "Pixel",
            corner_radius=dp(14), fill_color=surface, text_color=self.text_color,
            muted_color=self.muted_color, icon_color=self.accent_color)
        board_button.bind(on_release=lambda *_: self._show_setting_choices(
            "Board style", [(name, name.title()) for name in BOARD_PALETTES], self.board_palette,
            lambda value: self._choose_board_palette(value, board_button), view))
        pieces_button.bind(on_release=lambda *_: self._show_setting_choices(
            "Piece style", [("pixel", "Pixel"), ("vector", "Vector")], self.piece_style,
            lambda value: self._choose_piece_style(value, pieces_button), view))
        appearance_row.add_widget(board_button)
        appearance_row.add_widget(pieces_button)

        accent_name = "Auto" if self.accent_mode == "system" else self.accent_mode.title()
        accent_button = IconActionButton(
            icon="palette", title="Accent color", detail=accent_name,
            size_hint_y=None, height=dp(48), corner_radius=dp(14),
            fill_color=surface, text_color=self.text_color,
            muted_color=self.muted_color, icon_color=self.accent_color)
        accent_button.bind(on_release=lambda *_: self._show_setting_choices(
            "Accent color", [("system", "Auto")] + [(mode, mode.title()) for mode in ACCENT_PALETTES],
            self.accent_mode, lambda value: self._choose_accent(value, accent_button), view))

        close = PixelButton(text="Done", size_hint_y=None, height=dp(44),
                            font_size="15sp", corner_radius=dp(13),
                            fill_color=self.accent_color,
                            text_color=self._accent_text_color(self.accent_color))
        close.bind(on_release=view.dismiss)
        for widget in (heading, section("SOUND"), volume_row, soundtrack_button,
                       section("APPEARANCE"), appearance_row, accent_button, close):
            card.add_widget(widget)
        view.add_widget(card)
        self._open_dialog_near_top(view, card)
        card.opacity = 0
        Animation(opacity=1, duration=.20, t="out_quad").start(card)

    def _show_setting_choices(self, title, choices, selected, on_select, settings_view):
        """Show choices in a separate page, without stacking modal windows."""
        settings_view.dismiss(animation=False)
        Clock.schedule_once(lambda _dt: self._open_setting_choices(
            title, choices, selected, on_select), .05)

    def _open_setting_choices(self, title, choices, selected, on_select):
        row_height = dp(42)
        view_height = min(dp(440), dp(122) + len(choices) * (row_height + dp(5)))
        view = ModalView(size_hint=(.84, None), height=view_height, auto_dismiss=True,
                         background="", background_color=(0, 0, 0, 0),
                         overlay_color=(0, 0, 0, .40))
        card = RoundCard(orientation="vertical", padding=(dp(16), dp(14)), spacing=dp(8),
                         fill_color=(.16, .16, .15, 1) if self.dark_mode else (.99, .98, .95, 1),
                         corner_radius=dp(24))
        heading = Label(text=title, size_hint_y=None, height=dp(34), bold=True,
                        font_size="19sp", color=self.text_color, halign="left")
        heading.bind(size=lambda widget, size: setattr(widget, "text_size", size))
        rows = BoxLayout(orientation="vertical", size_hint_y=None,
                         height=row_height * len(choices) + dp(5) * max(0, len(choices) - 1),
                         spacing=dp(5))
        for value, caption in choices:
            mark = "✓  " if value == selected else ""
            option = PixelButton(text=mark + caption, size_hint_y=None, height=row_height,
                                 corner_radius=dp(12), font_size="14sp",
                                 fill_color=self.accent_color if value == selected else
                                 ((.29, .29, .28, 1) if self.dark_mode else (.90, .89, .86, 1)),
                                 text_color=self._accent_text_color(self.accent_color) if value == selected
                                 else self.text_color)
            option.bind(on_release=lambda *_args, choice=value: self._select_setting_choice(
                choice, on_select, view))
            rows.add_widget(option)
        back = PixelButton(text="Back", size_hint_y=None, height=dp(42),
                           font_size="14sp", corner_radius=dp(13),
                           fill_color=(.31, .31, .30, 1) if self.dark_mode else (.85, .83, .79, 1),
                           text_color=self.text_color)
        back.bind(on_release=lambda *_: view.dismiss(animation=False))
        card.add_widget(heading)
        card.add_widget(rows)
        card.add_widget(back)
        view.add_widget(card)
        self._open_dialog_near_top(view, card)
        view.bind(on_dismiss=self._restore_settings_after_picker)

    def _restore_settings_after_picker(self, *_):
        Clock.schedule_once(self._show_settings, .25)

    @staticmethod
    def _select_setting_choice(value, on_select, view):
        on_select(value)
        view.dismiss(animation=False)

    def _choose_soundtrack(self, value, button):
        self._set_soundtrack(value)
        button.detail_label.text = SOUNDTRACKS_BY_ID[value]["title"]

    def _choose_board_palette(self, value, button):
        self._set_board_palette(value)
        button.detail_label.text = value.title()

    def _choose_piece_style(self, value, button):
        self._set_piece_style(value)
        button.detail_label.text = value.title()

    def _choose_accent(self, value, button):
        self._set_accent_mode(value)
        button.detail_label.text = "Auto" if value == "system" else value.title()
        button.icon_color = self.accent_color

    def _update_volume_controls(self, value, label):
        label.text = f'{round(value * 100)}%'
        self._set_master_volume(value)

    def _show_about(self):
        self.show_info('About Pixel Chess',
                       'A minimalist chess game for focused play. Choose either side to play against the local opponent.\n\n'
                       'HOW TO PLAY\nTap a piece, then tap one of its highlighted legal moves.\n\n'
                       'MUSIC\nFriday Morning, Easy Lemon, Immersed, Morning, and Evening by Kevin MacLeod (incompetech.com), licensed under CC BY 4.0. Audio was converted from MP3 to mono WAV.\nhttps://creativecommons.org/licenses/by/4.0/\n\n'
                       'LICENSE\nGNU General Public License v3 (GPL-3.0).')

    def show_info(self, title, message):
        view = ModalView(size_hint=(.90, None), height=dp(480), auto_dismiss=True,
                         background='', background_color=(0, 0, 0, 0),
                         overlay_color=(0, 0, 0, .38))
        card = RoundCard(orientation='vertical', padding=(dp(22), dp(14), dp(22), dp(8)), spacing=dp(12),
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
        github_icon = Image(source=str(asset_path("github-mark-light.png" if self.dark_mode
                                               else "github-mark.png")),
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
        self._open_dialog_near_top(view, card)
        card.opacity = 0
        Animation(opacity=1, duration=.20, t='out_quad').start(card)

    def _open_repository(view):
        webbrowser.open("https://github.com/mardner4ik/Pixel-Chess")
        view.dismiss()
