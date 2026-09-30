"""Static evaluation: tapered material + piece-square tables + pawn structure.

Scores are in centipawns from the side to move's point of view.
Tables are written from white's perspective with rank 8 on the first row,
the way you'd see the board printed.
"""

from .board import (
    BISHOP, BLACK, EMPTY, KING, KNIGHT, PAWN, QUEEN, ROOK, SQUARES, WHITE,
    file_of, rank_of,
)

MG_VALUE = {PAWN: 82, KNIGHT: 337, BISHOP: 365, ROOK: 477, QUEEN: 1025, KING: 0}
EG_VALUE = {PAWN: 94, KNIGHT: 281, BISHOP: 297, ROOK: 512, QUEEN: 936, KING: 0}

# Game phase weights: 24 = all pieces on the board, 0 = bare kings and pawns.
PHASE_WEIGHT = {PAWN: 0, KNIGHT: 1, BISHOP: 1, ROOK: 2, QUEEN: 4, KING: 0}
MAX_PHASE = 24

PAWN_PST = [
      0,   0,   0,   0,   0,   0,   0,   0,
     50,  50,  50,  50,  50,  50,  50,  50,
     10,  10,  20,  30,  30,  20,  10,  10,
      5,   5,  10,  25,  25,  10,   5,   5,
      0,   0,   0,  20,  20,   0,   0,   0,
      5,  -5, -10,   0,   0, -10,  -5,   5,
      5,  10,  10, -20, -20,  10,  10,   5,
      0,   0,   0,   0,   0,   0,   0,   0,
]
PAWN_EG_PST = [
      0,   0,   0,   0,   0,   0,   0,   0,
     80,  80,  80,  80,  80,  80,  80,  80,
     50,  50,  50,  50,  50,  50,  50,  50,
     30,  30,  30,  30,  30,  30,  30,  30,
     15,  15,  15,  15,  15,  15,  15,  15,
      5,   5,   5,   5,   5,   5,   5,   5,
      0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,
]
KNIGHT_PST = [
    -50, -40, -30, -30, -30, -30, -40, -50,
    -40, -20,   0,   0,   0,   0, -20, -40,
    -30,   0,  10,  15,  15,  10,   0, -30,
    -30,   5,  15,  20,  20,  15,   5, -30,
    -30,   0,  15,  20,  20,  15,   0, -30,
    -30,   5,  10,  15,  15,  10,   5, -30,
    -40, -20,   0,   5,   5,   0, -20, -40,
    -50, -40, -30, -30, -30, -30, -40, -50,
]
BISHOP_PST = [
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10,   0,   0,   0,   0,   0,   0, -10,
    -10,   0,   5,  10,  10,   5,   0, -10,
    -10,   5,   5,  10,  10,   5,   5, -10,
    -10,   0,  10,  10,  10,  10,   0, -10,
    -10,  10,  10,  10,  10,  10,  10, -10,
    -10,   5,   0,   0,   0,   0,   5, -10,
    -20, -10, -10, -10, -10, -10, -10, -20,
]
ROOK_PST = [
      0,   0,   0,   0,   0,   0,   0,   0,
      5,  10,  10,  10,  10,  10,  10,   5,
     -5,   0,   0,   0,   0,   0,   0,  -5,
     -5,   0,   0,   0,   0,   0,   0,  -5,
     -5,   0,   0,   0,   0,   0,   0,  -5,
     -5,   0,   0,   0,   0,   0,   0,  -5,
     -5,   0,   0,   0,   0,   0,   0,  -5,
      0,   0,   0,   5,   5,   0,   0,   0,
]
QUEEN_PST = [
    -20, -10, -10,  -5,  -5, -10, -10, -20,
    -10,   0,   0,   0,   0,   0,   0, -10,
    -10,   0,   5,   5,   5,   5,   0, -10,
     -5,   0,   5,   5,   5,   5,   0,  -5,
      0,   0,   5,   5,   5,   5,   0,  -5,
    -10,   5,   5,   5,   5,   5,   0, -10,
    -10,   0,   5,   0,   0,   0,   0, -10,
    -20, -10, -10,  -5,  -5, -10, -10, -20,
]
KING_MG_PST = [
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -10, -20, -20, -20, -20, -20, -20, -10,
     20,  20,   0,   0,   0,   0,  20,  20,
     20,  30,  10,   0,   0,  10,  30,  20,
]
KING_EG_PST = [
    -50, -40, -30, -20, -20, -30, -40, -50,
    -30, -20, -10,   0,   0, -10, -20, -30,
    -30, -10,  20,  30,  30,  20, -10, -30,
    -30, -10,  30,  40,  40,  30, -10, -30,
    -30, -10,  30,  40,  40,  30, -10, -30,
    -30, -10,  20,  30,  30,  20, -10, -30,
    -30, -30,   0,   0,   0,   0, -30, -30,
    -50, -30, -30, -30, -30, -30, -30, -50,
]

