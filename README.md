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
```
