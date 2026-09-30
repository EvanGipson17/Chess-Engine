"""UCI protocol front end, so the engine works in any chess GUI
(Arena, Cute Chess, BanksiaGUI, lichess-bot, ...)."""

import sys
import threading

from .board import START_FEN, Board, move_to_uci
from .search import Searcher

NAME = "Gipson Engine"
AUTHOR = "Evan Gipson"

GO_INT_ARGS = ("wtime", "btime", "winc", "binc", "movestogo", "depth", "nodes", "movetime")


def parse_go(tokens):
    limits = {}
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in GO_INT_ARGS and i + 1 < len(tokens):
            limits[tok] = int(tokens[i + 1])
            i += 2
        elif tok == "infinite":
            limits["infinite"] = True
            i += 1
        else:
            i += 1
    return limits


def parse_position(tokens):
    board = Board()
    if not tokens:
        return board
    if tokens[0] == "startpos":
        board.set_fen(START_FEN)
        rest = tokens[1:]
    elif tokens[0] == "fen":
        end = tokens.index("moves") if "moves" in tokens else len(tokens)
        board.set_fen(" ".join(tokens[1:end]))
        rest = tokens[end:]
    else:
        raise ValueError("expected 'startpos' or 'fen'")
    if rest and rest[0] == "moves":
        for text in rest[1:]:
            board.push(board.parse_uci(text))
    return board


class UCI:
    def __init__(self, out=sys.stdout):
        self.out = out
        self.board = Board()
        self.searcher = Searcher()
        self.thread = None
        self.lock = threading.Lock()

    def send(self, line):
        with self.lock:
            self.out.write(line + "\n")
            self.out.flush()

    def wait(self):
        if self.thread is not None:
            self.thread.join()
            self.thread = None

    def stop(self):
        if self.thread is not None:
            self.searcher.stop()
            self.wait()

    def _go(self, board, limits):
        move, _ = self.searcher.search(board, limits, self.send)
        self.send(f"bestmove {move_to_uci(move) if move else '0000'}")

    def handle(self, line):
        """Process one command. Returns False when the engine should quit."""
        tokens = line.split()
        if not tokens:
            return True
        cmd, args = tokens[0], tokens[1:]

        if cmd == "uci":
            self.send(f"id name {NAME}")
            self.send(f"id author {AUTHOR}")
            self.send("uciok")
        elif cmd == "isready":
            self.send("readyok")
        elif cmd == "ucinewgame":
            self.stop()
            self.searcher.new_game()
            self.board = Board()
        elif cmd == "position":
            self.stop()
            try:
                self.board = parse_position(args)
            except (ValueError, KeyError, IndexError) as exc:
                self.send(f"info string bad position: {exc}")
        elif cmd == "go":
            self.stop()
            limits = parse_go(args)
            # Search a copy so a later "position" can't corrupt a running search.
            board = self.board.copy()
            self.thread = threading.Thread(target=self._go, args=(board, limits), daemon=True)
            self.thread.start()
        elif cmd == "stop":
            self.stop()
        elif cmd == "quit":
            self.stop()
            return False
        elif cmd == "d":
            self.send(str(self.board))
            self.send(f"Fen: {self.board.fen()}")
        return True

    def loop(self, stream=sys.stdin):
        for line in stream:
            if not self.handle(line.strip()):
                break
        self.stop()


def main():
    UCI().loop()
