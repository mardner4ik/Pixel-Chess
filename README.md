# Pixel Chess

A minimalist, mobile-first chess game built with [Kivy](https://kivy.org/). Choose White or Black and play against a local search-based opponent, with legal move hints, drag-and-drop pieces, light and dark themes, licensed piano music, and move sounds.

## Features

- Standard chess rules and game-end detection powered by `python-chess`
- Local opponent using iterative deepening, alpha-beta search, and a transposition table
- Responsive touch controls, legal move hints, and animated moves
- Google Sans Flex typography inspired by the Pixel interface
- Main menu with Singleplayer, Settings, and About; Multiplayer is shown as a future feature
- Custom white and black chess piece artwork shipped as PNG assets with SVG source files
- Choose to play as White or Black at the start of each game
- Kevin MacLeod's 3:30 piano track, a move sound effect, and a saved master volume setting
- Light and dark appearance follows the system theme

## Run on desktop

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python main.py
```

From the main menu, choose **Singleplayer**, then select White or Black. Tap a piece to show its legal moves, then tap a destination. The in-game menu provides Settings, About, and a shortcut back to the main menu. Multiplayer is visible but disabled while it is being developed. After a game ends, **Restart** lets you choose your side again.

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
assets/ambient.wav         licensed 3:30 piano soundtrack
assets/move.wav            soft move sound effect
assets/fonts/              Google Sans Flex UI font and SIL Open Font License
assets/pieces/             twelve piece images (PNG plus SVG source)
```

## License

Pixel Chess is distributed under the GNU General Public License v3.0 only (GPL-3.0-only). See [LICENSE](LICENSE).

## Authors and credits

- **[@mardner4ik](https://github.com/mardner4ik)** — project author and maintainer.
- **Kevin MacLeod** — composer of “Friday Morning,” the piano track used in the game. It is provided under CC BY 4.0 with attribution below.
- **OpenAI Codex** — AI development assistance; original chess-piece artwork and move sound were created for the project at the maintainer's direction.
- **GitHub** — the GitHub mark in About is GitHub's brand asset.
- **Google Fonts contributors** — Google Sans Flex, distributed under SIL Open Font License 1.1; see [`assets/fonts/OFL.txt`](assets/fonts/OFL.txt).
- The app uses [Kivy](https://kivy.org/) for its interface and [python-chess](https://python-chess.readthedocs.io/) for chess rules.

Music attribution: “Friday Morning” Kevin MacLeod ([incompetech.com](https://incompetech.com/music/royalty-free/index.html?Search=Search&isrc=USUAN1100224)), licensed under [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/). The source MP3 was converted to mono 22.05 kHz WAV for app playback; the composition is unchanged.
