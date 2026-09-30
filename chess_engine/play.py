"""Play against the engine in the terminal."""

from .board import WHITE, Board, move_to_uci
from .search import Searcher, score_to_uci


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description="Play chess against the engine.")
    parser.add_argument("--color", choices=("white", "black"), default="white",
                        help="the side you play (default: white)")
    parser.add_argument("--time", type=float, default=3.0,
                        help="engine thinking time per move in seconds (default: 3)")
    parser.add_argument("--fen", default=None, help="start from this FEN")
    args = parser.parse_args(argv)

    board = Board(args.fen) if args.fen else Board()
    human = WHITE if args.color == "white" else -WHITE
    searcher = Searcher()

    print("Enter moves like e2e4 or e7e8q. Commands: moves, undo, fen, quit.\n")
    while True:
        print(board, "\n")
        result = board.outcome()
        if result:
            print(f"Game over: {result}")
            return

        if board.side != human:
            move, score = searcher.search(board, {"movetime": int(args.time * 1000)})
            print(f"Engine plays {move_to_uci(move)} ({score_to_uci(score)})\n")
            board.push(move)
            continue

        text = input("Your move: ").strip().lower()
        if text in ("quit", "exit"):
            return
        if text == "moves":
            print(" ".join(sorted(move_to_uci(m) for m in board.legal_moves())), "\n")
            continue
        if text == "fen":
            print(board.fen(), "\n")
            continue
        if text == "undo":
            # Take back your move and the engine's reply.
            for _ in range(2):
                if board.history:
                    board.pop()
            continue
        try:
            board.push(board.parse_uci(text))
        except ValueError:
            print(f"'{text}' isn't a legal move. Type 'moves' to list them.\n")
