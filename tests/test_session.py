import tempfile
import unittest
from pathlib import Path

import chess

from chess_app.core.engine import ChessEngine
from chess_app.ui.session import GameSessionMixin


class SessionHarness(GameSessionMixin):
    def __init__(self, path):
        self._session_path = Path(path)
        self.engine = ChessEngine()
        self.player_color = chess.WHITE
        self.difficulty = "easy"
        self.time_control = 0
        self.board_palette = "sage"
        self.bot_thinking_delay = True
        self.piece_style = "pixel"
        self.soundtrack_id = "friday_morning"
        self.remaining_time = {chess.WHITE: 0.0, chess.BLACK: 0.0}
        self._game_started = True
        self._saved_session = None


class GameSessionTests(unittest.TestCase):
    def test_save_is_atomic_and_restorable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "saved_game.json"
            original = SessionHarness(path)
            original.engine.play(chess.Move.from_uci("e2e4"))
            self.assertTrue(original._save_game())
            self.assertTrue(path.is_file())
            self.assertFalse(path.with_suffix(".tmp").exists())

            restored = SessionHarness(path)
            restored._restore_saved_game()
            self.assertEqual(restored._saved_session["moves"], ["e2e4"])
            self.assertEqual(restored._saved_session["fen"], original.engine.board.fen())

    def test_invalid_save_is_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "saved_game.json"
            path.write_text("not json", encoding="utf-8")
            session = SessionHarness(path)
            session._restore_saved_game()
            self.assertFalse(path.exists())
            self.assertIsNone(session._saved_session)

    def test_save_is_rejected_without_active_game(self):
        with tempfile.TemporaryDirectory() as directory:
            session = SessionHarness(Path(directory) / "saved_game.json")
            session._game_started = False
            self.assertFalse(session._save_game())


if __name__ == "__main__":
    unittest.main()
