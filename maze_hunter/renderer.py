"""TerminalRenderer: matrisi ANSI renk kodları ile renklendirip tek seferde terminale basar.

Her karede terminal boyutu okunur ve düzen (Layout) yeniden hesaplanır:
  * Labirent hücresi sığan en büyük w×h karakter bloğuna ölçeklenir
    (6×3, 4×2, 2×1, 1×1 ...); büyük terminalde oyun da büyür.
  * Satır yetmezse önce yardım satırı, sonra boşluk satırları gizlenir.
  * Oyun alanı yatay ve dikey olarak ortalanır.
  * Hiçbir düzen sığmazsa uyarı gösterilir (motor bu sırada oyunu dondurur).
"""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from .engine import seconds
from .ghost import GhostState
from .maze import DOOR, PELLET, POWER, WALL

if TYPE_CHECKING:
    from .engine import GameEngine
    from .maze import Maze

RESET = "\x1b[0m"
COLORS = {
    "red": "\x1b[91m",
    "magenta": "\x1b[95m",
    "cyan": "\x1b[96m",
    "green": "\x1b[92m",
    "yellow": "\x1b[93m",
    "blue": "\x1b[34m",
    "brightblue": "\x1b[94m",
    "white": "\x1b[97m",
    "dim": "\x1b[2;37m",
}

# Hücre genişliğine göre karo setleri: {genişlik: {ad: metin}}
GLYPHS = {
    2: {"wall": "██", "door": "──", "pellet": "· ", "power": "● ", "empty": "  ",
        "player": "◉ ", "ghost": "◆ ", "scared": "◇ ", "eyes": "∘∘"},
    1: {"wall": "█", "door": "─", "pellet": "·", "power": "●", "empty": " ",
        "player": "◉", "ghost": "◆", "scared": "◇", "eyes": "∘"},
}

HELP_TEXT = "Yön tuşları / WASD: hareket   P: duraklat   Q: çık"
HELP_SHORT = "←↑↓→/WASD  P:dur  Q:çık"


@dataclass(frozen=True)
class Layout:
    cols: int
    rows: int
    cell_w: int        # bir labirent hücresinin genişliği (karakter)
    cell_h: int        # bir labirent hücresinin yüksekliği (satır)
    left: int          # sol boşluk (karakter)
    top: int           # üst boşluk (satır)
    gaps: bool         # başlık/durum çevresinde boş satır
    show_help: bool


def _terminal_size(stream) -> tuple[int, int]:
    try:
        size = os.get_terminal_size(stream.fileno())
    except (AttributeError, OSError, ValueError):
        size = shutil.get_terminal_size()
    return size.columns, size.lines


def _scales(max_h: int = 12):
    """Büyükten küçüğe aday hücre boyutları (genişlik, yükseklik).

    Terminal karakteri yaklaşık 1:2 oranlı olduğundan kare görünüm için w = 2h.
    """
    for h in range(max_h, 0, -1):
        yield 2 * h, h
        yield 2 * h - 1, h


