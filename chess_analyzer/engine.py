"""
chess_analyzer.engine
~~~~~~~~~~~~~~~~~~~~~
Stockfish UCI engine wrapper.

Download Stockfish from: https://stockfishchess.org/download/
Place it on PATH or pass the binary path explicitly.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Optional

import chess
import chess.engine

logger = logging.getLogger(__name__)

DEFAULT_DEPTH: int = 18
DEFAULT_TIME_LIMIT: float = 5.0


class EngineError(Exception):
    """Raised when the engine cannot be started or crashes."""


class StockfishEngine:
    """Context-manager wrapper around a Stockfish UCI process.

    Usage::

        with StockfishEngine() as sf:
            info = sf.evaluate_board(board)

    Parameters
    ----------
    path : str or Path, optional
        Path to Stockfish binary.  Auto-detected from PATH if omitted.
    depth : int
        Default search depth (plies).
    time_limit : float
        Default time cap per analysis (seconds).
    threads : int
        UCI ``Threads`` option.
    hash_mb : int
        UCI ``Hash`` option (MiB).
    """

    def __init__(
        self,
        path: Optional[str | Path] = None,
        depth: int = DEFAULT_DEPTH,
        time_limit: float = DEFAULT_TIME_LIMIT,
        threads: int = 1,
        hash_mb: int = 128,
    ) -> None:
        self.depth = depth
        self.time_limit = time_limit
        self._threads = threads
        self._hash_mb = hash_mb

        # Resolve binary path
        if path is not None:
            self._binary = Path(path)
            if not self._binary.is_file():
                raise EngineError(
                    f"Stockfish binary not found at '{self._binary}'.\n"
                    "Download from https://stockfishchess.org/download/"
                )
        else:
            resolved = shutil.which("stockfish")
            if resolved is None:
                raise EngineError(
                    "Could not find 'stockfish' on PATH.\n"
                    "Download from https://stockfishchess.org/download/"
                )
            self._binary = Path(resolved)

        logger.info("Stockfish binary → %s", self._binary)
        self._engine: Optional[chess.engine.SimpleEngine] = None

    def __enter__(self) -> "StockfishEngine":
        try:
            self._engine = chess.engine.SimpleEngine.popen_uci(
                str(self._binary)
            )
        except Exception as exc:
            raise EngineError(f"Failed to start Stockfish: {exc}") from exc

        self._engine.configure(
            {"Threads": self._threads, "Hash": self._hash_mb}
        )
        logger.info("Stockfish started (depth=%d).", self.depth)
        return self

    def __exit__(self, *args) -> None:
        self.quit()

    # ── Analysis ─────────────────────────────────────────────────────

    def evaluate_board(
        self,
        board: chess.Board,
        depth: Optional[int] = None,
        time_limit: Optional[float] = None,
    ) -> chess.engine.InfoDict:
        """Static evaluation of a position."""
        self._assert_running()
        assert self._engine is not None
        return self._engine.analyse(
            board,
            chess.engine.Limit(
                depth=depth or self.depth,
                time=time_limit or self.time_limit,
            ),
        )

    def get_best_move(
        self,
        board: chess.Board,
        depth: Optional[int] = None,
        time_limit: Optional[float] = None,
    ) -> tuple[chess.Move, chess.engine.InfoDict]:
        """Best move + evaluation in one call."""
        self._assert_running()
        assert self._engine is not None
        result = self._engine.play(
            board,
            chess.engine.Limit(
                depth=depth or self.depth,
                time=time_limit or self.time_limit,
            ),
            info=chess.engine.INFO_SCORE,
        )
        return result.move, result.info  # type: ignore[return-value]

    # ── Lifecycle ────────────────────────────────────────────────────

    def quit(self) -> None:
        if self._engine is not None:
            try:
                self._engine.quit()
            except chess.engine.EngineTerminatedError:
                pass
            finally:
                self._engine = None
                logger.info("Stockfish terminated.")

    def _assert_running(self) -> None:
        if self._engine is None:
            raise EngineError("Engine not running. Use as context manager.")
