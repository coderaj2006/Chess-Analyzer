<![CDATA[<div align="center">

# ♛ Chess Analyzer

**A modular, open-source CLI tool for analysing Chess.com games with Stockfish.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)](CONTRIBUTING.md)

</div>

---

## ✨ Features

| Feature | Description |
|---|---|
| **Chess.com Integration** | Fetch any player's recent games via the Chess.com Public API. |
| **Local PGN Support** | Analyse PGN files stored on your machine. |
| **Stockfish Engine** | Plug into any local Stockfish build via UCI. |
| **Per-Move Analysis** | Centipawn Loss (CPL) calculated for every half-move. |
| **Move Classification** | Each move graded: *Best, Excellent, Good, Inaccuracy, Mistake, Blunder, Forced Mate*. |
| **Beautiful CLI Output** | Colour-coded terminal tables with per-side summaries. |

---

## 📦 Project Structure

```
Chess-Analyzer/
├── chess_analyzer/
│   ├── __init__.py      # Package metadata
│   ├── api.py           # Chess.com HTTP client
│   ├── engine.py        # Stockfish UCI wrapper
│   ├── analyzer.py      # PGN parsing, CPL math, classification
│   └── cli.py           # CLI entrypoint
├── requirements.txt
├── README.md
└── .gitignore
```

Every module is **fully decoupled** — you can import `api`, `engine`, or `analyzer` independently in your own scripts.

---

## 🚀 Quick Start

### 1. Clone & install dependencies

```bash
git clone https://github.com/<your-username>/Chess-Analyzer.git
cd Chess-Analyzer
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Install Stockfish

Download the correct binary for your OS from **[stockfishchess.org/download](https://stockfishchess.org/download/)**.

Then **either**:
- Place it on your system `PATH` so the command `stockfish` is available, **or**
- Pass the path explicitly with `--stockfish /path/to/stockfish`.

### 3. Run

```bash
# Analyse the most recent game of a Chess.com user
python -m chess_analyzer.cli -u hikaru

# Analyse the last 5 games
python -m chess_analyzer.cli -u hikaru -n 5

# Analyse a local PGN file
python -m chess_analyzer.cli -f my_game.pgn

# Custom engine settings
python -m chess_analyzer.cli -u hikaru --depth 22 --threads 4 --hash 256
```

---

## ⚙️ CLI Options

| Flag | Default | Description |
|---|---|---|
| `-u, --username` | — | Chess.com username to fetch games for. |
| `-f, --file` | — | Path to a local `.pgn` file. |
| `-n, --num-games` | `1` | Number of recent games to analyse. |
| `--stockfish` | auto | Path to Stockfish binary. |
| `--depth` | `18` | Engine search depth (plies). |
| `--threads` | `1` | CPU threads for Stockfish. |
| `--hash` | `128` | Hash table size in MiB. |
| `-v, --verbose` | off | Enable debug logging. |

> **Note:** `--username` and `--file` are mutually exclusive.

---

## 🧮 How CPL & Classification Work

### Centipawn Loss (CPL)

For every move, the engine evaluates the position **before** and **after** the player's move. The difference — normalised to the moving player's perspective — is the **Centipawn Loss**:

```
White's CPL = eval_before − eval_after      (positive = lost advantage)
Black's CPL = eval_after  − eval_before      (positive = lost advantage)
```

Scores are clamped to `≥ 0` because *gaining* evaluation is not a loss.

### Mate Scores

Stockfish sometimes returns `Mate(n)` instead of centipawns. These are mapped to **±10 000 cp** so arithmetic stays clean.

### Classification Thresholds

| Category | CPL Range |
|---|---|
| **Best** | 0 |
| **Excellent** | 1 – 9 |
| **Good** | 10 – 29 |
| **Inaccuracy** | 30 – 79 |
| **Mistake** | 80 – 199 |
| **Blunder** | ≥ 200 |
| **Forced Mate** | Engine had a mate line; player deviated. |

---

## 🛠️ Using as a Library

```python
from chess_analyzer.api import get_recent_games
from chess_analyzer.engine import StockfishEngine
from chess_analyzer.analyzer import analyze_game

games = get_recent_games("hikaru", max_games=1)
pgn = games[0]["pgn"]

with StockfishEngine(depth=20) as engine:
    result = analyze_game(pgn, engine)
    print(f"Average CPL: {result.average_cpl:.1f}")
    for m in result.moves:
        print(f"  {m.move_number}. {m.move_san}  CPL={m.cpl}  [{m.classification}]")
```

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/my-feature`).
3. Commit with clear messages.
4. Open a Pull Request.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

<div align="center">
<sub>Built with ♟️ by the open-source community.</sub>
</div>
]]>
