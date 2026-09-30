"""Alpha-beta search.

Negamax with principal variation search, iterative deepening, a
transposition table, quiescence search, null-move pruning, late move
reductions, reverse futility pruning, check extensions, and move ordering
by TT move / MVV-LVA / killers / history.
"""

import threading
import time

from .board import (
    BISHOP, EMPTY, FLAG_EP, KNIGHT, PAWN, QUEEN, ROOK, SQUARES,
    move_flag, move_from, move_promo, move_to, move_to_uci,
)
from .evaluate import PIECE_VALUE, evaluate

INF = 1_000_000
MATE = 100_000
MAX_PLY = 64
MATE_BOUND = MATE - MAX_PLY

EXACT, LOWER, UPPER = 0, 1, 2
TT_MAX_ENTRIES = 2_000_000


class SearchStopped(Exception):
    pass


def score_to_uci(score):
    if score > MATE_BOUND:
        return f"mate {(MATE - score + 1) // 2}"
    if score < -MATE_BOUND:
        return f"mate {-((MATE + score) // 2)}"
    return f"cp {score}"


class Searcher:
    def __init__(self):
        self.tt = {}
        self.stop_event = threading.Event()
        self.reset_heuristics()

    def new_game(self):
        self.tt.clear()
        self.reset_heuristics()

    def reset_heuristics(self):
        self.killers = [[0, 0] for _ in range(MAX_PLY + 1)]
        self.history = [0] * (13 * 120)

    def stop(self):
        self.stop_event.set()

    # ------------------------------------------------------------ time mgmt

    def _plan_time(self, board, limits):
        """Return (soft, hard) time budgets in seconds, or (None, None)."""
        if limits.get("infinite"):
            return None, None
        if "movetime" in limits:
            t = limits["movetime"] / 1000
            return t, t
        our_time = limits.get("wtime" if board.side == 1 else "btime")
        if our_time is None:
            return None, None
        inc = limits.get("winc" if board.side == 1 else "binc", 0)
        moves_to_go = limits.get("movestogo") or 30
        our_time /= 1000
        inc /= 1000
        # Leave a safety margin for GUI/process overhead.
        usable = max(our_time - 0.05, 0.01)
        soft = min(usable / moves_to_go + inc * 0.75, usable * 0.5)
        hard = min(soft * 3, usable * 0.8)
        return max(soft, 0.01), max(hard, 0.01)

    def _check_time(self):
        self.next_check = self.nodes + 1024
        if self.stop_event.is_set():
            raise SearchStopped
        if self.hard_deadline is not None and time.time() >= self.hard_deadline:
            raise SearchStopped
        if self.node_limit is not None and self.nodes >= self.node_limit:
            raise SearchStopped

    # ---------------------------------------------------------------- search

    def search(self, board, limits=None, info=None):
        """Find the best move. `limits` uses UCI names: depth, movetime,
        wtime, btime, winc, binc, movestogo, nodes, infinite. `info` is an
        optional callback that receives UCI "info ..." strings.
        Returns (best_move, score)."""
        limits = limits or {}
        self.stop_event.clear()
        self.nodes = 0
        self.start = time.time()
        soft, hard = self._plan_time(board, limits)
        self.node_limit = limits.get("nodes")
        if self.node_limit is not None:
            self.next_check = min(self.node_limit, 1024)
        else:
            self.next_check = 1024
        self.hard_deadline = self.start + hard if hard is not None else None
        max_depth = min(limits.get("depth", MAX_PLY), MAX_PLY)
        root_len = len(board.history)

        legal = board.legal_moves()
        if not legal:
            return 0, 0
        best_move, best_score = legal[0], 0
        self.killers = [[0, 0] for _ in range(MAX_PLY + 1)]
        self.history = [h // 8 for h in self.history]

        for depth in range(1, max_depth + 1):
            self.root_best = 0
            try:
                score = self.negamax(board, depth, -INF, INF, 0, True)
            except SearchStopped:
                # Keep a move from the unfinished iteration only if it
                # already beat the previous best line.
                if self.root_best:
                    best_move = self.root_best
                break
            finally:
                # Unwind any moves still on the stack from an aborted search.
                while len(board.history) > root_len:
                    if board.history[-1][0] == 0:
                        board.pop_null()
                    else:
                        board.pop()

            if self.root_best:
                best_move, best_score = self.root_best, score
            elapsed = time.time() - self.start
            if info:
                pv = self._pv(board, best_move, depth)
                nps = int(self.nodes / elapsed) if elapsed > 0 else 0
                info(f"info depth {depth} score {score_to_uci(best_score)} "
                     f"nodes {self.nodes} nps {nps} time {int(elapsed * 1000)} "
                     f"pv {' '.join(move_to_uci(m) for m in pv)}")
            if abs(best_score) > MATE_BOUND and depth > 1 and not limits.get("infinite"):
                # Forced mate found; searching deeper won't change the move.
                if MATE - abs(best_score) <= depth:
                    break
            if soft is not None and elapsed >= soft * 0.6:
                break

        if len(self.tt) > TT_MAX_ENTRIES:
            self.tt.clear()
        return best_move, best_score

    def negamax(self, board, depth, alpha, beta, ply, allow_null):
        if self.nodes >= self.next_check:
            self._check_time()

        pv_node = beta - alpha > 1

        if ply > 0:
            if board.halfmove >= 100 or board.is_repetition():
                return 0
            # Mate distance pruning.
            alpha = max(alpha, -MATE + ply)
            beta = min(beta, MATE - ply - 1)
            if alpha >= beta:
                return alpha
            if ply >= MAX_PLY:
                return evaluate(board)

        in_check = board.in_check()
        if in_check:
            depth += 1
        if depth <= 0:
            return self.quiesce(board, alpha, beta, ply)

        self.nodes += 1

        tt_move = 0
        entry = self.tt.get(board.hash)
        if entry is not None:
            e_depth, e_score, e_flag, e_move = entry
            tt_move = e_move
            if e_depth >= depth and ply > 0 and not pv_node:
                if e_score > MATE_BOUND:
                    e_score -= ply
                elif e_score < -MATE_BOUND:
                    e_score += ply
                if (e_flag == EXACT
                        or (e_flag == LOWER and e_score >= beta)
                        or (e_flag == UPPER and e_score <= alpha)):
                    return e_score

        if not in_check and not pv_node:
            static_eval = evaluate(board)
            # Reverse futility pruning: way above beta at shallow depth.
            if depth <= 3 and static_eval - 120 * depth >= beta and abs(beta) < MATE_BOUND:
                return static_eval
            # Null move pruning: if passing still beats beta, cut.
            if allow_null and depth >= 3 and static_eval >= beta and self._has_pieces(board):
                r = 2 + depth // 4
                board.push_null()
                score = -self.negamax(board, depth - 1 - r, -beta, -beta + 1, ply + 1, False)
                board.pop_null()
                if score >= beta:
                    return beta if score > MATE_BOUND else score

        moves = self._ordered(board, board.pseudo_moves(), tt_move, ply)
        original_alpha = alpha
        best_score = -INF
        best_move = 0
        legal = 0
        b = board.squares

        for m in moves:
            is_capture = b[move_to(m)] != EMPTY or move_flag(m) == FLAG_EP
            is_quiet = not is_capture and not move_promo(m)
            piece = b[move_from(m)]
            if not board.push(m):
                continue
            legal += 1
            gives_check = board.in_check()

            if legal == 1:
                score = -self.negamax(board, depth - 1, -beta, -alpha, ply + 1, True)
            else:
                r = 0
                if depth >= 3 and legal > 3 and is_quiet and not in_check and not gives_check:
                    r = 1 if legal <= 8 else 2
                    if pv_node:
                        r -= 1
                score = -self.negamax(board, depth - 1 - r, -alpha - 1, -alpha, ply + 1, True)
                if score > alpha and r > 0:
                    score = -self.negamax(board, depth - 1, -alpha - 1, -alpha, ply + 1, True)
                if alpha < score < beta:
                    score = -self.negamax(board, depth - 1, -beta, -alpha, ply + 1, True)
            board.pop()

            if score > best_score:
                best_score = score
                best_move = m
                if score > alpha:
                    alpha = score
                    if ply == 0:
                        self.root_best = m
                    if score >= beta:
                        if is_quiet:
                            k = self.killers[ply]
                            if k[0] != m:
                                k[1] = k[0]
                                k[0] = m
                            self.history[(piece + 6) * 120 + move_to(m)] += depth * depth
                        break

        if legal == 0:
            return -MATE + ply if in_check else 0

        if best_score >= beta:
            flag = LOWER
        elif best_score > original_alpha:
            flag = EXACT
        else:
            flag = UPPER
        stored = best_score
        if stored > MATE_BOUND:
            stored += ply
        elif stored < -MATE_BOUND:
            stored -= ply
        self.tt[board.hash] = (depth, stored, flag, best_move)
        return best_score

    def quiesce(self, board, alpha, beta, ply):
        self.nodes += 1
        if self.nodes >= self.next_check:
            self._check_time()

        stand_pat = evaluate(board)
        if ply >= MAX_PLY or stand_pat >= beta:
            return stand_pat
        if stand_pat > alpha:
            alpha = stand_pat

        b = board.squares
        moves = self._ordered(board, board.pseudo_moves(captures_only=True), 0, ply)
        for m in moves:
            captured = b[move_to(m)]
            gain = PIECE_VALUE[abs(captured)] if captured != EMPTY else PIECE_VALUE[PAWN]
            if move_promo(m):
                gain += PIECE_VALUE[QUEEN] - PIECE_VALUE[PAWN]
            # Delta pruning: even winning this piece can't lift us to alpha.
            if stand_pat + gain + 200 < alpha:
                continue
            if not board.push(m):
                continue
            score = -self.quiesce(board, -beta, -alpha, ply + 1)
            board.pop()
            if score >= beta:
                return score
            if score > alpha:
                alpha = score
        return alpha

    # --------------------------------------------------------------- helpers

    def _ordered(self, board, moves, tt_move, ply):
        b = board.squares
        killers = self.killers[ply] if ply <= MAX_PLY else (0, 0)
        history = self.history

        def key(m):
            if m == tt_move:
                return 10_000_000
            to = move_to(m)
            victim = b[to]
            promo = move_promo(m)
            if victim != EMPTY or move_flag(m) == FLAG_EP:
                # MVV-LVA: most valuable victim, least valuable attacker.
                v = PIECE_VALUE[abs(victim)] if victim != EMPTY else PIECE_VALUE[PAWN]
                a = abs(b[move_from(m)])
                return 1_000_000 + v * 10 - a + (PIECE_VALUE[promo] if promo else 0)
            if promo:
                return 900_000 + PIECE_VALUE[promo]
            if m == killers[0]:
                return 800_000
            if m == killers[1]:
                return 700_000
            return history[(b[move_from(m)] + 6) * 120 + to]

        moves.sort(key=key, reverse=True)
        return moves

    @staticmethod
    def _has_pieces(board):
        """Side to move has something besides king and pawns (null move is
        unsafe in pawn endgames because of zugzwang)."""
        b, us = board.squares, board.side
        for s in SQUARES:
            p = b[s] * us
            if p in (KNIGHT, BISHOP, ROOK, QUEEN):
                return True
        return False

    def _pv(self, board, first, depth):
        pv = [first]
        pushed = 0
        seen = {board.hash}
        if board.push(first):
            pushed += 1
            while len(pv) < depth:
                entry = self.tt.get(board.hash)
                if not entry or not entry[3] or board.hash in seen:
                    break
                seen.add(board.hash)
                m = entry[3]
                if m not in board.pseudo_moves() or not board.push(m):
                    break
                pushed += 1
                pv.append(m)
        for _ in range(pushed):
            board.pop()
        return pv

