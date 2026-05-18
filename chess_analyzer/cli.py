"""
chess_analyzer.cli
~~~~~~~~~~~~~~~~~~
Command-line interface entrypoint for the Chess Game Analyzer.

Run with::

    python -m chess_analyzer.cli --username <chess.com_username>

Or after installing the package::

    chess-analyzer --username <chess.com_username>

This module is intentionally thin — it wires together the API, engine,
and analyzer layers and formats the output for the terminal.  All heavy
lifting lives in the other modules so they can be reused programmatically.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional

from chess_analyzer import __version__
from chess_analyzer.api import get_recent_games
from chess_analyzer.engine import EngineError, StockfishEngine
from chess_analyzer.analyzer import analyze_game, GameAnalysis


# ═══════════════════════════════════════════════════════════════════════════
#  Terminal colours (ANSI escape codes)
# ═══════════════════════════════════════════════════════════════════════════
# We use lightweight ANSI codes rather than pulling in a dependency like
# ``colorama`` or ``rich``.  On Windows ≥ 10 the new terminal supports
# them natively; older terminals degrade gracefully to plain text.

class _Colors:
    """ANSI colour shortcuts."""
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    RED     = "\033[91m"
    CYAN    = "\033[96m"
    MAGENTA = "\033[95m"
    WHITE   = "\033[97m"

C = _Colors()

# Map classification labels → colour codes for pretty output.
CLASSIFICATION_COLORS: dict[str, str] = {
    "Best":        C.GREEN,
    "Excellent":   C.GREEN,
    "Good":        C.CYAN,
    "Inaccuracy":  C.YELLOW,
    "Mistake":     C.MAGENTA,
    "Blunder":     C.RED,
    "Forced Mate": C.RED,
}


# ═══════════════════════════════════════════════════════════════════════════
#  Display helpers
# ═══════════════════════════════════════════════════════════════════════════


def _print_banner() -> None:
    """Print an ASCII-art header to make the tool feel polished."""
    banner = rf"""
{C.CYAN}{C.BOLD}
   ♛  Chess Analyzer  v{__version__}
   ─────────────────────────────
   Open-source game analysis CLI
{C.RESET}"""
    print(banner)


def _print_game_header(analysis: GameAnalysis) -> None:
    """Print PGN header information (players, event, result)."""
    h = analysis.headers
    white = h.get("White", "?")
    black = h.get("Black", "?")
    result = h.get("Result", "*")
    event = h.get("Event", "")
    date = h.get("Date", "")

    print(f"\n{C.BOLD}{'═' * 60}{C.RESET}")
    print(f"  {C.WHITE}{C.BOLD}{white}{C.RESET}  vs  {C.WHITE}{C.BOLD}{black}{C.RESET}")
    if event:
        print(f"  {C.DIM}{event}  •  {date}{C.RESET}")
    print(f"  Result: {C.BOLD}{result}{C.RESET}")
    print(f"{C.BOLD}{'═' * 60}{C.RESET}")


def _print_move_table(analysis: GameAnalysis) -> None:
    """Print a formatted table of every move with CPL and classification."""
    # Table header.
    print(
        f"\n  {'#':>4}  {'Side':<6} {'Move':<8} "
        f"{'Before':>7} {'After':>7} {'CPL':>5}  {'Class':<14} {'Engine Best'}"
    )
    print(f"  {'─' * 75}")

    for m in analysis.moves:
        color = CLASSIFICATION_COLORS.get(m.classification, "")
        best_str = m.best_move_san or "—"

        print(
            f"  {m.move_number:>4}. {m.side:<6} {m.move_san:<8} "
            f"{m.score_before_cp:>7} {m.score_after_cp:>7} "
            f"{m.cpl:>5}  "
            f"{color}{m.classification:<14}{C.RESET} "
            f"{C.DIM}{best_str}{C.RESET}"
        )


def _print_summary(analysis: GameAnalysis) -> None:
    """Print per-side average CPL and classification breakdown."""
    print(f"\n{C.BOLD}── Summary ──{C.RESET}\n")

    for side in ("white", "black"):
        avg = analysis.average_cpl_for(side)
        counts = analysis.classification_counts(side)

        label = f"{'♔ White' if side == 'white' else '♚ Black'}"
        print(f"  {C.BOLD}{label}{C.RESET}  —  Avg CPL: {C.BOLD}{avg:.1f}{C.RESET}")

        # Sort categories in severity order for readability.
        order = [
            "Best", "Excellent", "Good",
            "Inaccuracy", "Mistake", "Blunder", "Forced Mate",
        ]
        parts = []
        for cat in order:
            n = counts.get(cat, 0)
            if n:
                col = CLASSIFICATION_COLORS.get(cat, "")
                parts.append(f"{col}{cat}: {n}{C.RESET}")
        if parts:
            print(f"    {' │ '.join(parts)}")
        print()


# ═══════════════════════════════════════════════════════════════════════════
#  Argument parsing
# ═══════════════════════════════════════════════════════════════════════════


def build_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="chess-analyzer",
        description="Analyse Chess.com games with Stockfish.",
    )

    # ── Data source (mutually exclusive) ─────────────────────────────
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "-u", "--username",
        help="Chess.com username whose recent games to analyse.",
    )
    source.add_argument(
        "-f", "--file",
        help="Path to a local PGN file to analyse.",
    )

    # ── Engine options ───────────────────────────────────────────────
    parser.add_argument(
        "--stockfish",
        default=None,
        help="Path to the Stockfish binary (auto-detected from PATH if omitted).",
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=18,
        help="Engine search depth in plies (default: 18).",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=1,
        help="CPU threads for Stockfish (default: 1).",
    )
    parser.add_argument(
        "--hash",
        type=int,
        default=128,
        dest="hash_mb",
        help="Hash table size in MiB (default: 128).",
    )

    # ── Fetch options ────────────────────────────────────────────────
    parser.add_argument(
        "-n", "--num-games",
        type=int,
        default=1,
        help="Number of recent games to fetch and analyse (default: 1).",
    )

    # ── Misc ─────────────────────────────────────────────────────────
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug-level logging.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    return parser


# ═══════════════════════════════════════════════════════════════════════════
#  Main entry-point
# ═══════════════════════════════════════════════════════════════════════════


def main(argv: Optional[list[str]] = None) -> int:
    """Parse CLI args, fetch/load games, run analysis, print results.

    Returns
    -------
    int
        Exit code (0 = success, 1 = error).
    """
    # Force UTF-8 encoding for Windows terminals to display chess pieces correctly.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(argv)

    # ── Logging setup ────────────────────────────────────────────────
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s | %(name)s | %(message)s",
    )

    _print_banner()

    # ── Collect PGN strings ──────────────────────────────────────────
    pgn_strings: list[str] = []

    if args.username:
        # Fetch from Chess.com API.
        try:
            games = get_recent_games(args.username, max_games=args.num_games)
        except Exception as exc:
            print(f"\n{C.RED}✖ Failed to fetch games: {exc}{C.RESET}")
            return 1

        if not games:
            print(f"\n{C.YELLOW}No games found for '{args.username}'.{C.RESET}")
            return 0

        for g in games:
            pgn = g.get("pgn")
            if pgn:
                pgn_strings.append(pgn)

        print(f"  Fetched {len(pgn_strings)} game(s) for {C.BOLD}{args.username}{C.RESET}.")

    elif args.file:
        # Read from local PGN file.
        try:
            with open(args.file, "r", encoding="utf-8") as fh:
                pgn_strings.append(fh.read())
        except FileNotFoundError:
            print(f"\n{C.RED}✖ File not found: {args.file}{C.RESET}")
            return 1

        print(f"  Loaded PGN from {C.BOLD}{args.file}{C.RESET}.")

    if not pgn_strings:
        print(f"\n{C.YELLOW}No PGN data to analyse.{C.RESET}")
        return 0

    # ── Start engine & analyse ───────────────────────────────────────
    try:
        with StockfishEngine(
            path=args.stockfish,
            depth=args.depth,
            threads=args.threads,
            hash_mb=args.hash_mb,
        ) as engine:
            for idx, pgn in enumerate(pgn_strings, start=1):
                print(f"\n{C.DIM}▸ Analysing game {idx}/{len(pgn_strings)}…{C.RESET}")

                analysis = analyze_game(pgn, engine, depth=args.depth)

                if not analysis.moves:
                    print(f"  {C.YELLOW}(No moves to analyse — skipping.){C.RESET}")
                    continue

                _print_game_header(analysis)
                _print_move_table(analysis)
                _print_summary(analysis)

    except EngineError as exc:
        print(f"\n{C.RED}✖ Engine error: {exc}{C.RESET}")
        return 1

    print(f"\n{C.GREEN}{C.BOLD}✔ Analysis complete.{C.RESET}\n")
    return 0


# Allow ``python -m chess_analyzer.cli …``
if __name__ == "__main__":
    sys.exit(main())
