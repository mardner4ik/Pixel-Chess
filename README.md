# Pixel Chess

A minimalist, mobile-first chess game built with [Kivy](https://kivy.org/). Choose White or Black and play against a local search-based opponent, with legal move hints, drag-and-drop pieces, light and dark themes, licensed piano music, and move sounds.

## Features

- Standard chess rules and game-end detection powered by `python-chess`
- Local opponent using iterative deepening, alpha-beta search, and a transposition table, with Easy, Normal, and Hard strengths
- The bot waits a random 4–15 seconds before each move; Easy deliberately chooses weaker moves
- Optional 3, 5, and 10 minute clocks
- Undo the latest turn, save and resume an unfinished game
- Four board palettes and two piece artwork styles
- Responsive touch controls, legal move hints, and animated moves
- Google Sans Flex typography inspired by the Pixel interface
- Main menu with Play, Settings, and About; Multiplayer is shown as a future feature
- Android 12+ wallpaper-derived system accent colors, plus selectable palettes and a fallback for older Android and desktop
- Custom white and black chess piece artwork shipped as PNG assets with SVG source files
- Choose to play as White or Black at the start of each game
- Five selectable Kevin MacLeod soundtracks and a move sound effect, with a saved master volume setting
- Choose the opponent difficulty before choosing your side
- Light and dark appearance follows the system theme

## Run on desktop

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python main.py
```

From the main menu, choose **Play → Singleplayer**, select the opponent strength, then choose White or Black. The **Advanced** section offers optional clock controls and a choice between a 4–15 second thinking delay or instant bot moves. The clock is off by default. During a thinking delay, a live countdown appears in the game status. Tap a piece to show its legal moves, then tap a destination, or drag a piece to a square. The in-game menu provides Settings, About, **Save**, Undo, and **Resign**. Save writes a resumable game and confirms with a brief toast. Settings controls volume, soundtrack, board and piece styles, and accent colors. An unfinished game can be resumed from the main menu. After a game ends, choose **Main menu** or **Restart**. Multiplayer is visible but disabled while it is being developed.

## Build for Android

This project uses Buildozer. Install its Android build dependencies, then run:

```bash
buildozer android debug
```

The app configuration is in [`buildozer.spec`](buildozer.spec). Generated build files and APKs are excluded from version control.

## Project layout

```text
main.py                    app entry point
chess_app/core/engine.py     chess rules and local opponent search
chess_app/ui/game_screen.py  screen lifecycle, menus, and game interaction
chess_app/ui/board.py        board drawing, gestures, and move animation
chess_app/ui/dialogs.py      settings and modal dialogs
chess_app/ui/session.py      clocks, save/resume, and undo
chess_app/ui/widgets.py      shared buttons and cards
chess_app/ui/theme.kv        Kivy interface styles
chess_app/ui/system_theme.py system light/dark theme detection
assets/ambient.wav           Friday Morning piano soundtrack
assets/music/                four additional selectable soundtracks
assets/move.wav              soft move sound effect
assets/fonts/                Google Sans Flex UI font and SIL Open Font License
assets/pieces/               pixel and vector piece artwork
```

## License

Pixel Chess is distributed under the GNU General Public License v3.0 only (GPL-3.0-only). See [LICENSE](LICENSE).

## Authors and credits

- **[@mardner4ik](https://github.com/mardner4ik)** — project author and maintainer.
- **Kevin MacLeod** — composer of all five selectable soundtracks, provided under CC BY 4.0 with attribution below.
- **OpenAI Codex** — AI development assistance; original chess-piece artwork and move sound were created for the project at the maintainer's direction.
- **GitHub** — the GitHub mark in About is GitHub's brand asset.
- **Google Fonts contributors** — Google Sans Flex, distributed under SIL Open Font License 1.1; see [`assets/fonts/OFL.txt`](assets/fonts/OFL.txt).
- The app uses [Kivy](https://kivy.org/) for its interface and [python-chess](https://python-chess.readthedocs.io/) for chess rules.

Music attribution: “Friday Morning” ([source](https://incompetech.com/music/royalty-free/index.html?Search=Search&isrc=USUAN1100224)), “Easy Lemon” ([source](https://incompetech.com/music/royalty-free/index.html?Search=Search&isrc=USUAN1200076)), “Immersed” ([source](https://incompetech.com/music/royalty-free/index.html?Search=Search&isrc=USUAN1600010)), “Morning” ([source](https://incompetech.com/music/royalty-free/index.html?Search=Search&isrc=USUAN2300003)), and “Evening” ([source](https://incompetech.com/music/royalty-free/index.html?Search=Search&isrc=USUAN2300002)) by Kevin MacLeod ([incompetech.com](https://incompetech.com/)), licensed under [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/). The source MP3s were converted to mono 22.05 kHz WAV for app playback; the compositions are unchanged.
