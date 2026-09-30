import io
import time
import unittest

from chess_engine.board import Board, move_to_uci
from chess_engine.search import MATE_BOUND, Searcher
from chess_engine.uci import UCI


def best(fen, **limits):
    board = Board(fen)
    move, score = Searcher().search(board, limits or {"depth": 5})
    return move_to_uci(move), score


class SearchTest(unittest.TestCase):
    def test_mate_in_one(self):
        move, score = best("6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1")
        self.assertEqual(move, "a1a8")
        self.assertGreater(score, MATE_BOUND)

    def test_scholars_mate(self):
        move, _ = best("r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4")
        self.assertEqual(move, "h5f7")

    def test_mate_in_two(self):
        # 1. Nf6+ gxf6 2. Bxf7#
        move, score = best("r2qkb1r/pp2nppp/3p4/2pNN1B1/2BnP3/3P4/PPP2PPP/R2bK2R w KQkq - 1 1")
        self.assertEqual(move, "d5f6")
        self.assertGreater(score, MATE_BOUND)

    def test_takes_free_queen(self):
        move, _ = best("rnb1kbnr/pppp1ppp/8/4p3/4P2q/5N2/PPPP1PPP/RNBQKB1R w KQkq - 0 1")
        self.assertEqual(move, "f3h4")

    def test_black_to_move_mate(self):
        move, score = best("r5k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 1")
        self.assertEqual(move, "a8a1")
        self.assertGreater(score, MATE_BOUND)

    def test_avoids_stalemate_when_winning(self):
        # Qg6 stalemates; anything sensible keeps the win going.
        board = Board("7k/8/5K2/8/8/8/8/6Q1 w - - 0 1")
        move, _ = Searcher().search(board, {"depth": 4})
        board.push(move)
        self.assertNotEqual(board.outcome(), "1/2-1/2 stalemate")

    def test_board_unchanged_after_timed_search(self):
        board = Board("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1")
        fen = board.fen()
        start = time.time()
        move, _ = Searcher().search(board, {"movetime": 300})
        self.assertLess(time.time() - start, 1.5)
        self.assertIn(move, board.legal_moves())
        self.assertEqual(board.fen(), fen)


class UCITest(unittest.TestCase):
    def run_commands(self, *lines):
        out = io.StringIO()
        uci = UCI(out)
        for line in lines:
            uci.handle(line)
        uci.wait()
        return out.getvalue().splitlines()

    def test_handshake(self):
        lines = self.run_commands("uci", "isready")
        self.assertIn("uciok", lines)
        self.assertEqual(lines[-1], "readyok")

    def test_go_returns_legal_bestmove(self):
        lines = self.run_commands("position startpos moves e2e4 e7e5", "go depth 3")
        bestmove = [l for l in lines if l.startswith("bestmove")]
        self.assertEqual(len(bestmove), 1)
        board = Board()
        for text in ("e2e4", "e7e5"):
            board.push(board.parse_uci(text))
        board.parse_uci(bestmove[0].split()[1])  # raises if illegal

    def test_stop_infinite(self):
        out = io.StringIO()
        uci = UCI(out)
        uci.handle("position startpos")
        uci.handle("go infinite")
        time.sleep(0.3)
        uci.handle("stop")
        self.assertTrue(any(l.startswith("bestmove") for l in out.getvalue().splitlines()))


if __name__ == "__main__":
    unittest.main()
