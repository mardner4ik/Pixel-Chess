# Pixel Chess

A minimalist, mobile-first chess game built with [Kivy](https://kivy.org/). Choose White or Black and play against a local search-based opponent, with legal move hints, drag-and-drop pieces, light and dark themes, a varied original soundtrack, and move sounds.

## Features

- Standard chess rules and game-end detection powered by `python-chess`
- Local opponent using iterative deepening, alpha-beta search, and a transposition table
- Responsive touch controls, legal move hints, and animated moves
- Custom white and black chess piece artwork shipped as PNG assets with SVG source files
- Choose to play as White or Black at the start of each game
- Original 128-second ambient music, move sound effects, and a saved master volume setting
- Light and dark appearance follows the system theme

## Run on desktop

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python main.py
```

Choose White or Black when a game opens. Tap a piece to show its legal moves, then tap a destination. Use the top-right menu to adjust the master volume or open About. After a game ends, **Restart** lets you choose your side again.

## Build for Android

This project uses Buildozer. Install its Android build dependencies, then run:

```bash
buildozer android debug
```

The app configuration is in [`buildozer.spec`](buildozer.spec). Generated build files and APKs are excluded from version control.

## Project layout

```text
main.py                    app entry point
chess_app/core/engine.py   chess rules and local opponent search
chess_app/ui/game_screen.py board, interaction, menus, and dialogs
chess_app/ui/theme.kv      Kivy interface styles
chess_app/ui/system_theme.py system light/dark theme detection
assets/ambient.wav         original 128-second ambient loop
assets/move.wav            soft move sound effect
assets/pieces/             twelve piece images (PNG plus SVG source)
```

## License

Pixel Chess is distributed under the GNU General Public License v3.0 only (GPL-3.0-only). See [LICENSE](LICENSE).

## Authors and credits

- **[@mardner4ik](https://github.com/mardner4ik)** — project author and maintainer.
- **OpenAI Codex** — AI development assistance and original chess-piece artwork, soundtrack, and move sound created for this project at the maintainer's direction.
- **GitHub** — the GitHub mark in About is GitHub's brand asset.
- The app uses [Kivy](https://kivy.org/) for its interface and [python-chess](https://python-chess.readthedocs.io/) for chess rules.
