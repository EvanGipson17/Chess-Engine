"""Entry point.

    python -m chess_engine                 # UCI mode (for chess GUIs)
    python -m chess_engine play [options]  # play in the terminal
    python -m chess_engine perft DEPTH [FEN]
"""

import sys
import time


def main():
    args = sys.argv[1:]
    if args and args[0] == "play":
        from .play import main as play_main
        play_main(args[1:])
    elif args and args[0] == "perft":
        from .board import Board, perft
        depth = int(args[1]) if len(args) > 1 else 4
        board = Board(" ".join(args[2:])) if len(args) > 2 else Board()
        start = time.time()
        nodes = perft(board, depth)
        elapsed = time.time() - start
        print(f"perft({depth}) = {nodes}  [{elapsed:.2f}s, {int(nodes / max(elapsed, 1e-9))} nps]")
    else:
        from .uci import main as uci_main
        uci_main()


if __name__ == "__main__":
    main()
