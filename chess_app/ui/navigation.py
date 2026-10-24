"""Main menu and in-game navigation actions."""

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.image import Image
from kivy.uix.label import Label

from chess_app.core.engine import ChessEngine
from chess_app.paths import asset_path
from chess_app.ui.widgets import MenuPanel, PixelButton, RoundCard, ToastMessage


class GameNavigationMixin:
    def _build_main_menu(self):
        self.main_menu = MenuPanel(orientation='vertical', spacing=dp(12),
                                   padding=(dp(16), dp(16)), size_hint=(.90, None),
                                   height=dp(420), pos_hint={'center_x': .5, 'center_y': .5})
        self.main_menu_card = RoundCard(orientation='vertical', spacing=dp(8),
                                        padding=(dp(20), dp(18)),
                                        size_hint_y=None,
                                        fill_color=(.16, .16, .15, 1) if self.dark_mode else (.99, .98, .95, 1),
                                        corner_radius=dp(24))
        self._main_menu_icon = Image(source=str(asset_path("pieces", "white-king.png"
                                                           if self.dark_mode else "black-king.png")),
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
        child_heights = sum(widget.height for widget in self.main_menu_card.children)
        child_spacing = self.main_menu_card.spacing * max(0, len(self.main_menu_card.children) - 1)
        card_padding = dp(36)
        self.main_menu_card.height = child_heights + child_spacing + card_padding
        self.main_menu.height = self.main_menu_card.height + dp(32)

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
        self._cancel_bot_thinking()
        self._game_started = False
        if self._clock_event is not None:
            self._clock_event.cancel()
            self._clock_event = None
        self.engine = ChessEngine()
        self.selection = None
        self.board_widget.flipped = False
        self._in_main_menu = False
        Animation.cancel_all(self.main_menu, 'opacity')
        fade = Animation(opacity=0, duration=.14, t='out_quad')
        fade.bind(on_complete=lambda *_: self._hide_main_menu())
        fade.start(self.main_menu)
        self.ids.board_container.disabled = False
        self.ids.board_container.opacity = 1
        self.ids.menu_button.disabled = False
        self.ids.status_label.opacity = 1
        # Draw the board as soon as Singleplayer is chosen so it is visible
        # behind the difficulty and side pickers, before a color is selected.
        self.refresh()
        self._side_picker = None
        Clock.schedule_once(self._show_difficulty_picker, .12)

    def _hide_main_menu(self):
        if not self._in_main_menu:
            self.main_menu.disabled = True
            self.ids.board_container.opacity = 1
            self.ids.menu_button.opacity = 1

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