def compute_layout(maze: Maze, cols: int, rows: int) -> Layout | None:
    """Verilen terminal boyutu için en büyük sığan düzeni seçer; sığmazsa None."""
    for cell_w, cell_h in _scales():
        width = maze.width * cell_w
        if width > cols:
            continue
        # (gaps, show_help) — en zengin seçenekten en sadeye
        for gaps, show_help in ((True, True), (False, True), (True, False), (False, False)):
            height = maze.height * cell_h + 2 + (2 if gaps else 0) + (1 if show_help else 0)
            if height <= rows:
                return Layout(cols, rows, cell_w, cell_h, (cols - width) // 2,
                              (rows - height) // 2, gaps, show_help)
    return None


def min_size(maze: Maze) -> tuple[int, int]:
    return maze.width, maze.height + 2


class TerminalRenderer:
    def __init__(self, stream=None, size_fn: Callable[[], tuple[int, int]] | None = None) -> None:
        self.out = stream or sys.stdout
        self._size_fn = size_fn or (lambda: _terminal_size(self.out))
        self._last_size: tuple[int, int] | None = None
        self.layout: Layout | None = None
        self._resized = False

    def __enter__(self) -> TerminalRenderer:
        # Alternatif ekran tamponu + imleci gizle + temizle
        self.out.write("\x1b[?1049h\x1b[?25l\x1b[2J")
        self.out.flush()
        return self

    def __exit__(self, *exc) -> None:
        self.out.write(RESET + "\x1b[?25h\x1b[?1049l")
        self.out.flush()

    # --- Düzen ------------------------------------------------------------------

    def update_layout(self, maze: Maze) -> Layout | None:
        """Terminal boyutunu okuyup düzeni günceller. Oyun sığmıyorsa None döner."""
        size = self._size_fn()
        if size != self._last_size:
            self._resized = True
            self._last_size = size
            self.layout = compute_layout(maze, *size)
        return self.layout

    # --- Çizim ------------------------------------------------------------------

    @staticmethod
    def _block(w: int, h: int, glyph: str, color: str, fill: bool = False) -> list[str]:
        """w×h boyutlu bir karo: ya tamamen dolu ya da ortasında tek glif."""
        if fill:
            return [color + glyph * w + RESET] * h
        rows = [" " * w] * h
        cx, cy = (w - 1) // 2, (h - 1) // 2
        rows[cy] = " " * cx + color + glyph + RESET + " " * (w - cx - 1)
        return rows

    @staticmethod
    def _sprite(w: int, h: int, color: str, eyes: bool = False) -> list[str]:
        """Büyük ölçekte figürler: kenarlarda 1 sütun boşluklu dolu dikdörtgen."""
        pad = 1 if w >= 4 else 0
        inner = w - 2 * pad
        body = " " * pad + color + "█" * inner + RESET + " " * pad
        if not eyes:
            return [body] * h
        eye = (" " * pad + color + ("°" + " " * max(0, inner - 2) + "°")[:inner]
               + RESET + " " * pad)
        return [eye] + [" " * w] * (h - 1)

    def _tiles(self, lay: Layout, engine: GameEngine) -> tuple[dict, dict]:
        """(labirent karoları, figür karoları); her karo cell_h satırlık liste."""
        w, h = lay.cell_w, lay.cell_h
        power_on = (engine.tick // 8) % 2 == 0
        blink = engine.fright_ticks < seconds(2) and (engine.tick // 6) % 2 == 0
        scared = COLORS["white"] if blink else COLORS["brightblue"]

        if h == 1:
            g = GLYPHS[2] if w >= 2 else GLYPHS[1]
            pad = " " * (w - len(g["wall"]))

            def one(key: str, color: str) -> list[str]:
                return [color + g[key] + RESET + pad]

            maze = {
                WALL: [COLORS["blue"] + "█" * w + RESET],
                DOOR: [COLORS["magenta"] + "─" * w + RESET],
                PELLET: one("pellet", COLORS["dim"]),
                POWER: one("power", COLORS["white"]) if power_on else [" " * w],
            }
            player = one("player", COLORS["yellow"])
            ghost = {c: one("ghost", COLORS[c]) for c in COLORS}
            fright, eaten = one("scared", scared), one("eyes", COLORS["white"])
        else:
            maze = {
                WALL: self._block(w, h, "█", COLORS["blue"], fill=True),
                DOOR: self._block(w, h, "─", COLORS["magenta"], fill=False),
                PELLET: self._block(w, h, "·", COLORS["dim"]),
                POWER: self._block(w, h, "●", COLORS["white"]) if power_on else [" " * w] * h,
            }
            maze[DOOR][(h - 1) // 2] = COLORS["magenta"] + "─" * w + RESET
            player = self._sprite(w, h, COLORS["yellow"])
            ghost = {c: self._sprite(w, h, COLORS[c]) for c in COLORS}
            fright, eaten = self._sprite(w, h, scared), self._sprite(w, h, COLORS["white"], eyes=True)

        entities: dict[tuple[int, int], list[str]] = {}
        p = engine.player
        entities[(p.x, p.y)] = player
        for gh in engine.ghosts:
            if gh.state == GhostState.FRIGHTENED:
                entities[(gh.x, gh.y)] = fright
            elif gh.state == GhostState.EATEN:
                entities[(gh.x, gh.y)] = eaten
            else:
                entities[(gh.x, gh.y)] = ghost[gh.color]
        return maze, entities

    def _header(self, engine: GameEngine, width: int) -> str:
        lives = engine.player.lives
        y, r = COLORS["yellow"], RESET
        variants = [
            (f"  LABİRENT AVCISI   SKOR {engine.score:>6}   SEVİYE {engine.level}   CAN {'◉ ' * lives}",
             f"{y}  LABİRENT AVCISI{r}   SKOR {engine.score:>6}   SEVİYE {engine.level}   "
             f"CAN {y}{'◉ ' * lives}{r}"),
            (f"SKOR {engine.score}  SV {engine.level}  CAN {'◉' * lives}",
             f"SKOR {engine.score}  SV {engine.level}  CAN {y}{'◉' * lives}{r}"),
            (f"{engine.score} L{engine.level} {'◉' * lives}",
             f"{engine.score} L{engine.level} {y}{'◉' * lives}{r}"),
        ]
        for plain, colored in variants:
            if len(plain) <= width:
                return colored
        return variants[-1][0][:width]

    @staticmethod
    def _fit(text: str, width: int) -> str:
        return text if len(text) <= width else text[: max(0, width - 1)] + "…"

    def _too_small(self, engine: GameEngine) -> str:
        cols, rows = self._last_size or (0, 0)
        need_c, need_r = min_size(engine.maze)
        msgs = [
            "Terminal çok küçük",
            f"şu an {cols}x{rows}",
            f"en az {need_c}x{need_r} gerekli",
            "(oyun duraklatıldı)",
        ]
        msgs = [self._fit(m, cols) for m in msgs][: max(1, rows)]
        top = max(0, (rows - len(msgs)) // 2)
        lines = [""] * top + [" " * max(0, (cols - len(m)) // 2) + m for m in msgs]
        return "\x1b[H" + "\x1b[K\n".join(lines) + "\x1b[K\x1b[J"

    def compose(self, engine: GameEngine) -> str:
        lay = self.layout
        if lay is None:
            return self._too_small(engine)

        maze = engine.maze
        maze_w = maze.width * lay.cell_w
        maze_tiles, entities = self._tiles(lay, engine)
        empty = [" " * lay.cell_w] * lay.cell_h

        body = [self._header(engine, maze_w)]
        if lay.gaps:
            body.append("")
        for y, row in enumerate(maze.grid):
            blocks = [entities.get((x, y)) or maze_tiles.get(c, empty) for x, c in enumerate(row)]
            for sub in range(lay.cell_h):
                body.append("".join(b[sub] for b in blocks))
        if lay.gaps:
            body.append("")

        status = "DURAKLATILDI — P: devam" if engine.paused else engine.message
        body.append(f"{COLORS['yellow']}{self._fit(status, maze_w)}{RESET}")
        if lay.show_help:
            help_text = HELP_TEXT if len(HELP_TEXT) <= maze_w else HELP_SHORT
            body.append(f"{COLORS['dim']}{self._fit(help_text, maze_w)}{RESET}")

        pad = " " * lay.left
        lines = [""] * lay.top + [pad + line for line in body]
        # Satır sonlarını temizle; tüm kareyi tek write() çağrısıyla bas
        return "\x1b[H" + "\x1b[K\n".join(lines) + "\x1b[K\x1b[J"

    def draw(self, engine: GameEngine) -> None:
        if self.layout is None and self._last_size is None:
            self.update_layout(engine.maze)
        frame = self.compose(engine)
        if self._resized:
            frame = "\x1b[2J" + frame   # boyut değişince eski kalıntıları sil
            self._resized = False
        self.out.write(frame)
        self.out.flush()
