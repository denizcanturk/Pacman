"""Player: konum (x, y), anlık hız vektörü, yön tamponu ve can yönetimi."""

from .maze import Maze, PLAYER_START

Direction = tuple[int, int]


class Player:
    def __init__(self, lives: int = 3) -> None:
        self.lives = lives
        self.reset_position()

    def reset_position(self) -> None:
        self.x, self.y = PLAYER_START
        self.prev = (self.x, self.y)
        self.velocity: Direction = (0, 0)       # anlık hız vektörü
        self.buffered: Direction | None = None  # yön tamponu

    def queue_direction(self, direction: Direction) -> None:
        """İstenen yön, duvar izin verdiği ilk anda uygulanmak üzere saklanır."""
        self.buffered = direction

    def step(self, maze: Maze) -> None:
        if self.buffered is not None:
            bx, by = self.buffered
            if not maze.is_wall(self.x + bx, self.y + by):
                self.velocity = self.buffered
                self.buffered = None
        dx, dy = self.velocity
        if (dx, dy) != (0, 0) and not maze.is_wall(self.x + dx, self.y + dy):
            self.x, self.y = maze.wrap(self.x + dx, self.y + dy)

    def lose_life(self) -> bool:
        """Bir can düşer; oyun bittiyse True döner."""
        self.lives -= 1
        return self.lives <= 0
