"""
chess_analyzer.analyzer
~~~~~~~~~~~~~~~~~~~~~~~
PGN parsing, Centipawn Loss (CPL) calculation, and move classification.

Design decisions documented inline:

  • **Perspective normalization** — Stockfish's ``PovScore`` is always
    relative to the *side to move*.  After a move is played the side
    flips, so we convert every score to White's perspective before
    computing deltas.  This avoids sign-confusion.

  • **Mate-score linearization** — ``Mate(n)`` objects cannot be
    subtracted from centipawn integers.  We map them to a large scalar
    (±10 000 cp) so the arithmetic stays clean.  The sign tells us
    *who* is getting mated.

  • **Classification thresholds** follow the widely-used scale:
        Best  = 0 cp
        Excellent / Good  < 30 cp
        Inaccuracy  30–80 cp
        Mistake     80–200 cp
        Blunder     > 200 cp
    A special "Forced Mate" category is added when a mate sequence was
    available but the player deviated.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from typing import Optional

import chess
import chess.pgn

from chess_analyzer.engine import StockfishEngine

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
#  Constants
# ═══════════════════════════════════════════════════════════════════════════

# Scalar stand-in for Mate scores so we can do simple subtraction.
# 10 000 centipawns ≈ 100 pawns — absurdly large but finite.
MATE_SCORE_CP: int = 10_000

# Classification boundaries (centipawns).
THRESHOLD_GOOD: int = 30       # 0 < cpl < 30 → "Good" or "Excellent"
THRESHOLD_INACCURACY: int = 80
THRESHOLD_MISTAKE: int = 200   # 80 ≤ cpl < 200


# ═══════════════════════════════════════════════════════════════════════════
#  Data containers
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class MoveAnalysis:
    """Result of analysing a single half-move (ply)."""

    move_number: int                # Full move number (1-indexed).
    side: str                       # "white" or "black".
    move_san: str                   # Standard algebraic notation (e.g. "Nf3").
    move_uci: str                   # UCI notation (e.g. "g1f3").
    score_before_cp: int            # Position eval *before* this move (White POV, cp).
    score_after_cp: int             # Position eval *after* this move  (White POV, cp).
    cpl: int                        # Centipawn loss (≥ 0).
    classification: str             # Human-readable category.
    best_move_san: Optional[str]    # Engine's preferred move (SAN), if different.
    best_move_uci: Optional[str]    # Engine's preferred move (UCI), if different.
    is_mate_before: bool = False    # Was the position a forced mate before?
    is_mate_after: bool = False     # Is the position a forced mate after?


@dataclass
class GameAnalysis:
    """Aggregated analysis for an entire game."""

    headers: dict[str, str] = field(default_factory=dict)
    moves: list[MoveAnalysis] = field(default_factory=list)

    # ── Summary statistics ───────────────────────────────────────────

    @property
    def total_moves(self) -> int:
        return len(self.moves)

    @property
    def average_cpl(self) -> float:
        if not self.moves:
            return 0.0
        return sum(m.cpl for m in self.moves) / len(self.moves)

    def average_cpl_for(self, side: str) -> float:
        """Average CPL filtered to one side ('white' or 'black')."""
        side_moves = [m for m in self.moves if m.side == side]
        if not side_moves:
            return 0.0
        return sum(m.cpl for m in side_moves) / len(side_moves)

    def classification_counts(self, side: Optional[str] = None) -> dict[str, int]:
        """Count how many moves fall into each classification bucket."""
        pool = self.moves if side is None else [
            m for m in self.moves if m.side == side
        ]
        counts: dict[str, int] = {}
        for m in pool:
            counts[m.classification] = counts.get(m.classification, 0) + 1
        return counts


# ═══════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _score_to_cp(score: chess.engine.PovScore, pov_white: bool = True) -> int:
    """Convert a ``PovScore`` to an integer centipawn value from White's POV.

    Why White's POV?
    ~~~~~~~~~~~~~~~~
    Stockfish returns scores relative to the *side to move*.  If we kept
    that convention, a position evaluated as +150 before Black's move
    would become −150 after Black's move — even if Black played the best
    move.  Normalizing to White's POV removes the sign-flip headache.

    Mate handling
    ~~~~~~~~~~~~~
    ``Mate(n)`` means "mate in *n* full moves".  We cannot subtract a
    Mate from a centipawn value, so we replace it with a large scalar.
    ``Mate(+n)`` (the side to move delivers mate) → +MATE_SCORE_CP.
    ``Mate(-n)`` (the side to move gets mated)    → −MATE_SCORE_CP.
    We adjust the sign for perspective afterwards.
    """
    # Get score relative to White.
    white_score = score.white()

    cp = white_score.score(mate_score=MATE_SCORE_CP)

    # ``score(mate_score=…)`` returns:
    #   • The raw centipawn value if the score is a Cp, or
    #   • ±mate_score if the score is a Mate.
    # Either way we now have a plain int from White's perspective.
    if cp is None:
        # Defensive fallback — should never happen with mate_score set.
        return 0
    return cp


def _is_mate(score: chess.engine.PovScore) -> bool:
    """Return ``True`` if the score represents a forced checkmate."""
    return score.white().is_mate()


def classify_cpl(cpl: int, mate_available: bool) -> str:
    """Map a centipawn-loss value to a human-readable category.

    Parameters
    ----------
    cpl:
        Non-negative centipawn loss.
    mate_available:
        ``True`` when the engine had a forced-mate line but the player
        chose a different move.

    Returns
    -------
    str
        One of: "Best", "Excellent", "Good", "Inaccuracy", "Mistake",
        "Blunder", "Forced Mate".
    """
    # Special case: the engine saw a mate and the player missed it.
    if mate_available:
        return "Forced Mate"

    if cpl == 0:
        return "Best"
    if cpl < 10:
        return "Excellent"
    if cpl < THRESHOLD_GOOD:
        return "Good"
    if cpl < THRESHOLD_INACCURACY:
        return "Inaccuracy"
    if cpl < THRESHOLD_MISTAKE:
        return "Mistake"
    return "Blunder"


# ═══════════════════════════════════════════════════════════════════════════
#  PGN parsing
# ═══════════════════════════════════════════════════════════════════════════


def parse_pgn(pgn_string: str) -> Optional[chess.pgn.Game]:
    """Parse a PGN string into a ``chess.pgn.Game`` object.

    Returns ``None`` if the string is empty or malformed.
    """
    game = chess.pgn.read_game(io.StringIO(pgn_string))
    if game is None:
        logger.warning("Failed to parse PGN (empty or malformed).")
    return game


# ═══════════════════════════════════════════════════════════════════════════
#  Core analysis loop
# ═══════════════════════════════════════════════════════════════════════════


def analyze_game(
    pgn_string: str,
    engine: StockfishEngine,
    depth: Optional[int] = None,
) -> GameAnalysis:
    """Analyse every move in a PGN and return per-move CPL + classification.

    Algorithm
    ---------
    1. Parse PGN into a move list.
    2. Set up the board at the starting position.
    3. Evaluate the position *before* the first move.
    4. For each subsequent move:
       a. Ask the engine for its best move + evaluation (``score_before``).
       b. Push the player's actual move onto the board.
       c. Evaluate the new position (``score_after``).
       d. CPL = |score_before − score_after| from the moving side's POV.
       e. Classify the CPL.
    5. Collect everything into a ``GameAnalysis``.

    Parameters
    ----------
    pgn_string:
        Raw PGN text of one game.
    engine:
        An *already-started* :class:`StockfishEngine` (inside a ``with``).
    depth:
        Override the engine's default depth for this analysis.
    """
    game = parse_pgn(pgn_string)
    if game is None:
        return GameAnalysis()

    # Extract PGN headers (White, Black, Event, Date, Result, …).
    headers = {k: v for k, v in game.headers.items()}

    board = game.board()  # Starting position (usually standard).
    moves_analysis: list[MoveAnalysis] = []
    move_list = list(game.mainline_moves())

    if not move_list:
        logger.warning("Game has no moves to analyse.")
        return GameAnalysis(headers=headers)

    # ── Initial evaluation (before the very first move) ──────────
    info_before = engine.evaluate_board(board, depth=depth)
    score_before_pov = info_before["score"]

    for i, move in enumerate(move_list):
        # Determine whose turn it is *before* the move is played.
        side = "white" if board.turn == chess.WHITE else "black"
        full_move_number = board.fullmove_number

        # SAN must be generated *before* the move is pushed.
        move_san = board.san(move)

        # ── Engine's best move for this position ─────────────────
        # We already have the evaluation from ``info_before``.  Now we
        # also need the engine's *preferred* move so we can compare.
        best_move, best_info = engine.get_best_move(board, depth=depth)
        best_move_san = board.san(best_move) if best_move else None
        best_move_uci = best_move.uci() if best_move else None

        score_before_cp = _score_to_cp(score_before_pov)
        mate_before = _is_mate(score_before_pov)

        # ── Push the player's actual move ────────────────────────
        board.push(move)

        # ── Evaluate *after* the move ────────────────────────────
        info_after = engine.evaluate_board(board, depth=depth)
        score_after_pov = info_after["score"]
        score_after_cp = _score_to_cp(score_after_pov)
        mate_after = _is_mate(score_after_pov)

        # ── CPL calculation ──────────────────────────────────────
        #
        # CPL measures how much evaluation the player "lost" by not
        # playing the engine's top choice.
        #
        # Because we normalised everything to White's perspective:
        #   • White wants the score to stay HIGH (or go higher).
        #   • Black wants the score to stay LOW  (or go lower).
        #
        # So:
        #   White's CPL = score_before − score_after   (positive = lost eval)
        #   Black's CPL = score_after  − score_before  (positive = lost eval)
        #
        # We clamp to ≥ 0 because gaining eval is not a "loss".
        if side == "white":
            raw_cpl = score_before_cp - score_after_cp
        else:
            raw_cpl = score_after_cp - score_before_cp

        cpl = max(0, raw_cpl)

        # Did the engine have a forced-mate line that the player missed?
        mate_available = mate_before and not _is_mate(score_after_pov)

        classification = classify_cpl(cpl, mate_available)

        moves_analysis.append(
            MoveAnalysis(
                move_number=full_move_number,
                side=side,
                move_san=move_san,
                move_uci=move.uci(),
                score_before_cp=score_before_cp,
                score_after_cp=score_after_cp,
                cpl=cpl,
                classification=classification,
                best_move_san=best_move_san if move != best_move else None,
                best_move_uci=best_move_uci if move != best_move else None,
                is_mate_before=mate_before,
                is_mate_after=mate_after,
            )
        )

        logger.debug(
            "Move %d. %s %s  CPL=%d  [%s]",
            full_move_number,
            side,
            move_san,
            cpl,
            classification,
        )

        # The "after" eval of this move becomes the "before" eval for
        # the next move — avoids redundant engine calls.
        score_before_pov = score_after_pov

    return GameAnalysis(headers=headers, moves=moves_analysis)
