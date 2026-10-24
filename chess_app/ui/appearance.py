"""Theme, accent, and audio behavior for the game screen."""

from kivy.animation import Animation
from kivy.app import App
from kivy.core.window import Window

from chess_app.paths import ASSETS_DIR, asset_path
from chess_app.ui.board import ACCENT_PALETTES
from chess_app.ui.soundtracks import SOUNDTRACKS, SOUNDTRACKS_BY_ID
from chess_app.ui.system_theme import get_system_accent_color, is_dark_mode
from chess_app.ui.widgets import AccentChoiceButton, PixelButton


class AppearanceMixin:
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

            if self._background_music is not None:
                self._background_music.stop()
            if self._move_sound is not None:
                self._move_sound.stop()
            track = SOUNDTRACKS_BY_ID.get(self.soundtrack_id, SOUNDTRACKS[0])
            filename = track["file"]
            bundled_source = ASSETS_DIR / filename
            source = str(bundled_source) if bundled_source.is_file() else resource_find(
                f"assets/{filename}")
            if source is None:
                Logger.warning(f"PixelChess: assets/{filename} was not found")
                return
            sound = SoundLoader.load(source)
            if sound is None:
                Logger.warning(f"PixelChess: no audio provider could load assets/{filename}")
                return
            self._background_music = sound
            sound.loop = True
            sound.volume = self.master_volume * .65
            sound.play()
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
        if self._move_sound is None:
            try:
                from kivy.core.audio import SoundLoader

                move_path = ASSETS_DIR / "move.wav"
                self._move_sound = SoundLoader.load(str(move_path)) if move_path.is_file() else None
                if self._move_sound is not None:
                    self._move_sound.volume = self.master_volume * .85
            except Exception:
                self._move_sound = None
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
            self._main_menu_icon.source = str(asset_path(
                "pieces", "white-king.png" if dark else "black-king.png"))
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
                    widget._github_icon.source = str(asset_path(
                        "github-mark-light.png" if dark else "github-mark.png"))
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

