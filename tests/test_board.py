import unittest

from chess_engine.board import START_FEN, Board, move_to_uci, perft

# Reference counts from https://www.chessprogramming.org/Perft_Results
PERFT_CASES = [
    (START_FEN, [20, 400, 8902, 197281]),
    ("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1", [48, 2039, 97862]),
    ("8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1", [14, 191, 2812, 43238]),
    ("r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1", [6, 264, 9467]),
    ("rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8", [44, 1486, 62379]),
    ("r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10", [46, 2079, 89890]),
]


def hash_walk(board, depth):
    """Check the incremental Zobrist hash against a full recompute at every node."""
    assert board.hash == board.compute_hash(), board.fen()
    if depth == 0:
        return
    for m in board.legal_moves():
        board.push(m)
        hash_walk(board, depth - 1)
        board.pop()


class PerftTest(unittest.TestCase):
    def test_perft(self):
        for fen, counts in PERFT_CASES:
            board = Board(fen)
            for depth, expected in enumerate(counts, 1):
                with self.subTest(fen=fen, depth=depth):
                    self.assertEqual(perft(board, depth), expected)
            self.assertEqual(board.fen(), Board(fen).fen(), "make/unmake left the board changed")


class BoardTest(unittest.TestCase):
    def test_fen_round_trip(self):
        for fen, _ in PERFT_CASES:
            self.assertEqual(Board(fen).fen(), fen)

    def test_incremental_hash(self):
        for fen, _ in PERFT_CASES:
            hash_walk(Board(fen), 3)

    def test_en_passant_and_promotion_moves(self):
        board = Board("4k3/1P6/8/3pP3/8/8/8/4K3 w - d6 0 1")
        moves = {move_to_uci(m) for m in board.legal_moves()}
        self.assertIn("e5d6", moves)
        self.assertTrue({"b7b8q", "b7b8r", "b7b8b", "b7b8n"} <= moves)

    def test_cannot_castle_through_check(self):
        board = Board("4k3/8/8/8/8/8/5r2/R3K2R w KQ - 0 1")
        moves = {move_to_uci(m) for m in board.legal_moves()}
        self.assertNotIn("e1g1", moves)
        self.assertIn("e1c1", moves)

    def test_outcomes(self):
        self.assertEqual(Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1").outcome(), "1/2-1/2 stalemate")
        self.assertEqual(Board("R5k1/5ppp/8/8/8/8/8/6K1 b - - 0 1").outcome(), "1-0 checkmate")
        self.assertEqual(Board("8/8/4k3/8/8/3NK3/8/8 w - - 0 1").outcome(),
                         "1/2-1/2 insufficient material")

    def test_threefold_repetition(self):
        board = Board()
        for text in ["g1f3", "g8f6", "f3g1", "f6g8"] * 2:
            board.push(board.parse_uci(text))
        self.assertEqual(board.outcome(), "1/2-1/2 threefold repetition")


if __name__ == "__main__":
    unittest.main()
