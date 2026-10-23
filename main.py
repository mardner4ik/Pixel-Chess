import os

# Prefer SDL2's bundled WAV support over GStreamer, which may be installed
# without its optional WAV decoder plugin on Linux desktops.
os.environ["KIVY_AUDIO"] = "sdl2"

from kivy.config import Config

Config.set("graphics", "width", "420")
Config.set("graphics", "height", "860")
Config.set("graphics", "minimum_width", "340")
Config.set("graphics", "minimum_height", "600")
Config.set("graphics", "maxfps", "60")

from kivy.app import App
from kivy.lang import Builder
from kivy.core.window import Window
from kivy.utils import get_color_from_hex
from kivy.core.text import LabelBase

from chess_app.ui.game_screen import GameScreen


class PixelChessApp(App):
    title = "PIXEL CHESS"

    def build_config(self, config):
        config.setdefaults("audio", {"master_volume": "0.60"})

    def build(self):
        font_path = os.path.join(os.path.dirname(__file__), "assets", "fonts", "GoogleSansFlex.ttf")
        if os.path.isfile(font_path):
            LabelBase.register(name="PixelUI", fn_regular=font_path, fn_bold=font_path,
                               fn_italic=font_path, fn_bolditalic=font_path)
        Window.clearcolor = get_color_from_hex("#111111")
        Builder.load_file("chess_app/ui/theme.kv")
        return GameScreen()


if __name__ == "__main__":
    PixelChessApp().run()
