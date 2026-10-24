"""Modal dialogs and settings controls for the main game screen."""

from kivy.app import App
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

from chess_app.ui.board import ACCENT_PALETTES
from chess_app.ui.system_theme import get_system_accent_color
from chess_app.ui.soundtracks import SOUNDTRACKS, SOUNDTRACKS_BY_ID
from chess_app.ui.widgets import PixelButton, AccentChoiceButton, RoundCard


class GameDialogsMixin:
    def _confirm_resignation(self):
        view = ModalView(size_hint=(.90, None), height=dp(172), auto_dismiss=True,
                         background='', background_color=(0, 0, 0, 0),
                         overlay_color=(0, 0, 0, .42))
        card = RoundCard(orientation='vertical', padding=(dp(20), dp(12), dp(20), dp(8)), spacing=dp(10),
                         fill_color=(.16, .16, .15, 1) if self.dark_mode else (.99, .98, .95, 1),
                         corner_radius=dp(24))
        heading = Label(text='Resign this game?', size_hint_y=None, height=dp(34),
                        bold=True, font_size='20sp', color=self.text_color, halign='left')
        heading.bind(size=lambda widget, size: setattr(widget, 'text_size', size))
        message = Label(text='Your opponent will win the game.',
                        size_hint_y=None, height=dp(36), color=self.muted_color,
                        font_size='14sp', halign='left')
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
        self._game_started = False
        if self._clock_event is not None:
            self._clock_event.cancel()
            self._clock_event = None
        self._clear_saved_game()
        self.status_text = 'YOU RESIGNED'
        self.result_title = 'You resigned'
        self.result_detail = f'Opponent wins   ·   {len(self.engine.board.move_stack)} plies   ·   {self._elapsed_text()}'
        self.result_visible = True

    def _open_dialog_near_top(self, view, card):
        # ModalView is an AnchorLayout and centers its direct child. Put the
        # card in a full-screen FloatLayout so it stays centered independently
        # of the dialog's internal padding and action layout.
        width_hint = view.size_hint_x or .90
        card_height = view.height
        view.size_hint = (1, 1)
        card.size_hint = (width_hint, None)
        card.height = card_height
        card.pos_hint = {"center_x": .5, "center_y": .5}
        view.remove_widget(card)
        container = FloatLayout(size_hint=(1, 1))
        container.add_widget(card)
        view.add_widget(container)
        view._dialog_container = container
        view.open()

    def _show_settings(self):
        from kivy.uix.slider import Slider

        view = ModalView(size_hint=(.92, None), height=dp(570), auto_dismiss=True,
                         background='', background_color=(0, 0, 0, 0),
                         overlay_color=(0, 0, 0, .38))
        card = RoundCard(orientation='vertical', padding=(dp(24), dp(18), dp(24), dp(14)), spacing=dp(10),
                         fill_color=(.16, .16, .15, 1) if self.dark_mode else (.99, .98, .95, 1),
                         corner_radius=dp(30))
        heading = Label(text='Settings', size_hint_y=None, height=dp(40), bold=True,
                        font_size='24sp', color=self.text_color, halign='left')
        heading.bind(size=lambda widget, size: setattr(widget, 'text_size', size))
        volume_label = Label(text=f'Master volume  {round(self.master_volume * 100)}%',
                             size_hint_y=None, height=dp(28), color=self.text_color,
                             font_size='16sp', halign='left')
        volume_label.bind(size=lambda widget, size: setattr(widget, 'text_size', size))
        slider = Slider(min=0, max=1, value=self.master_volume, size_hint_y=None,
                        height=dp(38), cursor_size=(dp(24), dp(24)))
        slider.value_track = True
        slider.value_track_color = self.accent_color
        self._settings_slider = slider
        slider.bind(value=lambda _slider, value: self._update_volume_controls(
            value, volume_label))
        difficulty_label = Label(text=f"Opponent strength  {self.difficulty.title()}  ·  tap to change",
                                 size_hint_y=None, height=dp(26), color=self.text_color,
                                 font_size='13sp', halign='left')
        difficulty_label.bind(size=lambda widget, size: setattr(widget, 'text_size', size))
        difficulty_button = PixelButton(text=difficulty_label.text, size_hint_y=None, height=dp(42),
                                        font_size='14sp', corner_radius=dp(13))
        difficulty_button.fill_color = (.31, .31, .30, 1) if self.dark_mode else (.85, .83, .79, 1)
        difficulty_button.text_color = self.text_color
        difficulty_button.bind(on_release=lambda *_: self._cycle_difficulty(difficulty_button))
        clock_button = PixelButton(text=f"Time control  ·  {'Off' if not self.time_control else str(self.time_control) + ' min'}  ·  tap to change",
                                   size_hint_y=None, height=dp(42), font_size='14sp', corner_radius=dp(13))
        clock_button.fill_color = (.31, .31, .30, 1) if self.dark_mode else (.85, .83, .79, 1)
        clock_button.text_color = self.text_color
        clock_button.bind(on_release=lambda *_: self._cycle_time_control(clock_button))
        board_button = PixelButton(text=f"Board colors  ·  {self.board_palette.title()}  ·  tap to change",
                                   size_hint_y=None, height=dp(42), font_size='14sp', corner_radius=dp(13))
        board_button.fill_color = (.31, .31, .30, 1) if self.dark_mode else (.85, .83, .79, 1)
        board_button.text_color = self.text_color
        board_button.bind(on_release=lambda *_: self._cycle_board_palette(board_button))
        pieces_button = PixelButton(text=f"Piece style  ·  {'Vector' if self.piece_style == 'vector' else 'Pixel'}  ·  tap to change",
                                    size_hint_y=None, height=dp(42), font_size='14sp', corner_radius=dp(13))
        pieces_button.fill_color = (.31, .31, .30, 1) if self.dark_mode else (.85, .83, .79, 1)
        pieces_button.text_color = self.text_color
        pieces_button.bind(on_release=lambda *_: self._cycle_piece_style(pieces_button))
        current_track = SOUNDTRACKS_BY_ID.get(self.soundtrack_id, SOUNDTRACKS[0])
        soundtrack_button = PixelButton(
            text=f"Music  ·  {current_track['title']}  ·  tap to change",
            size_hint_y=None, height=dp(42), font_size='14sp', corner_radius=dp(13))
        soundtrack_button.fill_color = (.31, .31, .30, 1) if self.dark_mode else (.85, .83, .79, 1)
        soundtrack_button.text_color = self.text_color
        soundtrack_button.bind(on_release=lambda *_: self._cycle_soundtrack(soundtrack_button))
        palette_label = Label(text='Accent color', size_hint_y=None, height=dp(24),
                              color=self.text_color, font_size='16sp', halign='left')
        palette_label.bind(size=lambda widget, size: setattr(widget, 'text_size', size))
        palette_row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(5))
        self._settings_accent_buttons = []
        palette_options = [('system', 'Auto', None)] + [
            (mode, mode.title(), color) for mode, color in ACCENT_PALETTES.items()]
        for mode, caption, color in palette_options:
            color = self.accent_color if mode == self.accent_mode else (
                color if color is not None else get_system_accent_color(self.dark_mode) or
                ((.83, .65, .55, 1) if self.dark_mode else (.65, .40, .31, 1)))
            choice = AccentChoiceButton(text=caption, size_hint=(1, 1),
                                        corner_radius=dp(11), font_size='12sp',
                                        fill_color=color,
                                        text_color=self._accent_text_color(color),
                                        selected=mode == self.accent_mode)
            choice._accent_mode = mode
            choice.bind(on_release=lambda *_args, selected=mode: self._set_accent_mode(selected))
            self._settings_accent_buttons.append(choice)
            palette_row.add_widget(choice)
        close = PixelButton(text='Done', size_hint_y=None, height=dp(50), font_size='16sp', corner_radius=dp(14))
        close.fill_color = (.31, .31, .30, 1) if self.dark_mode else (.85, .83, .79, 1)
        close.text_color = self.text_color
        close.ripple_color = (*self.accent_color[:3], .34)
        close.bind(on_release=view.dismiss)
        card.add_widget(heading)
        card.add_widget(volume_label)
        card.add_widget(slider)
        card.add_widget(difficulty_button)
        card.add_widget(clock_button)
        card.add_widget(soundtrack_button)
        card.add_widget(board_button)
        card.add_widget(pieces_button)
        card.add_widget(palette_label)
        card.add_widget(palette_row)
        card.add_widget(close)
        view.add_widget(card)
        self._open_dialog_near_top(view, card)
        card.opacity = 0
        Animation(opacity=1, duration=.20, t='out_quad').start(card)

    def _update_volume_controls(self, value, label):
        label.text = f'Master volume  {round(value * 100)}%'
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
        self._open_dialog_near_top(view, card)
        card.opacity = 0
        Animation(opacity=1, duration=.20, t='out_quad').start(card)

    def _open_repository(view):
        webbrowser.open("https://github.com/mardner4ik/Pixel-Chess")
        view.dismiss()
