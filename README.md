# Chess Engine

A UCI chess engine written in pure Python with no dependencies.

## Features

**Board and move generation**
- 10x12 mailbox board with incremental Zobrist hashing
- Fully legal move generation: castling, en passant, promotions, pins
- Verified against the standard [perft suite](https://www.chessprogramming.org/Perft_Results)
- Detects checkmate, stalemate, the fifty-move rule, threefold repetition and insufficient material

**Search**
- Negamax alpha-beta with principal variation search
- Iterative deepening with time management
- Transposition table
- Quiescence search with delta pruning
- Null-move pruning, late move reductions, reverse futility pruning
- Check extensions and mate distance pruning
- Move ordering: TT move, MVV-LVA captures, killer moves, history heuristic

**Evaluation**
- Tapered middlegame/endgame material and piece-square tables
- Passed, doubled and isolated pawns
- Bishop pair and rooks on open or semi-open files

## Usage

Requires Python 3.9+.

```bash
# Play against it in the terminal
python -m chess_engine play                       # you play white, 3s per engine move
python -m chess_engine play --color black --time 5

# UCI mode, for chess GUIs
python -m chess_engine

# Move generator benchmark
python -m chess_engine perft 5
```

### Using it in a chess GUI

In [Arena](http://www.playwitharena.de/), [Cute Chess](https://cutechess.com/) or
[BanksiaGUI](https://banksiagui.com/), add a new UCI engine and point it at a small
launcher script:

```bash
#!/bin/sh
exec python3 -m chess_engine
```

Set the script's working directory to this repository. On Windows, use a `.bat` file
containing `python -m chess_engine`.

## Tests

```bash
python -m unittest -v
```

The tests cover perft counts on six standard positions, incremental hash correctness,
FEN round-trips, the draw and mate rules, tactical puzzles (mates in one and two,
hanging pieces) and the UCI protocol.

## Layout

| File | What it does |
| --- | --- |
| `chess_engine/board.py` | Board, FEN, move generation, make/unmake, perft |
| `chess_engine/evaluate.py` | Static evaluation |
| `chess_engine/search.py` | Alpha-beta search and time management |
| `chess_engine/uci.py` | UCI protocol |
| `chess_engine/play.py` | Terminal play mode |
