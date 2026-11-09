"""GameEngine: ana döngü (tick), çarpışma denetimleri, skor ve seviye takibi."""

from __future__ import annotations

import random
import time

from .ghost import Ghost, GhostState, target_ahead, target_direct, target_pincer, target_wary
from .maze import HOUSE_EXIT, POWER, Maze
from .player import Player

TICK_RATE = 30  # saniyedeki tick sayısı

DIRECTION_COMMANDS = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}

# (mod, saniye) — son CHASE süresiz devam eder
MODE_SCHEDULE = [
    (GhostState.SCATTER, 7),
    (GhostState.CHASE, 20),
    (GhostState.SCATTER, 7),
    (GhostState.CHASE, 20),
    (GhostState.SCATTER, 5),
    (GhostState.CHASE, None),
]


def seconds(s: float) -> int:
    return int(s * TICK_RATE)


class GameEngine:
    def __init__(self, renderer=None, input_handler=None, seed: int | None = None) -> None:
        self.renderer = renderer
        self.input = input_handler
        self.rng = random.Random(seed)
        self.running = True
        self.new_game()

    # --- Oyun durumu --------------------------------------------------------

    def new_game(self) -> None:
        self.maze = Maze()
        self.player = Player(lives=3)
        self.ghosts = [
            Ghost("Kor", "red", HOUSE_EXIT, (26, -3), target_direct, 0),
            Ghost("Pusu", "magenta", (14, 9), (2, -3), target_ahead, seconds(2)),
            Ghost("Kıskaç", "cyan", (12, 9), (28, 21), target_pincer, seconds(5)),
            Ghost("Ürkek", "green", (16, 9), (0, 21), target_wary, seconds(8)),
        ]
        self.score = 0
        self.level = 1
        self.tick = 0
        self.paused = False
        self.game_over = False
        self._start_round()

    def _start_round(self) -> None:
        """Ölüm ya da yeni seviye sonrası konumları ve zamanlayıcıları sıfırlar."""
        self.player.reset_position()
        for g in self.ghosts:
            g.reset()
        self.round_tick = 0
        self.mode_index = 0
        self.mode_ticks_left = self._mode_duration(0)
        self.fright_ticks = 0
        self.ghost_combo = 0
        self.freeze_ticks = seconds(2)
        self.message = "HAZIR!"

    def _mode_duration(self, index: int) -> int | None:
        secs = MODE_SCHEDULE[index][1]
        return None if secs is None else seconds(secs)

    @property
    def current_mode(self) -> GhostState:
        return MODE_SCHEDULE[self.mode_index][0]

    # Hız: her N tick'te bir hücre ilerleme (küçük = hızlı)
    @property
    def player_interval(self) -> int:
        return max(3, 5 - (self.level - 1) // 2)

    def ghost_interval(self, g: Ghost) -> int:
        if g.state == GhostState.EATEN:
            return 2
        if g.state == GhostState.FRIGHTENED:
            return self.player_interval * 2
        return max(3, 6 - (self.level - 1) // 2)

    @property
    def fright_duration(self) -> int:
        return seconds(max(2.0, 8.0 - (self.level - 1)))

    # --- Girdi ----------------------------------------------------------------

    def handle_command(self, cmd: str) -> None:
        if cmd == "quit":
            self.running = False
        elif cmd == "pause" and not self.game_over:
            self.paused = not self.paused
        elif cmd == "restart" and self.game_over:
            self.new_game()
        elif cmd in DIRECTION_COMMANDS and not self.paused:
            self.player.queue_direction(DIRECTION_COMMANDS[cmd])

    # --- Tick -------------------------------------------------------------------

    def update(self) -> None:
        """Tek bir oyun tick'i."""
        if self.paused or self.game_over:
            return
        self.tick += 1
        if self.freeze_ticks > 0:
            self.freeze_ticks -= 1
            if self.freeze_ticks == 0:
                self.message = ""
            return

        self.round_tick += 1
        self._update_timers()

        self.player.prev = (self.player.x, self.player.y)
        for g in self.ghosts:
            g.prev = (g.x, g.y)

        if self.tick % self.player_interval == 0:
            self.player.step(self.maze)
            self._eat_at_player()
        if self._check_collisions():
            return

        for g in self.ghosts:
            if not g.released and self.round_tick >= g.release_delay:
                g.released = True
            if g.released and self.tick % self.ghost_interval(g) == 0:
                g.step(self.maze, self.player, self.ghosts, self.rng)
        if self._check_collisions():
            return

        if self.maze.remaining == 0:
            self._next_level()

    def _update_timers(self) -> None:
        if self.fright_ticks > 0:
            # Korku sürerken SCATTER/CHASE zamanlayıcısı durur
            self.fright_ticks -= 1
            if self.fright_ticks == 0:
                for g in self.ghosts:
                    g.calm()
            return
        if self.mode_ticks_left is not None:
            self.mode_ticks_left -= 1
            if self.mode_ticks_left <= 0:
                self.mode_index += 1
                self.mode_ticks_left = self._mode_duration(self.mode_index)
        for g in self.ghosts:
            g.set_mode(self.current_mode)

    def _eat_at_player(self) -> None:
        eaten = self.maze.eat(self.player.x, self.player.y)
        if eaten is None:
            return
        if eaten == POWER:
            self.score += Maze.POWER_POINTS
            self.fright_ticks = self.fright_duration
            self.ghost_combo = 0
            for g in self.ghosts:
                g.frighten()
        else:
            self.score += Maze.PELLET_POINTS

    def _check_collisions(self) -> bool:
        """Çarpışmaları denetler; tur sona erdiyse (ölüm) True döner."""
        p = self.player
        ppos = (p.x, p.y)
        for g in self.ghosts:
            gpos = (g.x, g.y)
            crossed = gpos == p.prev and g.prev == ppos and gpos != ppos
            if gpos != ppos and not crossed:
                continue
            if g.state == GhostState.FRIGHTENED:
                g.get_eaten()
                self.score += 200 * 2 ** self.ghost_combo
                self.ghost_combo += 1
            elif g.state != GhostState.EATEN:
                self._player_died()
                return True
        return False

    def _player_died(self) -> None:
        if self.player.lose_life():
            self.game_over = True
            self.message = "OYUN BİTTİ — R: yeniden, Q: çık"
        else:
            self._start_round()

    def _next_level(self) -> None:
        self.level += 1
        self.maze.reset()
        self._start_round()
        self.message = f"SEVİYE {self.level}"

    # --- Ana döngü -------------------------------------------------------------

    def run(self) -> None:
        frame = 1.0 / TICK_RATE
        with self.input, self.renderer:
            while self.running:
                started = time.perf_counter()
                for cmd in self.input.poll():
                    self.handle_command(cmd)
                # Terminal oyuna yetmeyecek kadar küçükse dünya donar
                if self.renderer.update_layout(self.maze) is not None:
                    self.update()
                self.renderer.draw(self)
                remaining = frame - (time.perf_counter() - started)
                if remaining > 0:
                    time.sleep(remaining)
