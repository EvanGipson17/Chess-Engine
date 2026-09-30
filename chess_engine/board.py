"""Board representation, move generation and make/unmake.

The board is a 10x12 mailbox: 120 squares where the playable 8x8 area sits in
the middle and the border squares hold OFF so that sliding pieces and knights
stop without any bounds checks. Square a1 is index 21, h1 is 28, a8 is 91 and
h8 is 98.

Pieces are small ints: positive for white, negative for black.
Moves are packed ints: from | to << 7 | promo << 14 | flag << 17.
"""

import random

EMPTY, PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING = 0, 1, 2, 3, 4, 5, 6
OFF = 7
WHITE, BLACK = 1, -1

FLAG_NONE, FLAG_DOUBLE, FLAG_EP, FLAG_CASTLE = 0, 1, 2, 3

WK_CASTLE, WQ_CASTLE, BK_CASTLE, BQ_CASTLE = 1, 2, 4, 8

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

N, S, E, W = 10, -10, 1, -1
KNIGHT_DIRS = (21, 19, 12, 8, -8, -12, -19, -21)
BISHOP_DIRS = (N + E, N + W, S + E, S + W)
ROOK_DIRS = (N, S, E, W)
KING_DIRS = BISHOP_DIRS + ROOK_DIRS

PIECE_CHARS = {PAWN: "p", KNIGHT: "n", BISHOP: "b", ROOK: "r", QUEEN: "q", KING: "k"}
CHAR_PIECES = {c: p for p, c in PIECE_CHARS.items()}


def sq(file, rank):
    """Mailbox index for 0-based file and rank."""
    return 21 + file + 10 * rank


def file_of(s):
    return (s - 21) % 10


def rank_of(s):
    return (s - 21) // 10


def sq_name(s):
    return "abcdefgh"[file_of(s)] + str(rank_of(s) + 1)


def parse_sq(name):
    return sq("abcdefgh".index(name[0]), int(name[1]) - 1)


SQUARES = [sq(f, r) for r in range(8) for f in range(8)]

# Castling rights that survive a move touching each square.
CASTLE_MASK = [15] * 120
CASTLE_MASK[sq(4, 0)] = 15 & ~(WK_CASTLE | WQ_CASTLE)
CASTLE_MASK[sq(7, 0)] = 15 & ~WK_CASTLE
CASTLE_MASK[sq(0, 0)] = 15 & ~WQ_CASTLE
CASTLE_MASK[sq(4, 7)] = 15 & ~(BK_CASTLE | BQ_CASTLE)
CASTLE_MASK[sq(7, 7)] = 15 & ~BK_CASTLE
CASTLE_MASK[sq(0, 7)] = 15 & ~BQ_CASTLE


def make_move(frm, to, promo=0, flag=FLAG_NONE):
    return frm | (to << 7) | (promo << 14) | (flag << 17)


def move_from(m):
    return m & 127


def move_to(m):
    return (m >> 7) & 127


def move_promo(m):
    return (m >> 14) & 7


def move_flag(m):
    return m >> 17


def move_to_uci(m):
    s = sq_name(move_from(m)) + sq_name(move_to(m))
    promo = move_promo(m)
    if promo:
        s += PIECE_CHARS[promo]
    return s


# Zobrist keys. Fixed seed so hashes are reproducible between runs.
_rng = random.Random(0xC0FFEE)
ZOBRIST_PIECE = {
    (p, s): _rng.getrandbits(64)
    for p in (-6, -5, -4, -3, -2, -1, 1, 2, 3, 4, 5, 6)
    for s in SQUARES
}
ZOBRIST_SIDE = _rng.getrandbits(64)
ZOBRIST_CASTLE = [_rng.getrandbits(64) for _ in range(16)]
ZOBRIST_EP = [_rng.getrandbits(64) for _ in range(8)]


