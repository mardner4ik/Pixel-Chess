import unittest

from kivy.uix.scrollview import ScrollView

from chess_app.ui.dialogs import GameDialogsMixin
from chess_app.ui.widgets import PixelButton


class DialogHarness(GameDialogsMixin):
    dark_mode = True
    text_color = (.95, .95, .92, 1)
    muted_color = (.65, .65, .62, 1)
    accent_color = (.52, .34, .78, 1)

    @staticmethod
    def _accent_text_color(_color):
        return (1, 1, 1, 1)

    def _open_dialog_near_top(self, view, card):
        self.opened_view = view
        self.opened_card = card

    def _show_settings(self, *_):
        pass


class SettingsDialogTests(unittest.TestCase):
    def test_setting_options_are_direct_buttons_with_visible_text(self):
        harness = DialogHarness()
        harness._open_setting_choices(
            "Accent color",
            [("system", "Auto"), ("blue", "Blue"), ("green", "Green"),
             ("violet", "Violet"), ("amber", "Amber")],
            "violet",
            lambda _choice: None,
        )
        buttons = [widget for widget in harness.opened_view.walk()
                   if isinstance(widget, PixelButton) and widget.text]
        labels = [button.text for button in buttons]
        self.assertIn("Blue", labels)
        self.assertIn("✓  Violet", labels)
        self.assertIn("Back", labels)
        self.assertFalse(any(isinstance(widget, ScrollView)
                             for widget in harness.opened_view.walk()))


if __name__ == "__main__":
    unittest.main()
