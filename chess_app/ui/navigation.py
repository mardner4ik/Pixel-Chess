"""Main menu and in-game navigation actions."""

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.scrollview import ScrollView
from concurrent.futures import ThreadPoolExecutor
from kivy.app import App
from urllib.parse import urlsplit
import ipaddress
import time

import chess
from chess_app.core.engine import ChessEngine
from chess_app.multiplayer_client import MultiplayerClient
from chess_app.paths import asset_path
from chess_app.ui.widgets import (MenuPanel, PixelButton, RoundCard, ToastMessage,
                                  CountryFlag, RoomEntryButton)

MP_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix='pixel-chess-network')


class GameNavigationMixin:
    def _build_main_menu(self):
        self.main_menu = MenuPanel(orientation='vertical', spacing=dp(12),
                                   padding=(dp(8), dp(8)), size_hint=(.90, None),
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
        self.bind(size=self._fit_main_menu)
        self.bind(size=self._handle_multiplayer_resize)
        self._fit_main_menu()

    def _handle_multiplayer_resize(self, *_):
        if getattr(self, '_main_menu_page', '') != 'multiplayer_lobby':
            return
        landscape = self.width > self.height * 1.08
        if landscape != getattr(self, '_mp_lobby_landscape', landscape):
            self._show_multiplayer_lobby()

    def _fit_main_menu(self, *_):
        if not hasattr(self, 'main_menu_card'):
            return
        multiplayer = getattr(self, '_main_menu_page', '').startswith('multiplayer')
        self.main_menu.size_hint_x = .96 if multiplayer else .90
        available = max(dp(260), self.height - (dp(24) if multiplayer else dp(32)))
        if multiplayer:
            self.main_menu.height = available
            self.main_menu_card.padding = (dp(24), dp(20))
            self.main_menu_card.height = max(dp(220), available - dp(16))
        else:
            self.main_menu_card.padding = (dp(20), dp(18))
            self.main_menu.height = min(self.main_menu_card.height + dp(16), available)

    def _populate_main_menu(self, page):
        self._main_menu_page = page
        self._main_menu_icon.height = dp(0) if page.startswith('multiplayer') else dp(72)
        self.main_menu_card.clear_widgets()
        self._main_menu_buttons = []
        self._main_menu_title = Label(
            text='Pixel Chess' if page == "home" else "Choose a mode",
            size_hint_y=None, height=dp(44),
            font_size='34sp' if page.startswith('multiplayer') else '29sp', bold=True,
            color=self.text_color)
        self._main_menu_subtitle = Label(
            text='A calm game of chess' if page == "home" else 'Choose how you want to play',
            size_hint_y=None, height=dp(28),
            font_size='16sp' if page.startswith('multiplayer') else '14sp', color=self.muted_color)
        self.main_menu_card.add_widget(self._main_menu_icon)
        self.main_menu_card.add_widget(self._main_menu_title)
        self.main_menu_card.add_widget(self._main_menu_subtitle)
        has_saved_game = self._has_saved_game()
        if page == "home":
            entries = (((('Continue', self._continue_saved_game, has_saved_game),) if has_saved_game else ()) +
                       (('Play', self._show_play_menu, True),
                        ('Settings', self._show_settings, True),
                        ('About', self._show_about, True)))
        elif page == "play":
            entries = (('Singleplayer', self._start_singleplayer, True),
                       ('Multiplayer', self._open_multiplayer, True),
                       ('Back', self._show_home_menu, True))
        else:
            entries = ()
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
        self._fit_main_menu()

    def _mp_label(self, text, height=dp(28), font_size='14sp'):
        label = Label(text=text, size_hint_y=None, height=height,
                      font_size=font_size, color=self.muted_color,
                      halign='center', valign='middle')
        label.bind(size=lambda w, s: setattr(w, 'text_size', (s[0] - dp(8), None)))
        return label

    def _mp_centered_form(self, width_hint=.84):
        form = BoxLayout(orientation='vertical', size_hint=(width_hint, None),
                         spacing=dp(12))
        form.bind(minimum_height=form.setter('height'))
        anchor = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=1)
        anchor.add_widget(form)
        self.main_menu_card.add_widget(anchor)
        return form

    def _mp_button(self, caption, callback, primary=False):
        button = PixelButton(text=caption, size_hint_y=None, height=dp(50),
                             corner_radius=dp(14))
        button.fill_color = (self.accent_color if primary else
                             ((.25, .25, .24, 1) if self.dark_mode else (.88, .87, .84, 1)))
        button.text_color = self._accent_text_color(self.accent_color) if primary else self.text_color
        button.bind(on_release=lambda *_: callback())
        return button

    def _multiplayer_config(self):
        app = App.get_running_app()
        return app.config if app is not None else None

    def _open_multiplayer(self):
        config = self._multiplayer_config()
        nickname = config.get('multiplayer', 'nickname') if config else ''
        url = config.get('multiplayer', 'server_url') if config else ''
        self._mp_nickname = nickname.strip()
        if not url.strip():
            self._animate_multiplayer_page(self._show_server_setup)
            return
        self._mp_client = MultiplayerClient(url)
        def got_profile(data):
            self._mp_country = data.get('country', 'ZZ')
            if config:
                config.set('multiplayer', 'country', self._mp_country)
                config.write()
            page = self._show_multiplayer_lobby if nickname.strip() else self._show_multiplayer_profile
            self._animate_multiplayer_page(page)
        self._mp_async(self._mp_client.profile, got_profile)

    def _mp_async(self, operation, success=None, failure=None):
        future = MP_POOL.submit(operation)
        def finished(result):
            try:
                value = result.result()
                if success:
                    Clock.schedule_once(lambda _dt: success(value), 0)
            except Exception as error:
                callback = failure or (lambda _dt, err=error: self._show_toast(str(err)[:110]))
                Clock.schedule_once(callback, 0)
        future.add_done_callback(finished)

    def _animate_multiplayer_page(self, builder):
        Animation.cancel_all(self.main_menu_card, 'opacity')
        def switch(*_):
            builder()
            self.main_menu_card.opacity = 0
            Animation(opacity=1, duration=.20, t='out_quad').start(self.main_menu_card)
        fade = Animation(opacity=.12, duration=.12, t='out_quad')
        fade.bind(on_complete=switch)
        fade.start(self.main_menu_card)

    def _show_server_setup(self):
        self._populate_main_menu('multiplayer_server')
        self._main_menu_title.text = 'Connect to server'
        self._main_menu_subtitle.text = 'HTTPS online · HTTP on your local Wi-Fi'
        form = self._mp_centered_form(.88)
        config = self._multiplayer_config()
        url = TextInput(text=config.get('multiplayer', 'server_url') if config else '',
                        hint_text='https://… or http://192.168.1.10:5000', multiline=False,
                        size_hint_y=None, height=dp(54), padding=(dp(14), dp(14)),
                        foreground_color=self.text_color,
                        background_color=((.12,.12,.11,1) if self.dark_mode else (.93,.92,.89,1)))
        form.add_widget(self._mp_label(
            'PythonAnywhere uses HTTPS. Local Flask uses HTTP and your PC’s Wi-Fi IP.',
            dp(48), '16sp'))
        form.add_widget(url)
        form.add_widget(self._mp_button('Connect', lambda: self._connect_multiplayer_server(url.text), True))
        form.add_widget(self._mp_button('Back', self._show_play_menu))
        self._resize_main_menu_card()

    def _connect_multiplayer_server(self, url):
        url = url.strip().rstrip('/')
        if not self._is_allowed_multiplayer_url(url):
            if url.lower().startswith('http://'):
                self._show_toast('Local HTTP needs a private IP, e.g. http://192.168.0.104:5000')
            else:
                self._show_toast('Use HTTPS online or http://<private-ip>:5000 locally')
            return
        config = self._multiplayer_config()
        if config:
            config.set('multiplayer', 'server_url', url)
            config.write()
        self._mp_client = MultiplayerClient(url)
        def connected(profile):
            self._mp_country = profile.get('country', 'ZZ')
            if config:
                config.set('multiplayer', 'country', self._mp_country)
                config.write()
            page = self._show_multiplayer_profile if not self._mp_nickname else self._show_multiplayer_lobby
            self._animate_multiplayer_page(page)
        self._mp_async(self._mp_client.profile, connected)

    @staticmethod
    def _is_allowed_multiplayer_url(url):
        try:
            parsed = urlsplit(url)
            if not parsed.hostname or parsed.username or parsed.password:
                return False
            if parsed.scheme == 'https':
                return True
            if parsed.scheme != 'http':
                return False
            hostname = parsed.hostname.lower().rstrip('.')
            if hostname == 'localhost':
                return True
            address = ipaddress.ip_address(hostname)
            return address.is_private or address.is_loopback or address.is_link_local
        except ValueError:
            return False

    def _show_multiplayer_profile(self):
        self._populate_main_menu('multiplayer_profile')
        self._main_menu_title.text = 'Player profile'
        self._main_menu_subtitle.text = 'Your country is detected automatically from your IP'
        form = self._mp_centered_form(.80)
        config = self._multiplayer_config()
        saved_name = config.get('multiplayer', 'nickname') if config else ''
        nickname = TextInput(text=saved_name, hint_text='Nickname', multiline=False,
                             size_hint_y=None, height=dp(54), padding=(dp(14), dp(14)),
                             foreground_color=self.text_color,
                             background_color=((.12,.12,.11,1) if self.dark_mode else (.93,.92,.89,1)))
        country = getattr(self, '_mp_country', 'ZZ')
        names = {'UA':'Ukraine','US':'United States','GB':'United Kingdom','PL':'Poland',
                 'DE':'Germany','FR':'France','CA':'Canada','JP':'Japan'}
        identity = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(36), spacing=dp(10))
        identity.add_widget(CountryFlag(country=country, size_hint=(None,None), size=(dp(40),dp(26))))
        country_name = names.get(country, 'Location unavailable' if country == 'ZZ' else country)
        identity.add_widget(self._mp_label(f"{country_name} · detected automatically", dp(36)))
        form.add_widget(self._mp_label('Nickname', dp(32), '16sp'))
        form.add_widget(nickname)
        form.add_widget(self._mp_label('Country', dp(32), '16sp'))
        form.add_widget(identity)
        def save_profile():
            name = nickname.text.strip()[:20]
            if not name:
                nickname.hint_text = 'Enter a nickname to continue'
                return
            if config:
                config.set('multiplayer', 'nickname', name)
                config.set('multiplayer', 'country', country)
                config.write()
            self._mp_nickname = name
            self._animate_multiplayer_page(self._show_multiplayer_lobby)
        form.add_widget(self._mp_button('Continue', save_profile, True))
        form.add_widget(self._mp_button('Back', self._show_play_menu))
        self._resize_main_menu_card()

    def _profile_identity(self):
        config = self._multiplayer_config()
        name = config.get('multiplayer', 'nickname') if config else 'Player'
        country = getattr(self, '_mp_country', config.get('multiplayer', 'country') if config else 'ZZ')
        return name or 'Player', country

    def _show_multiplayer_lobby(self):
        self._populate_main_menu('multiplayer_lobby')
        self._main_menu_title.text = 'Multiplayer'
        name, country = self._profile_identity()
        self._main_menu_subtitle.text = 'Find a room or invite a friend'
        identity = BoxLayout(orientation='horizontal', size_hint=(None, None),
                             width=dp(240), height=dp(36), spacing=dp(10),
                             pos_hint={'center_x': .5})
        identity.add_widget(CountryFlag(country=country, size_hint=(None,None), size=(dp(36),dp(23))))
        identity.add_widget(self._mp_label(name, dp(36), '16sp'))
        self.main_menu_card.add_widget(identity)

        landscape = self.width > self.height * 1.08
        self._mp_lobby_landscape = landscape
        content = BoxLayout(orientation='horizontal' if landscape else 'vertical',
                            size_hint_y=1, spacing=dp(16))
        rooms_panel = BoxLayout(orientation='vertical', spacing=dp(8),
                                size_hint_x=.64 if landscape else 1,
                                size_hint_y=1)
        rooms_heading = BoxLayout(orientation='horizontal', size_hint_y=None,
                                  height=dp(42), spacing=dp(8))
        rooms_heading.add_widget(self._mp_label('OPEN ROOMS  ·  TAP TO JOIN', dp(42), '16sp'))
        refresh_button = self._mp_button('Refresh', self._load_public_rooms)
        refresh_button.size_hint_x = None
        refresh_button.width = dp(96)
        refresh_button.height = dp(38)
        rooms_heading.add_widget(refresh_button)
        rooms_panel.add_widget(rooms_heading)
        self._mp_rooms_frame = RoundCard(orientation='vertical', size_hint=(1, 1),
                                         padding=dp(9), spacing=dp(6),
                                         fill_color=(.12,.12,.11,1) if self.dark_mode else (.93,.92,.89,1),
                                         corner_radius=dp(20))
        self._mp_rooms_scroll = ScrollView(do_scroll_x=False, bar_width=dp(4),
                                           scroll_type=['bars', 'content'])
        self._mp_rooms_box = BoxLayout(orientation='vertical', size_hint_y=None,
                                       spacing=dp(8), padding=(0, dp(3)))
        self._mp_rooms_box.bind(minimum_height=self._mp_rooms_box.setter('height'))
        self._mp_rooms_scroll.add_widget(self._mp_rooms_box)
        self._mp_rooms_frame.add_widget(self._mp_rooms_scroll)
        self._mp_rooms_box.add_widget(self._mp_label('Loading rooms…', dp(42)))
        rooms_panel.add_widget(self._mp_rooms_frame)
        content.add_widget(rooms_panel)

        actions = BoxLayout(orientation='vertical', spacing=dp(10),
                            size_hint_x=.36 if landscape else 1,
                            size_hint_y=1 if landscape else None)
        if landscape:
            actions.add_widget(self._mp_label('PLAY WITH FRIENDS', dp(34), '16sp'))
        create_button = self._mp_button(
            'Create a room', lambda: self._animate_multiplayer_page(self._show_create_room), True)
        create_button.height = dp(54)
        actions.add_widget(create_button)
        if landscape:
            actions.add_widget(self._mp_label('JOIN WITH A ROOM CODE', dp(30), '14sp'))
        code = TextInput(text='', hint_text='Room code', multiline=False,
                         size_hint_y=None, height=dp(48), padding=(dp(14), dp(12)),
                         foreground_color=self.text_color,
                         background_color=((.12, .12, .11, 1) if self.dark_mode else (.93, .92, .89, 1)))
        join_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(48), spacing=dp(8))
        join_row.add_widget(code)
        join_button = self._mp_button('Join', lambda: self._join_room_code(code.text))
        join_button.size_hint_x = None
        join_button.width = dp(90)
        join_row.add_widget(join_button)
        actions.add_widget(join_row)
        tools_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(46), spacing=dp(8))
        edit_button = self._mp_button('Edit nickname', self._show_multiplayer_profile_edit)
        server_button = self._mp_button('Server settings', lambda: self._animate_multiplayer_page(self._show_server_setup))
        edit_button.height = server_button.height = dp(46)
        tools_row.add_widget(edit_button)
        tools_row.add_widget(server_button)
        if landscape:
            actions.add_widget(self._mp_label('Room list refreshes automatically every 12 seconds.', dp(52)))
            actions.add_widget(BoxLayout(size_hint_y=1))
        else:
            actions.height = dp(54 + 48 + 46 + 46 + 3 * 10)
        actions.add_widget(tools_row)
        back_button = self._mp_button('Back to menu', self._show_play_menu)
        back_button.height = dp(46)
        actions.add_widget(back_button)
        content.add_widget(actions)
        self.main_menu_card.add_widget(content)
        self._resize_main_menu_card()
        self._load_public_rooms()
        previous_refresh = getattr(self, '_mp_rooms_refresh_event', None)
        if previous_refresh:
            previous_refresh.cancel()
        self._mp_rooms_refresh_event = Clock.schedule_interval(
            lambda _dt: self._load_public_rooms()
            if getattr(self, '_main_menu_page', '') == 'multiplayer_lobby' else False, 12)

    def _show_multiplayer_profile_edit(self):
        self._animate_multiplayer_page(self._show_multiplayer_profile)

    def _show_create_room(self):
        self._populate_main_menu('multiplayer_create')
        self._main_menu_title.text = 'Create a room'
        self._main_menu_subtitle.text = 'Set up a match for another player'
        form = self._mp_centered_form(.88)
        form.add_widget(self._mp_label('Room visibility', dp(32), '16sp'))
        visibility = self._mp_button('Visibility: Public', lambda: None)
        visibility.size_hint_y = None
        visibility.height = dp(54)
        visibility._private = False
        def toggle_visibility(*_):
            visibility._private = not visibility._private
            visibility.text = 'Visibility: Private' if visibility._private else 'Visibility: Public'
        visibility.bind(on_release=toggle_visibility)
        form.add_widget(visibility)
        form.add_widget(self._mp_label('Short room description', dp(32), '16sp'))
        description = TextInput(text='', hint_text='Friendly game, no timer…', multiline=False,
                                size_hint_y=None, height=dp(54), padding=(dp(14), dp(14)),
                                foreground_color=self.text_color,
                                background_color=((.12, .12, .11, 1) if self.dark_mode else (.93, .92, .89, 1)))
        form.add_widget(description)
        form.add_widget(self._mp_label('Invite friends by code, or publish this room for others.', dp(48), '15sp'))
        form.add_widget(self._mp_button('Create room', lambda: self._create_online_room(visibility._private, description.text), True))
        form.add_widget(self._mp_button('Back', lambda: self._animate_multiplayer_page(self._show_multiplayer_lobby)))
        self._resize_main_menu_card()

    def _create_online_room(self, private, description):
        name, _ = self._profile_identity()
        self._mp_async(lambda: self._mp_client.create_room(name, private, description),
                       self._room_created)

    def _room_created(self, room):
        self._mp_room = room
        self._mp_room_finished = False
        self._mp_room['opponent'] = ''
        self._mp_seq = room.get('seq', 0)
        self._animate_multiplayer_page(self._show_room_waiting)
        self._begin_room_polling()

    def _join_room_code(self, code):
        name, _ = self._profile_identity()
        self._mp_async(lambda: self._mp_client.join_room(code, name), self._joined_room)

    def _joined_room(self, room):
        self._mp_room = room
        self._mp_room_finished = False
        self._mp_seq = room.get('seq', 0)
        self._animate_multiplayer_page(self._show_guest_waiting)
        self._begin_room_polling()

    def _show_guest_waiting(self):
        self._populate_main_menu('multiplayer_joined')
        self._main_menu_title.text = 'Room joined'
        self._main_menu_subtitle.text = 'Waiting for the owner to start'
        form = self._mp_centered_form(.82)
        host = self._mp_room.get('opponent', 'Host')
        country = self._mp_room.get('opponent_country', 'ZZ')
        host_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(34), spacing=dp(8))
        host_row.add_widget(CountryFlag(country=country, size_hint=(None,None), size=(dp(36),dp(23))))
        host_row.add_widget(self._mp_label(host, dp(34)))
        form.add_widget(host_row)
        form.add_widget(self._mp_label('ROOM CODE', dp(32), '16sp'))
        form.add_widget(self._mp_label(self._mp_room['code'], dp(72), '36sp'))
        self._mp_guest_wait_status = self._mp_label('The owner will start the match soon.', dp(50))
        form.add_widget(self._mp_guest_wait_status)
        form.add_widget(self._mp_button('Leave room', self._leave_multiplayer_room))
        self._resize_main_menu_card()

    def _show_room_waiting(self):
        self._populate_main_menu('multiplayer_waiting')
        self._main_menu_title.text = 'Waiting for opponent'
        self._main_menu_subtitle.text = 'Private room' if self._mp_room.get('private') else 'Public room'
        form = self._mp_centered_form(.82)
        name, country = self._profile_identity()
        identity = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(30), spacing=dp(8))
        identity.add_widget(CountryFlag(country=country, size_hint=(None,None), size=(dp(36),dp(23))))
        identity.add_widget(self._mp_label(name, dp(30)))
        form.add_widget(identity)
        form.add_widget(self._mp_label('ROOM CODE', dp(32), '16sp'))
        form.add_widget(self._mp_label(self._mp_room['code'], dp(72), '36sp'))
        form.add_widget(self._mp_label(self._mp_room.get('description', '') or 'No description', dp(42), '16sp'))
        form.add_widget(self._mp_label('Room is hosted on the server. Share its code with your opponent.', dp(54), '15sp'))
        self._mp_wait_status = self._mp_label('Waiting for an opponent to join…', dp(42))
        form.add_widget(self._mp_wait_status)
        self._mp_start_button = self._mp_button('Waiting for opponent', self._start_room_on_server, True)
        self._mp_start_button.disabled = True
        self._mp_start_button.fill_color = self.surface_color
        self._mp_start_button.disabled_color = self.text_color
        form.add_widget(self._mp_start_button)
        form.add_widget(self._mp_button('Cancel room', self._leave_multiplayer_room))
        self._resize_main_menu_card()

    def _load_public_rooms(self):
        self._mp_async(self._mp_client.rooms, self._render_public_rooms)

    def _render_public_rooms(self, rooms):
        if getattr(self, '_main_menu_page', '') != 'multiplayer_lobby' or not hasattr(self, '_mp_rooms_box'):
            return
        self._mp_rooms_box.clear_widgets()
        shown = rooms[:30]
        if not shown:
            empty = self._mp_label('No open rooms yet', dp(38))
            empty.size_hint_x = 1
            self._mp_rooms_box.add_widget(empty)
        for room in shown:
            row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(66), spacing=dp(10))
            row.add_widget(CountryFlag(country=room.get('country', 'ZZ'), size_hint=(None,None), size=(dp(38),dp(25))))
            description = room.get('description') or 'Chess match'
            button = RoomEntryButton(text=f"{room['host']}\n{description}  ·  OPEN",
                                     size_hint=(1, 1), corner_radius=dp(14),
                                     font_size='15sp',
                                     fill_color=(.24,.24,.23,1) if self.dark_mode else (.87,.86,.83,1),
                                     text_color=self.text_color, halign='left', valign='middle',
                                     padding=(dp(12), dp(3)))
            button.bind(size=lambda widget, size: setattr(
                widget, 'text_size', (max(0, size[0] - dp(24)), size[1] - dp(6))))
            button.bind(on_release=lambda *_args, code=room['code']: self._join_room_code(code))
            row.add_widget(button)
            self._mp_rooms_box.add_widget(row)
        self._resize_main_menu_card()

    def _begin_room_polling(self):
        if self._mp_poll_event:
            self._mp_poll_event.cancel()
        self._mp_poll_event = Clock.schedule_interval(lambda _dt: self._poll_multiplayer_state(), 1.0)
        self._poll_multiplayer_state()

    def _poll_multiplayer_state(self):
        room = getattr(self, '_mp_room', None)
        if (not room or not room.get('token') or getattr(self, '_mp_poll_inflight', False)
                or getattr(self, '_mp_move_pending', False)):
            return
        self._mp_poll_inflight = True
        self._mp_async(lambda: self._mp_client.state(room['code'], room['token'], self._mp_seq),
                       self._poll_completed, lambda _dt: self._poll_failed())

    def _poll_completed(self, state):
        self._mp_poll_inflight = False
        self._mp_poll_failures = 0
        self._apply_multiplayer_state(state)

    def _poll_failed(self, _dt=0):
        self._mp_poll_inflight = False
        self._mp_poll_failures = getattr(self, '_mp_poll_failures', 0) + 1
        if self._mp_poll_failures == 3:
            self._show_toast('Connection interrupted; retrying…')

    def _apply_multiplayer_state(self, state):
        if not getattr(self, '_mp_room', None):
            return
        # A state request can have started just before our move POST. Do not
        # let its stale FEN roll the board back while that move is in flight.
        if getattr(self, '_mp_move_pending', False):
            return
        self._mp_seq = max(self._mp_seq, state.get('seq', 0))
        own_color = self._mp_room.get('color')
        for event in state.get('events', []):
            if event['sender'] == own_color:
                continue
            if event['kind'] == 'move' and self._multiplayer_active:
                try:
                    move = chess.Move.from_uci(event['payload']['uci'])
                    if move in self.engine.board.legal_moves:
                        self.engine.play(move)
                        self._play_move_sound()
                        self.board_widget.animate_move(move)
                        self.refresh()
                except (ValueError, KeyError):
                    pass
            elif event['kind'] == 'left' and self._multiplayer_active:
                self._game_started = False
                self._multiplayer_active = False
                self._mp_room_finished = False
                if self._mp_poll_event:
                    self._mp_poll_event.cancel()
                    self._mp_poll_event = None
                self.result_title = 'Opponent disconnected'
                self.result_detail = 'The room is waiting for another player'
                self.result_visible = True
            elif event['kind'] == 'resigned' and self._multiplayer_active:
                self._game_started = False
                if self._mp_poll_event:
                    self._mp_poll_event.cancel()
                    self._mp_poll_event = None
                self._multiplayer_active = False
                self._mp_room_finished = True
                self.result_title = 'Opponent resigned'
                self.result_detail = 'You win'
                self.result_visible = True
        if self._multiplayer_active and state.get('fen'):
            if self.engine.board.fen() != state['fen']:
                self.engine.board.set_fen(state['fen'])
                self.board_widget.selected = []
                self.board_widget.targets = []
                self.refresh()
        if state.get('status') == 'ready' and self._mp_room.get('color') == 'white':
            self._mp_room['opponent'] = state.get('opponent') or 'Opponent'
            self._mp_room['opponent_country'] = state.get('opponent_country') or 'ZZ'
            if getattr(self, '_mp_start_button', None) is not None:
                self._mp_wait_status.text = f"{self._mp_room['opponent']} joined. Start when you're ready."
                self._mp_start_button.text = 'Start game'
                self._mp_start_button.fill_color = self.accent_color
                self._mp_start_button.text_color = self._accent_text_color(self.accent_color)
                self._mp_start_button.disabled = False
                self._mp_start_button.opacity = 1
        if state.get('status') == 'playing' and not self._multiplayer_active:
            color = chess.WHITE if self._mp_room.get('color') == 'white' else chess.BLACK
            self._start_multiplayer_game(color, state.get('opponent') or 'Opponent',
                                         state.get('opponent_country') or 'ZZ')

    def _start_room_on_server(self):
        room = getattr(self, '_mp_room', None)
        button = getattr(self, '_mp_start_button', None)
        if not room or room.get('color') != 'white' or not button or button.disabled:
            return
        button.disabled = True
        button.text = 'Starting…'
        self._mp_async(lambda: self._mp_client.start_room(room['code'], room['token']),
                       lambda result: self._start_multiplayer_game(
                           chess.WHITE, result.get('opponent', room.get('opponent', 'Opponent')),
                           result.get('opponent_country', room.get('opponent_country', 'ZZ'))),
                       lambda _dt: self._restore_start_button())

    def _restore_start_button(self):
        button = getattr(self, '_mp_start_button', None)
        if button:
            button.disabled = False
            button.text = 'Start game'

    def _start_multiplayer_game(self, color, opponent, country):
        self._multiplayer_active = True
        self._mp_move_pending = False
        self._opponent_identity.opacity = 1
        self._opponent_flag.country = country
        self._opponent_name.text = opponent
        self._position_opponent_identity()
        self._cancel_bot_thinking()
        self._game_started = True
        self.player_color = color
        self.engine = ChessEngine()
        self.selection = None
        self.board_widget.flipped = color == chess.BLACK
        self.board_widget.selected = []
        self.board_widget.targets = []
        self._in_main_menu = False
        self.result_visible = False
        self.main_menu.disabled = True
        self.main_menu.opacity = 0
        self.ids.board_container.disabled = False
        self.ids.board_container.opacity = 1
        self.ids.menu_button.disabled = False
        self.ids.menu_button.opacity = 1
        self.ids.status_label.pos_hint = {'x': .04, 'top': .92}
        self.ids.status_label.opacity = 1
        self.started_at = time.monotonic()
        self.time_control = 0
        self.remaining_time = {chess.WHITE: 0.0, chess.BLACK: 0.0}
        self.refresh()
        self._begin_room_polling()

    def _send_multiplayer_move(self, move):
        room = self._mp_room
        if not room or getattr(self, '_mp_move_pending', False):
            return
        self._mp_move_pending = True
        self.board_widget.disabled = True
        self.status_text = 'SENDING MOVE…'
        uci = move.uci()

        def accepted(result):
            if self._mp_room is not room or not self._multiplayer_active:
                return
            try:
                if move not in self.engine.board.legal_moves:
                    raise ValueError('Position changed before move confirmation')
                self.engine.play(move)
                if result.get('fen') and self.engine.board.fen() != result['fen']:
                    self.engine.board.set_fen(result['fen'])
                self._mp_seq = max(self._mp_seq, int(result.get('seq', 0)))
                self._play_move_sound()
                self.board_widget.animate_move(move)
                self.refresh()
            except (KeyError, TypeError, ValueError):
                self._reload_multiplayer_position()
                return
            finally:
                self._mp_move_pending = False
                self.board_widget.disabled = False

        def rejected(_dt):
            self._mp_move_pending = False
            self.board_widget.disabled = False
            self._reload_multiplayer_position()

        self._mp_async(lambda: self._mp_client.send_move(room['code'], room['token'], uci),
                       accepted, rejected)

    def _reload_multiplayer_position(self):
        room = self._mp_room
        if not room:
            return
        def sync(state):
            try:
                self.engine.board.set_fen(state['fen'])
                self._mp_seq = max(self._mp_seq, int(state.get('seq', 0)))
                self.selection = None
                self.board_widget.selected = []
                self.board_widget.targets = []
                self.board_widget.disabled = False
                self.refresh()
                self._show_toast('Move not accepted; board synchronized')
            except (KeyError, ValueError):
                self.board_widget.disabled = False
                self._show_toast('Could not resynchronize the game')
        self._mp_async(lambda: self._mp_client.state(room['code'], room['token'], 0), sync)

    def _leave_multiplayer_room(self):
        room = getattr(self, '_mp_room', None)
        if self._mp_poll_event:
            self._mp_poll_event.cancel()
            self._mp_poll_event = None
        self._multiplayer_active = False
        self._mp_move_pending = False
        self.board_widget.disabled = False
        self._opponent_identity.opacity = 0
        self._mp_room_finished = True
        self._mp_room = None
        if room:
            self._mp_async(lambda: self._mp_client.leave_room(room['code'], room['token']),
                           lambda _result: self._animate_multiplayer_page(self._show_multiplayer_lobby))
        else:
            self._animate_multiplayer_page(self._show_multiplayer_lobby)

    def _close_multiplayer_session(self):
        room = getattr(self, '_mp_room', None)
        if self._mp_poll_event:
            self._mp_poll_event.cancel()
            self._mp_poll_event = None
        self._multiplayer_active = False
        self._mp_move_pending = False
        self.board_widget.disabled = False
        self._opponent_identity.opacity = 0
        if room and room.get('token') and not getattr(self, '_mp_room_finished', False):
            self._mp_async(lambda: self._mp_client.leave_room(room['code'], room['token']))
        self._mp_room = None

    def _resize_main_menu_card(self):
        if getattr(self, '_main_menu_page', '').startswith('multiplayer'):
            self._fit_main_menu()
            return
        child_heights = sum(widget.height for widget in self.main_menu_card.children)
        child_spacing = self.main_menu_card.spacing * max(0, len(self.main_menu_card.children) - 1)
        self.main_menu_card.height = child_heights + child_spacing + dp(36)
        self._fit_main_menu()

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
        multiplayer = getattr(self, "_multiplayer_active", False)
        menu_items = [("Settings", self._select_settings), ("About", self._select_about)]
        if not multiplayer:
            menu_items.extend((("Save", self._select_save), ("Undo move", self._select_undo)))
        menu_items.append(("Resign", self._select_resign))
        popup_height = dp(52 * len(menu_items))
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
        for text, callback in menu_items:
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

