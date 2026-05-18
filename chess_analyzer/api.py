"""
chess_analyzer.api
~~~~~~~~~~~~~~~~~~
HTTP client for the Chess.com Public API (PubAPI).

Chess.com requires every caller to send a descriptive ``User-Agent`` header;
requests that lack one are rejected with **HTTP 403**.  We set the header
once in the module-level ``SESSION`` so every subsequent call inherits it.

Reference: https://www.chess.com/news/view/published-data-api
"""

from __future__ import annotations

import logging
from typing import Any

import requests

# ---------------------------------------------------------------------------
# Module-level logger — consumers can control verbosity via standard logging.
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Persistent HTTP session.
#
# Why a session instead of raw ``requests.get``?
#   1.  Connection pooling — Chess.com API calls share the same host, so TCP
#       connections are reused automatically.
#   2.  Default headers — the mandatory ``User-Agent`` is set once and
#       inherited by every request.
# ---------------------------------------------------------------------------
SESSION = requests.Session()
SESSION.headers.update(
    {
        # Chess.com mandates a descriptive User-Agent string.  Generic ones
        # (e.g. "python-requests/2.x") trigger 403 Forbidden responses.
        "User-Agent": "ChessAnalyzer-OpenSource-Project"
    }
)

# ---------------------------------------------------------------------------
# Base URL — all PubAPI endpoints stem from this root.
# ---------------------------------------------------------------------------
BASE_URL = "https://api.chess.com/pub"


# ═══════════════════════════════════════════════════════════════════════════
#  Public helpers
# ═══════════════════════════════════════════════════════════════════════════


def get_player_profile(username: str) -> dict[str, Any]:
    """Fetch public profile data for *username*.

    Useful for a quick sanity check that the account exists before
    attempting to pull game archives.

    Parameters
    ----------
    username:
        Chess.com username (case-insensitive on their end).

    Returns
    -------
    dict
        JSON payload from ``/pub/player/{username}``.

    Raises
    ------
    requests.HTTPError
        On any non-2xx response (404 if user doesn't exist, 403 if
        User-Agent is missing, etc.).
    """
    url = f"{BASE_URL}/player/{username}"
    logger.info("Fetching profile for '%s' → %s", username, url)

    response = SESSION.get(url, timeout=15)

    # Raise immediately on HTTP errors so the caller gets a clear exception
    # instead of silently processing an error body.
    response.raise_for_status()

    return response.json()


def get_monthly_archives(username: str) -> list[str]:
    """Return a list of monthly archive URLs for *username*.

    Chess.com groups games by calendar month.  Each URL in the returned
    list points to an endpoint that yields all games for that month.

    Parameters
    ----------
    username:
        Chess.com username.

    Returns
    -------
    list[str]
        Ordered list of archive URLs (oldest → newest).
    """
    url = f"{BASE_URL}/player/{username}/games/archives"
    logger.info("Fetching archive list → %s", url)

    response = SESSION.get(url, timeout=15)
    response.raise_for_status()

    # The JSON shape is:  {"archives": ["https://…/2024/01", …]}
    data: dict[str, Any] = response.json()
    archives: list[str] = data.get("archives", [])

    logger.info("Found %d monthly archives for '%s'.", len(archives), username)
    return archives


def get_games_for_month(archive_url: str) -> list[dict[str, Any]]:
    """Download every game record from a single monthly archive URL.

    Each element in the returned list contains metadata **and** a ``pgn``
    key holding the raw PGN string of that game.

    Parameters
    ----------
    archive_url:
        A full URL as returned by :func:`get_monthly_archives`.

    Returns
    -------
    list[dict]
        Game records.  Each dict has at minimum ``white``, ``black``,
        ``pgn``, ``time_class``, ``url``, etc.
    """
    logger.info("Downloading games from %s", archive_url)

    response = SESSION.get(archive_url, timeout=30)
    response.raise_for_status()

    data: dict[str, Any] = response.json()
    games: list[dict[str, Any]] = data.get("games", [])

    logger.info("Retrieved %d games from archive.", len(games))
    return games


def get_recent_games(username: str, max_games: int = 10) -> list[dict[str, Any]]:
    """Convenience wrapper: fetch the most recent *max_games* for a player.

    Strategy
    --------
    1. Pull the full archive list.
    2. Walk backwards from the newest month, collecting games until we
       have enough (or run out of archives).

    This avoids downloading the *entire* history of prolific players.

    Parameters
    ----------
    username:
        Chess.com username.
    max_games:
        Maximum number of games to return.  Defaults to 10.

    Returns
    -------
    list[dict]
        Up to *max_games* game records, newest first.
    """
    archives = get_monthly_archives(username)

    if not archives:
        logger.warning("No archives found for '%s'.", username)
        return []

    collected: list[dict[str, Any]] = []

    # Walk archives in reverse-chronological order so we get the newest
    # games first without downloading every month.
    for archive_url in reversed(archives):
        month_games = get_games_for_month(archive_url)

        # Within a single month the API returns games in chronological
        # order, so reverse them to keep "newest first" semantics.
        collected.extend(reversed(month_games))

        if len(collected) >= max_games:
            break

    # Trim to the exact count requested.
    return collected[:max_games]
