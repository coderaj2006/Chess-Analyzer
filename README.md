# ♔ Chess Analyzer

A modular, open-source CLI and Web tool for fetching and analysing Chess.com games with Stockfish.

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)

---

## ✨ Features

| Feature | Description |
| :--- | :--- |
| **Chess.com Integration** | Fetch any player's recent games via the Chess.com Public API. |
| **Local PGN Support** | Analyse PGN files stored directly on your machine. |
| **Stockfish Engine** | Plug into any local Stockfish build via the standard UCI protocol. |
| **Per-Move Analysis** | Centipawn Loss (CPL) calculated accurately for every single half-move. |
| **Move Classification** | Every move graded instantly: *Best, Excellent, Good, Inaccuracy, Mistake, Blunder, Forced Mate*. |
| **Dual Interfaces** | Choose between a beautifully color-coded terminal CLI or an interactive Web Dashboard. |

---

## 📦 Project Structure

Every module is **fully decoupled**—meaning you can import `api`, `engine`, or `analyzer` independently into your own custom Python scripts.

```text
Chess-Analyzer/
├── chess_analyzer/
│   ├── __init__.py      # Package metadata & version control
│   ├── api.py           # Chess.com HTTP connection-pooling client
│   ├── engine.py        # Stockfish UCI process wrapper & lifecycle manager
│   ├── analyzer.py      # PGN parsing, POV centipawn loss math, & classification
│   └── cli.py           # Multi-platform terminal user interface
├── app.py               # Layman-friendly Streamlit Web UI Dashboard
├── requirements.txt     # Third-party dependencies (chess, streamlit)
├── .gitignore           # Python & OS environment exclusions
└── README.md            # Project documentation
## 🚀 Quick Start

### 1. Clone & Install Dependencies

```bash
# Clone the repository
git clone https://github.com/YourUsername/Chess-Analyzer.git
cd Chess-Analyzer

# Set up a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

### 2. Setup Stockfish

Download the correct binary for your operating system from the [official Stockfish Downloads](https://stockfishchess.org/download/).

Either place it on your system's global `PATH` so the command `stockfish` is recognized natively, or pass its path explicitly using the `--stockfish` flag when running the app.

---

## 💻 Running the Interfaces

### 1. Web UI Dashboard (Recommended for Laymen)

Launch a beautiful, interactive web interface to easily visualize your games in a web browser:

```bash
streamlit run app.py
```

### 2. Command-Line Interface (CLI)

Run a lightning-fast analysis directly inside your favorite terminal:

```bash
# Analyse the most recent game of a Chess.com user
python -m chess_analyzer.cli -u hikaru

# Analyse the last 5 games of a user
python -m chess_analyzer.cli -u hikaru -n 5

# Analyse a local PGN file saved on your machine
python -m chess_analyzer.cli -f my_game.pgn

# Run analysis with customized engine hardware performance settings
python -m chess_analyzer.cli -u hikaru --depth 22 --threads 4 --hash 256
```

---

## ⚙️ CLI Options Reference

| Flag | Default | Description |
| :--- | :--- | :--- |
| `-u, --username` | — | Chess.com username whose recent games to analyse. |
| `-f, --file` | — | Path to a local `.pgn` file to load and analyse. |
| `-n, --num-games` | `1` | Total number of recent web games to fetch. |
| `--stockfish` | `auto` | Explicit system file path to your Stockfish binary. |
| `--depth` | `18` | Engine search depth configuration in plies. |
| `--threads` | `1` | Total CPU threads dedicated to the Stockfish process. |
| `--hash` | `128` | Memory buffer size allocated to the engine cache in MiB. |
| `-v, --verbose` | `False` | Enables system-level debug logging inside the console. |
