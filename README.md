# Maze Hunter

A maze-chase game that runs entirely in your terminal. It is written in pure Python with no third-party dependencies. Eat every pellet in the maze while four ghosts with different personalities hunt you down. When you grab a power pellet, the hunters become the hunted.

```
  LABİRENT AVCISI   SKOR    170   SEVİYE 1   CAN ◉ ◉ ◉
██████████████████████████████████████████████████████████
██● · · · · · ██◇ · · · · · · · · · · · · ██· · · · · ● ██
██· ██████· · ██· ██████████· ██████████· ██· · ██████· ██
██· · · · · · · · · · · ◆ · · · · · · · · · · · · · · · ██
██· ██████· ██· ██████· ██████████· ██████· ██· ██████· ██
██· · · · · ██· · · ██· · · · · · · ██· · · ██· · · · · ██
██████████· ██████· ██· ██████████· ██· ██████· ██████████
██████████· ██· · · · · · · · · · · · · · · ██· ██████████
██████████· ██· ████· ██████──██████◆ ████· ██· ██████████
· · · · · · · · · · · ██        ◆ ██· · · · · · · · · · ·
██████████· ██· ████· ██████████████· ████· ██· ██████████
██████████· ██· · · · · · · · · · · · · · · ██· ██████████
██· · · · · · · · · ██· · · · · · · ██· · · · · · · · · ██
██· ██████· ██████· ██· ██████████· ██· ██████· ██████· ██
██◉                           · · · · · · · · · · · · ● ██
████· ██· ██· ██████████· ██████· ██████████· ██· ██· ████
██· · · · ██· · · · · · · · · · · · · · · · · ██· · · · ██
██· ██████████████· ██████████████████· ██████████████· ██
██· · · · · · · · · · · · · · · · · · · · · · · · · · · ██
██████████████████████████████████████████████████████████
```

> The in-game text is in Turkish (*SKOR* = score, *SEVİYE* = level, *CAN* = lives).

## Features

- **Responsive rendering:** the game measures the terminal on every frame and scales the maze to fill it. Each maze cell is drawn as a block of 1×1, 2×1, 4×2, 6×3 characters or larger, whichever fits. You can resize the window while playing. If the terminal gets too small, the game pauses and shows a message until there is enough room again.
- **Ghost AI built on a state machine:** each ghost switches between *Scatter*, *Chase*, *Frightened* and *Eaten* states on a timed schedule. In *Chase* mode, each ghost picks its target in its own way:
  | Ghost | Chase behaviour |
  |---|---|
  | Kor (red) | Targets the player's current tile |
  | Pusu (magenta) | Ambushes 4 tiles ahead of the player |
  | Kıskaç (cyan) | Works with the red ghost to trap the player from both sides |
  | Ürkek (green) | Chases from a distance but runs back to its corner when it gets close |
- **Smooth controls:** you can press a turn before you reach a corner. The input is kept in a buffer and applied as soon as the path is open.
- **Non-blocking input:** a background thread reads the keyboard in cbreak mode, so the game loop never waits for a key press.
- **Flicker-free output:** each frame is built as a single ANSI string and written in one call. The game draws on the alternate screen buffer, so your terminal is restored when you quit.
- **Increasing difficulty:** every level makes the player and the ghosts faster and shortens the power-pellet time.

## Requirements

- Python **3.10+**
- A Unix-like terminal (Linux, macOS, or WSL on Windows). The input handler uses `termios`/`tty`, which native Windows does not have.
- A terminal at least **29×22** characters. Bigger terminals show a bigger maze.

## Getting started

```bash
git clone https://github.com/<your-username>/<repo-name>.git
cd <repo-name>
python3 -m maze_hunter
```

You can also use the launcher script, which works from any directory:

```bash
./MazeHunter.sh
```

Run the command from the repository root, not from inside `maze_hunter/`. The game is a package and uses relative imports.

## Controls

| Key | Action |
|---|---|
| Arrow keys / `W` `A` `S` `D` | Move |
| `P` / `Space` | Pause / resume |
| `R` | Restart (after game over) |
| `Q` | Quit |

## Scoring

| Item | Points |
|---|---|
| Pellet `·` | 10 |
| Power pellet `●` | 50 |
| Ghosts eaten during one power pellet | 200 → 400 → 800 → 1600 |

You start with 3 lives. Clear every pellet to advance to the next level.

## Project structure

```
maze_hunter/
├── __main__.py        Entry point (python -m maze_hunter)
├── engine.py          GameEngine: tick loop, collisions, score and level tracking
├── maze.py            Maze: grid storage, wall checks, remaining-pellet count
├── player.py          Player: position, velocity vector, direction buffer, lives
├── ghost.py           Ghost: FSM states and target-tile selection
├── renderer.py        TerminalRenderer: responsive layout and ANSI frame output
└── input_handler.py   InputHandler: thread-based, non-blocking keyboard input
```

### How it works

- **Game loop:** `GameEngine.run()` ticks 30 times per second. Each tick it reads the queued input, updates the world, and redraws the screen. Characters move one tile every *N* ticks, so speed is set by tick intervals and stays the same regardless of frame timing.
- **Collisions:** the engine checks collisions after the player moves and again after the ghosts move. It also catches a player and a ghost passing through each other in the same tick.
- **Ghost movement:** at each tile a ghost picks the open direction closest to its target. It never reverses unless it has to. Frightened ghosts pick a random direction instead.
- **Maze:** only the left half is stored in `maze.py`. The right half is a mirror copy, so the maze is always symmetric. The row with open ends at the sides is a wrap-around tunnel.

## Tips

- If the maze looks small, make the terminal **taller**. Rows limit the scale more than columns do: the next scale step (4×2) needs at least 42 rows.
- Shrinking the font (`Ctrl` + `-` in most terminals) gives you more rows and columns, so the maze is drawn at a larger scale.
