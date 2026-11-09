"""Ghost: FSM durumları (Chase/Scatter/Frightened/Eaten), hedef koordinat seçimi."""

from __future__ import annotations

import random
from enum import Enum
from typing import Callable, TYPE_CHECKING

from .maze import HOUSE_CENTER, HOUSE_EXIT, Maze

if TYPE_CHECKING:
    from .player import Player

# Eşitlik durumunda öncelik sırası: yukarı, sol, aşağı, sağ
DIRECTIONS = [(0, -1), (-1, 0), (0, 1), (1, 0)]


class GhostState(Enum):
    SCATTER = "scatter"
    CHASE = "chase"
    FRIGHTENED = "frightened"
    EATEN = "eaten"


Strategy = Callable[["Ghost", "Player", list["Ghost"]], tuple[int, int]]


def _dist2(a: tuple[int, int], b: tuple[int, int]) -> int:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


# --- Kovalama stratejileri (CHASE durumundaki hedef seçimi) -----------------

def target_direct(g: Ghost, p: Player, ghosts: list[Ghost]) -> tuple[int, int]:
    """Doğrudan oyuncunun bulunduğu hücreyi hedefler."""
    return p.x, p.y


def target_ahead(g: Ghost, p: Player, ghosts: list[Ghost]) -> tuple[int, int]:
    """Oyuncunun 4 hücre önünü keser."""
    dx, dy = p.velocity
    return p.x + 4 * dx, p.y + 4 * dy


def target_pincer(g: Ghost, p: Player, ghosts: list[Ghost]) -> tuple[int, int]:
    """İlk hayaletle oyuncunun önündeki noktayı kıskaca alır."""
    dx, dy = p.velocity
    ax, ay = p.x + 2 * dx, p.y + 2 * dy
    lead = ghosts[0]
    return 2 * ax - lead.x, 2 * ay - lead.y


def target_wary(g: Ghost, p: Player, ghosts: list[Ghost]) -> tuple[int, int]:
    """Uzaktayken kovalar, 8 hücreden yakına gelince köşesine kaçar."""
    if _dist2((g.x, g.y), (p.x, p.y)) > 64:
        return p.x, p.y
    return g.scatter_target


class Ghost:
    def __init__(
        self,
        name: str,
        color: str,
        start: tuple[int, int],
        scatter_target: tuple[int, int],
        strategy: Strategy,
        release_delay: int,
    ) -> None:
        self.name = name
        self.color = color
        self.start = start
        self.scatter_target = scatter_target
        self.strategy = strategy
        self.release_delay = release_delay  # tick cinsinden evden çıkış gecikmesi
        self.reset()

    def reset(self) -> None:
        self.x, self.y = self.start
        self.prev = (self.x, self.y)
        self.direction = (0, -1)
        self.state = GhostState.SCATTER
        self.resume_state = GhostState.SCATTER
        self.in_house = self.start != HOUSE_EXIT
        self.released = not self.in_house

    # --- FSM geçişleri ----------------------------------------------------

    def _reverse(self) -> None:
        self.direction = (-self.direction[0], -self.direction[1])

    def set_mode(self, mode: GhostState) -> None:
        """Global SCATTER/CHASE zamanlayıcısından gelen mod değişikliği."""
        self.resume_state = mode
        if self.state in (GhostState.FRIGHTENED, GhostState.EATEN):
            return
        if self.state != mode:
            self.state = mode
            if not self.in_house:
                self._reverse()

    def frighten(self) -> None:
        if self.state == GhostState.EATEN or self.in_house:
            return
        if self.state != GhostState.FRIGHTENED:
            self._reverse()
        self.state = GhostState.FRIGHTENED

    def calm(self) -> None:
        if self.state == GhostState.FRIGHTENED:
            self.state = self.resume_state

    def get_eaten(self) -> None:
        self.state = GhostState.EATEN

    # --- Hedef seçimi ve hareket -------------------------------------------

    def choose_target(self, player: Player, ghosts: list[Ghost]) -> tuple[int, int]:
        if self.state == GhostState.EATEN:
            return HOUSE_CENTER
        if self.in_house:
            return HOUSE_EXIT
        if self.state == GhostState.SCATTER:
            return self.scatter_target
        return self.strategy(self, player, ghosts)

    def step(self, maze: Maze, player: Player, ghosts: list[Ghost], rng: random.Random) -> None:
        allow_door = self.in_house or self.state == GhostState.EATEN
        reverse = (-self.direction[0], -self.direction[1])

        def open_(d: tuple[int, int]) -> bool:
            return not maze.is_wall(self.x + d[0], self.y + d[1], allow_door)

        options = [d for d in DIRECTIONS if d != reverse and open_(d)]
        if not options:
            options = [reverse] if open_(reverse) else []
        if not options:
            return

        if self.state == GhostState.FRIGHTENED:
            choice = rng.choice(options)
        else:
            tx, ty = self.choose_target(player, ghosts)
            choice = min(options, key=lambda d: _dist2((self.x + d[0], self.y + d[1]), (tx, ty)))

        self.direction = choice
        self.x, self.y = maze.wrap(self.x + choice[0], self.y + choice[1])

        if self.in_house and (self.x, self.y) == HOUSE_EXIT:
            self.in_house = False
        elif self.state == GhostState.EATEN and (self.x, self.y) == HOUSE_CENTER:
            # Eve döndü: yeniden canlan ve tekrar dışarı çık
            self.state = self.resume_state
            self.in_house = True
            self.direction = (0, -1)