class Board:
    def __init__(self, fen=START_FEN):
        self.set_fen(fen)

    # ------------------------------------------------------------------ setup

    def set_fen(self, fen):
        parts = fen.split()
        if len(parts) < 4:
            raise ValueError(f"bad FEN: {fen!r}")
        self.squares = [OFF] * 120
        for s in SQUARES:
            self.squares[s] = EMPTY
        self.king_sq = {WHITE: 0, BLACK: 0}

        rows = parts[0].split("/")
        if len(rows) != 8:
            raise ValueError(f"bad FEN board: {parts[0]!r}")
        for i, row in enumerate(rows):
            rank = 7 - i
            file = 0
            for c in row:
                if c.isdigit():
                    file += int(c)
                    continue
                piece = CHAR_PIECES[c.lower()]
                color = WHITE if c.isupper() else BLACK
                self.squares[sq(file, rank)] = piece * color
                if piece == KING:
                    self.king_sq[color] = sq(file, rank)
                file += 1

        self.side = WHITE if parts[1] == "w" else BLACK
        self.castling = 0
        for c, bit in (("K", WK_CASTLE), ("Q", WQ_CASTLE), ("k", BK_CASTLE), ("q", BQ_CASTLE)):
            if c in parts[2]:
                self.castling |= bit
        self.ep = 0 if parts[3] == "-" else parse_sq(parts[3])
        self.halfmove = int(parts[4]) if len(parts) > 4 else 0
        self.fullmove = int(parts[5]) if len(parts) > 5 else 1

        self.history = []
        self.hash = self.compute_hash()
        self.hash_history = []

    def fen(self):
        rows = []
        for rank in range(7, -1, -1):
            row, empty = "", 0
            for file in range(8):
                p = self.squares[sq(file, rank)]
                if p == EMPTY:
                    empty += 1
                    continue
                if empty:
                    row += str(empty)
                    empty = 0
                c = PIECE_CHARS[abs(p)]
                row += c.upper() if p > 0 else c
            if empty:
                row += str(empty)
            rows.append(row)
        castle = "".join(
            c for c, bit in (("K", WK_CASTLE), ("Q", WQ_CASTLE), ("k", BK_CASTLE), ("q", BQ_CASTLE))
            if self.castling & bit
        ) or "-"
        ep = sq_name(self.ep) if self.ep else "-"
        side = "w" if self.side == WHITE else "b"
        return f"{'/'.join(rows)} {side} {castle} {ep} {self.halfmove} {self.fullmove}"

    def compute_hash(self):
        h = 0
        for s in SQUARES:
            p = self.squares[s]
            if p != EMPTY:
                h ^= ZOBRIST_PIECE[(p, s)]
        if self.side == BLACK:
            h ^= ZOBRIST_SIDE
        h ^= ZOBRIST_CASTLE[self.castling]
        if self.ep:
            h ^= ZOBRIST_EP[file_of(self.ep)]
        return h

    def copy(self):
        b = Board.__new__(Board)
        b.squares = self.squares[:]
        b.king_sq = dict(self.king_sq)
        b.side = self.side
        b.castling = self.castling
        b.ep = self.ep
        b.halfmove = self.halfmove
        b.fullmove = self.fullmove
        b.history = list(self.history)
        b.hash = self.hash
        b.hash_history = list(self.hash_history)
        return b

    def __str__(self):
        lines = []
        for rank in range(7, -1, -1):
            cells = []
            for file in range(8):
                p = self.squares[sq(file, rank)]
                if p == EMPTY:
                    cells.append(".")
                else:
                    c = PIECE_CHARS[abs(p)]
                    cells.append(c.upper() if p > 0 else c)
            lines.append(f"{rank + 1}  " + " ".join(cells))
        lines.append("   a b c d e f g h")
        return "\n".join(lines)

    # ---------------------------------------------------------------- attacks

    def is_attacked(self, target, by):
        """True if side `by` attacks square `target`."""
        b = self.squares
        # Pawns: a white pawn attacks up-left/up-right, so look down from target.
        if by == WHITE:
            if b[target - 9] == PAWN or b[target - 11] == PAWN:
                return True
        else:
            if b[target + 9] == -PAWN or b[target + 11] == -PAWN:
                return True
        knight, king = KNIGHT * by, KING * by
        for d in KNIGHT_DIRS:
            if b[target + d] == knight:
                return True
        for d in KING_DIRS:
            if b[target + d] == king:
                return True
        bishop, rook, queen = BISHOP * by, ROOK * by, QUEEN * by
        for d in BISHOP_DIRS:
            s = target + d
            while b[s] == EMPTY:
                s += d
            if b[s] == bishop or b[s] == queen:
                return True
        for d in ROOK_DIRS:
            s = target + d
            while b[s] == EMPTY:
                s += d
            if b[s] == rook or b[s] == queen:
                return True
        return False

    def in_check(self, side=None):
        if side is None:
            side = self.side
        return self.is_attacked(self.king_sq[side], -side)

    # ------------------------------------------------------------- generation

    def pseudo_moves(self, captures_only=False):
        moves = []
        add = moves.append
        b = self.squares
        us = self.side
        forward = N if us == WHITE else S
        start_rank = 1 if us == WHITE else 6
        promo_rank = 7 if us == WHITE else 0

        for frm in SQUARES:
            p = b[frm] * us
            if p <= 0:
                continue

            if p == PAWN:
                to = frm + forward
                if b[to] == EMPTY:
                    # Promotions count as "noisy", so quiescence sees them too.
                    if rank_of(to) == promo_rank:
                        for promo in ((QUEEN,) if captures_only else (QUEEN, ROOK, BISHOP, KNIGHT)):
                            add(make_move(frm, to, promo))
                    elif not captures_only:
                        add(make_move(frm, to))
                        to2 = to + forward
                        if rank_of(frm) == start_rank and b[to2] == EMPTY:
                            add(make_move(frm, to2, 0, FLAG_DOUBLE))
                for to in (frm + forward + E, frm + forward + W):
                    target = b[to]
                    if target != OFF and target * us < 0:
                        if rank_of(to) == promo_rank:
                            for promo in (QUEEN, ROOK, BISHOP, KNIGHT):
                                add(make_move(frm, to, promo))
                        else:
                            add(make_move(frm, to))
                    elif to == self.ep and self.ep:
                        add(make_move(frm, to, 0, FLAG_EP))
                continue

            if p == KNIGHT or p == KING:
                for d in (KNIGHT_DIRS if p == KNIGHT else KING_DIRS):
                    to = frm + d
                    target = b[to]
                    if target == OFF or target * us > 0:
                        continue
                    if captures_only and target == EMPTY:
                        continue
                    add(make_move(frm, to))
                continue

            dirs = BISHOP_DIRS if p == BISHOP else ROOK_DIRS if p == ROOK else KING_DIRS
            for d in dirs:
                to = frm + d
                while True:
                    target = b[to]
                    if target == OFF or target * us > 0:
                        break
                    if target == EMPTY:
                        if not captures_only:
                            add(make_move(frm, to))
                    else:
                        add(make_move(frm, to))
                        break
                    to += d

        if not captures_only:
            self._castling_moves(add)
        return moves

    def _castling_moves(self, add):
        b = self.squares
        them = -self.side
        if self.side == WHITE:
            rank, k_bit, q_bit = 0, WK_CASTLE, WQ_CASTLE
        else:
            rank, k_bit, q_bit = 7, BK_CASTLE, BQ_CASTLE
        e, f, g = sq(4, rank), sq(5, rank), sq(6, rank)
        d, c, bsq = sq(3, rank), sq(2, rank), sq(1, rank)
        if not self.castling & (k_bit | q_bit):
            return
        if self.is_attacked(e, them):
            return
        if (self.castling & k_bit and b[f] == EMPTY and b[g] == EMPTY
                and not self.is_attacked(f, them) and not self.is_attacked(g, them)):
            add(make_move(e, g, 0, FLAG_CASTLE))
        if (self.castling & q_bit and b[d] == EMPTY and b[c] == EMPTY and b[bsq] == EMPTY
                and not self.is_attacked(d, them) and not self.is_attacked(c, them)):
            add(make_move(e, c, 0, FLAG_CASTLE))

    def legal_moves(self):
        legal = []
        for m in self.pseudo_moves():
            if self.push(m):
                legal.append(m)
                self.pop()
        return legal

    # -------------------------------------------------------------- make/undo

    def push(self, m):
        """Play move m. Returns False (and leaves the board unchanged) if the
        move would leave our own king in check."""
        b = self.squares
        frm, to = move_from(m), move_to(m)
        promo, flag = move_promo(m), move_flag(m)
        us = self.side
        piece = b[frm]
        captured = b[to]
        h = self.hash

        self.history.append((m, captured, self.castling, self.ep, self.halfmove, h))
        self.hash_history.append(h)

        h ^= ZOBRIST_CASTLE[self.castling]
        if self.ep:
            h ^= ZOBRIST_EP[file_of(self.ep)]

        if captured != EMPTY:
            h ^= ZOBRIST_PIECE[(captured, to)]
        h ^= ZOBRIST_PIECE[(piece, frm)]
        b[frm] = EMPTY
        placed = promo * us if promo else piece
        b[to] = placed
        h ^= ZOBRIST_PIECE[(placed, to)]

        if flag == FLAG_EP:
            cap_sq = to - (N if us == WHITE else S)
            h ^= ZOBRIST_PIECE[(b[cap_sq], cap_sq)]
            b[cap_sq] = EMPTY
        elif flag == FLAG_CASTLE:
            if to > frm:
                r_from, r_to = to + 1, to - 1
            else:
                r_from, r_to = to - 2, to + 1
            rook = b[r_from]
            b[r_from] = EMPTY
            b[r_to] = rook
            h ^= ZOBRIST_PIECE[(rook, r_from)] ^ ZOBRIST_PIECE[(rook, r_to)]

        if abs(piece) == KING:
            self.king_sq[us] = to

        self.castling &= CASTLE_MASK[frm] & CASTLE_MASK[to]
        self.ep = (frm + to) // 2 if flag == FLAG_DOUBLE else 0
        h ^= ZOBRIST_CASTLE[self.castling]
        if self.ep:
            h ^= ZOBRIST_EP[file_of(self.ep)]

        self.halfmove = 0 if abs(piece) == PAWN or captured != EMPTY else self.halfmove + 1
        if us == BLACK:
            self.fullmove += 1
        self.side = -us
        h ^= ZOBRIST_SIDE
        self.hash = h

        if self.is_attacked(self.king_sq[us], -us):
            self.pop()
            return False
        return True

    def pop(self):
        m, captured, castling, ep, halfmove, h = self.history.pop()
        self.hash_history.pop()
        b = self.squares
        frm, to = move_from(m), move_to(m)
        promo, flag = move_promo(m), move_flag(m)
        self.side = us = -self.side
        if us == BLACK:
            self.fullmove -= 1

        piece = PAWN * us if promo else b[to]
        b[frm] = piece
        b[to] = captured
        if flag == FLAG_EP:
            b[to - (N if us == WHITE else S)] = -PAWN * us
        elif flag == FLAG_CASTLE:
            if to > frm:
                r_from, r_to = to + 1, to - 1
            else:
                r_from, r_to = to - 2, to + 1
            b[r_from] = b[r_to]
            b[r_to] = EMPTY
        if abs(piece) == KING:
            self.king_sq[us] = frm

        self.castling = castling
        self.ep = ep
        self.halfmove = halfmove
        self.hash = h

    def push_null(self):
        self.history.append((0, EMPTY, self.castling, self.ep, self.halfmove, self.hash))
        self.hash_history.append(self.hash)
        if self.ep:
            self.hash ^= ZOBRIST_EP[file_of(self.ep)]
        self.ep = 0
        self.side = -self.side
        self.hash ^= ZOBRIST_SIDE

    def pop_null(self):
        _, _, _, ep, _, h = self.history.pop()
        self.hash_history.pop()
        self.side = -self.side
        self.ep = ep
        self.hash = h

    # ------------------------------------------------------------------ misc

    def parse_uci(self, text):
        """Return the legal move matching a UCI string like e2e4 or e7e8q."""
        for m in self.legal_moves():
            if move_to_uci(m) == text:
                return m
        raise ValueError(f"illegal move: {text}")

    def is_repetition(self):
        """True if the current position occurred before since the last
        irreversible move. One repeat is enough inside a search."""
        hist = self.hash_history
        stop = max(len(hist) - self.halfmove, 0)
        for i in range(len(hist) - 2, stop - 1, -2):
            if hist[i] == self.hash:
                return True
        return False

    def is_threefold(self):
        hist = self.hash_history
        stop = max(len(hist) - self.halfmove, 0)
        count = sum(1 for i in range(len(hist) - 2, stop - 1, -2) if hist[i] == self.hash)
        return count >= 2

    def insufficient_material(self):
        minors = 0
        for s in SQUARES:
            p = abs(self.squares[s])
            if p in (PAWN, ROOK, QUEEN):
                return False
            if p in (KNIGHT, BISHOP):
                minors += 1
        return minors <= 1

    def outcome(self):
        """None if the game is ongoing, else a short result string."""
        if not self.legal_moves():
            if self.in_check():
                return "0-1 checkmate" if self.side == WHITE else "1-0 checkmate"
            return "1/2-1/2 stalemate"
        if self.halfmove >= 100:
            return "1/2-1/2 fifty-move rule"
        if self.is_threefold():
            return "1/2-1/2 threefold repetition"
        if self.insufficient_material():
            return "1/2-1/2 insufficient material"
        return None


def perft(board, depth):
    if depth == 0:
        return 1
    nodes = 0
    for m in board.pseudo_moves():
        if board.push(m):
            nodes += perft(board, depth - 1)
            board.pop()
    return nodes