MG_PST = {PAWN: PAWN_PST, KNIGHT: KNIGHT_PST, BISHOP: BISHOP_PST,
          ROOK: ROOK_PST, QUEEN: QUEEN_PST, KING: KING_MG_PST}
EG_PST = {PAWN: PAWN_EG_PST, KNIGHT: KNIGHT_PST, BISHOP: BISHOP_PST,
          ROOK: ROOK_PST, QUEEN: QUEEN_PST, KING: KING_EG_PST}


def _build_tables():
    """Precompute value + PST per (signed piece, mailbox square) so the
    evaluation loop is a couple of dict lookups per piece."""
    mg, eg = {}, {}
    for piece in (PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING):
        for s in SQUARES:
            f, r = file_of(s), rank_of(s)
            white_idx = (7 - r) * 8 + f
            black_idx = r * 8 + f
            mg[(piece, s)] = MG_VALUE[piece] + MG_PST[piece][white_idx]
            eg[(piece, s)] = EG_VALUE[piece] + EG_PST[piece][white_idx]
            mg[(-piece, s)] = MG_VALUE[piece] + MG_PST[piece][black_idx]
            eg[(-piece, s)] = EG_VALUE[piece] + EG_PST[piece][black_idx]
    return mg, eg


MG_TABLE, EG_TABLE = _build_tables()

BISHOP_PAIR = 30
DOUBLED_PAWN = -12
ISOLATED_PAWN = -15
# Extra bonus for a passed pawn by how far it has advanced (0..7).
PASSED_PAWN_MG = [0, 5, 10, 15, 25, 40, 60, 0]
PASSED_PAWN_EG = [0, 10, 20, 35, 60, 90, 130, 0]
ROOK_OPEN_FILE = 20
ROOK_SEMI_OPEN_FILE = 10
TEMPO = 10


def evaluate(board):
    b = board.squares
    mg = eg = 0
    phase = 0
    bishops = {WHITE: 0, BLACK: 0}
    # Pawn ranks by file for each colour, for pawn-structure terms.
    pawn_files = {WHITE: [[] for _ in range(8)], BLACK: [[] for _ in range(8)]}
    rooks = []

    for s in SQUARES:
        p = b[s]
        if p == EMPTY:
            continue
        color = WHITE if p > 0 else BLACK
        kind = p * color
        mg += MG_TABLE[(p, s)] * color
        eg += EG_TABLE[(p, s)] * color
        phase += PHASE_WEIGHT[kind]
        if kind == PAWN:
            pawn_files[color][file_of(s)].append(rank_of(s))
        elif kind == BISHOP:
            bishops[color] += 1
        elif kind == ROOK:
            rooks.append((color, file_of(s)))

    for color in (WHITE, BLACK):
        if bishops[color] >= 2:
            mg += BISHOP_PAIR * color
            eg += BISHOP_PAIR * color

        ours, theirs = pawn_files[color], pawn_files[-color]
        for f in range(8):
            ranks = ours[f]
            if not ranks:
                continue
            if len(ranks) > 1:
                pen = DOUBLED_PAWN * (len(ranks) - 1)
                mg += pen * color
                eg += pen * color
            left = ours[f - 1] if f > 0 else []
            right = ours[f + 1] if f < 7 else []
            if not left and not right:
                mg += ISOLATED_PAWN * len(ranks) * color
                eg += ISOLATED_PAWN * len(ranks) * color
            for r in ranks:
                if _is_passed(r, f, color, theirs):
                    adv = r if color == WHITE else 7 - r
                    mg += PASSED_PAWN_MG[adv] * color
                    eg += PASSED_PAWN_EG[adv] * color

    for color, f in rooks:
        if not pawn_files[color][f]:
            bonus = ROOK_OPEN_FILE if not pawn_files[-color][f] else ROOK_SEMI_OPEN_FILE
            mg += bonus * color
            eg += bonus * color // 2

    phase = min(phase, MAX_PHASE)
    score = (mg * phase + eg * (MAX_PHASE - phase)) // MAX_PHASE
    return score * board.side + TEMPO


def _is_passed(rank, file, color, enemy_files):
    for f in (file - 1, file, file + 1):
        if f < 0 or f > 7:
            continue
        for r in enemy_files[f]:
            if (color == WHITE and r > rank) or (color == BLACK and r < rank):
                return False
    return True


PIECE_VALUE = {EMPTY: 0, PAWN: 100, KNIGHT: 320, BISHOP: 330, ROOK: 500, QUEEN: 900, KING: 20000}
