import threading
import unittest

import chess

from chess_app.core.engine import ChessEngine


class ChessEngineTests(unittest.TestCase):
    def test_start_position_has_twenty_legal_moves(self):
        engine = ChessEngine()
        self.assertEqual(len(list(engine.board.legal_moves)), 20)
        moves = engine.legal_moves_from(chess.E2)
        self.assertEqual(len(moves), 2)
        self.assertTrue(all(move.from_square == chess.E2 for move in moves))

    def test_instant_bot_move_is_legal_and_updates_board(self):
        engine = ChessEngine()
        legal_moves = set(engine.board.legal_moves)
        move = engine.bot_move("normal", thinking_time=0)
        self.assertIn(move, legal_moves)
        self.assertEqual(engine.board.peek(), move)

    def test_cancelled_search_does_not_play_a_move(self):
        engine = ChessEngine()
        cancel = threading.Event()
        cancel.set()
        before = engine.board.fen()
        move = engine.bot_move("hard", thinking_time=10, cancel_event=cancel)
        self.assertIsNone(move)
        self.assertEqual(engine.board.fen(), before)


if __name__ == "__main__":
    unittest.main()
