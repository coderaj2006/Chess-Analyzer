"""
Chess Analyzer — A modular, open-source Chess Game Analysis toolkit.

This package exposes four core submodules:
  • api       – HTTP client for the Chess.com Public API.
  • engine    – Stockfish UCI engine wrapper.
  • analyzer  – PGN parsing, CPL calculation, and move classification.
  • cli       – Command-line interface entrypoint.

Typical quick-start usage:
    python -m chess_analyzer.cli --username <chess.com_user>
"""

__version__ = "0.1.0"
__author__ = "Chess Analyzer Contributors"
