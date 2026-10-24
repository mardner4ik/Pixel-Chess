from __future__ import annotations

import random
import time

import chess
import chess.polyglot


class ChessEngine:
    """Small game facade keeping UI code independent from python-chess."""

    def __init__(self) -> None:
        self.board = chess.Board()

    def legal_moves_from(self, square: chess.Square) -> list[chess.Move]:
        return [move for move in self.board.legal_moves if move.from_square == square]

    def play(self, move: chess.Move) -> None:
        if move not in self.board.legal_moves:
            raise ValueError("Illegal move")
        self.board.push(move)

    def bot_move(self, difficulty: str = "normal") -> chess.Move | None:
        moves = list(self.board.legal_moves)
        if not moves:
            return None
        # Iterative deepening gives a legal answer quickly, while a variable
        # budget makes the opponent feel less mechanical on a phone.
        complexity = min(1.0, len(moves) / 36)
        budgets = {"easy": (.10, .24), "normal": (.38, .90), "hard": (.85, 1.50)}
        low, high = budgets.get(difficulty, budgets["normal"])
        budget = random.uniform(low, high) + complexity * (high - low)
        if self.board.is_check() or len(moves) <= 4:
            budget += random.uniform(.12, .30)
        self._deadline = time.monotonic() + budget
        self._nodes = 0
        self._table = {}
        move = self._ordered(moves)[0]
        self._root_move = move
        for depth in range(1, 16):
            try:
                _, candidate = self._root_search(depth, moves)
                if candidate is not None:
                    move = candidate
                    self._root_move = move
            except SearchTimeout:
                break
        self.board.push(move)
        return move

    def _ordered(self, moves):
        values = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 335,
                  chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 20000}
        def score(move):
            victim = self.board.piece_at(move.to_square)
            attacker = self.board.piece_at(move.from_square)
            capture = values.get(victim.piece_type, 100) * 10 - values.get(attacker.piece_type, 0) if victim else 0
            promotion = values.get(move.promotion, 0) if move.promotion else 0
            return capture + promotion + (80 if self.board.gives_check(move) else 0)
        return sorted(moves, key=score, reverse=True)

    def _check_time(self):
        self._nodes += 1
        if (self._nodes & 255) == 0:
            # Search runs in a worker thread, but CPython still shares the GIL.
            # Briefly yield it so touch handling and rendering stay responsive.
            time.sleep(0)
            if time.monotonic() >= self._deadline:
                raise SearchTimeout

    def _root_search(self, depth, moves):
        alpha, beta = -100_000, 100_000
        best_score, best_move = -float("inf"), None
        ordered = self._ordered(moves)
        if self._root_move in ordered:
            ordered.remove(self._root_move)
            ordered.insert(0, self._root_move)
        for move in ordered:
            self._check_time()
            self.board.push(move)
            try:
                score = -self._search(depth - 1, -beta, -alpha, 1)
            finally:
                self.board.pop()
            if score > best_score:
                best_score, best_move = score, move
            alpha = max(alpha, score)
        return best_score, best_move

    def _search(self, depth, alpha, beta, ply):
        self._check_time()
        if self.board.is_checkmate():
            return -100000 + ply
        if self.board.is_stalemate() or self.board.is_insufficient_material() or self.board.can_claim_draw():
            return 0
        if depth <= 0:
            return self._quiescence(alpha, beta, ply)
        key = (chess.polyglot.zobrist_hash(self.board), self.board.halfmove_clock)
        original_alpha = alpha
        original_beta = beta
        cached = self._table.get(key)
        preferred = None
        if cached:
            cached_depth, cached_score, bound, preferred = cached
            if cached_depth >= depth:
                if bound == "exact":
                    return cached_score
                if bound == "lower":
                    alpha = max(alpha, cached_score)
                elif bound == "upper":
                    beta = min(beta, cached_score)
                if alpha >= beta:
                    return cached_score
        best = -float("inf")
        best_move = None
        moves = self._ordered(list(self.board.legal_moves))
        if preferred in moves:
            moves.remove(preferred)
            moves.insert(0, preferred)
        for move in moves:
            self.board.push(move)
            try:
                value = -self._search(depth - 1, -beta, -alpha, ply + 1)
            finally:
                self.board.pop()
            if value > best:
                best, best_move = value, move
            alpha = max(alpha, value)
            if alpha >= beta:
                break
        bound = "upper" if best <= original_alpha else "lower" if best >= original_beta else "exact"
        if len(self._table) > 150_000:
            self._table.clear()
        self._table[key] = (depth, best, bound, best_move)
        return best

    def _quiescence(self, alpha, beta, ply):
        if ply > 12:
            return self._evaluate()
        in_check = self.board.is_check()
        if in_check:
            best = -float("inf")
            candidates = list(self.board.legal_moves)
        else:
            best = stand_pat = self._evaluate()
            if stand_pat >= beta:
                return beta
            alpha = max(alpha, stand_pat)
            # Search forcing captures and promotions past the nominal horizon.
            candidates = list(self.board.generate_legal_captures()) + [m for m in self.board.legal_moves if m.promotion]
        for move in self._ordered(candidates):
            self._check_time()
            self.board.push(move)
            try:
                score = -self._quiescence(-beta, -alpha, ply + 1)
            finally:
                self.board.pop()
            if score >= beta:
                return beta
            alpha = max(alpha, score)
            best = max(best, score)
        return max(best, alpha)

    def _evaluate(self):
        values = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 335,
                  chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 0}
        score = 0
        phase = 0
        pawn_files = {
            color: [0] * 8 for color in (chess.WHITE, chess.BLACK)
        }
        pawns = []
        piece_map = self.board.piece_map()
        for square, piece in piece_map.items():
            if piece.piece_type == chess.PAWN:
                pawn_files[piece.color][chess.square_file(square)] += 1
                pawns.append((square, piece))
        for square, piece in piece_map.items():
            relative_rank = chess.square_rank(square) if piece.color else 7 - chess.square_rank(square)
            center = 7 - (abs(3.5 - chess.square_file(square)) + abs(3.5 - chess.square_rank(square)))
            positional = int(center * (7 if piece.piece_type in (chess.KNIGHT, chess.BISHOP) else 3))
            if piece.piece_type == chess.PAWN:
                positional += relative_rank * 9
                file_index = chess.square_file(square)
                file_count = pawn_files[piece.color][file_index]
                if file_count > 1:
                    positional -= 12
                if not any(pawn_files[piece.color][f] for f in (file_index - 1, file_index + 1) if 0 <= f < 8):
                    positional -= 10
            phase += {chess.KNIGHT: 1, chess.BISHOP: 1, chess.ROOK: 2, chess.QUEEN: 4}.get(piece.piece_type, 0)
            value = values[piece.piece_type] + positional
            score += value if piece.color == self.board.turn else -value
        # A full legal-move generation at every leaf was a major mobile CPU
        # cost. The existing piece-square terms provide positional guidance.
        # Encourage castling rights and king safety while major pieces remain.
        if phase > 8:
            rights = bool(self.board.castling_rights & chess.BB_ALL)
            if rights:
                score += 24
        return score

    def status(self) -> tuple[str, bool]:
        if self.board.is_checkmate():
            winner = "WHITE" if self.board.turn == chess.BLACK else "BLACK"
            return f"CHECKMATE • {winner} WINS", True
        if self.board.is_stalemate():
            return "STALEMATE • DRAW", True
        if self.board.is_insufficient_material() or self.board.can_claim_draw():
            return "DRAW", True
        if self.board.is_check():
            return "CHECK", False
        return ("OPPONENT THINKING" if self.board.turn == chess.BLACK else "YOUR TURN"), False

    def move_log(self) -> list[str]:
        board = chess.Board()
        san = []
        for move in self.board.move_stack:
            san.append(board.san(move))
            board.push(move)
        return [f"{i // 2 + 1:02}  {san[i] if i < len(san) else '—'}   {san[i + 1] if i + 1 < len(san) else ''}" for i in range(0, len(san), 2)]


class SearchTimeout(Exception):
    """Raised internally when the current iterative-deepening budget expires."""

