"""Maze: labirent matrisinin tutulması, duvar doğrulaması, kalan yem sayımı."""

WALL = "#"
PELLET = "."
POWER = "o"
DOOR = "-"
EMPTY = " "

# Labirentin sol yarısı (orta sütun dahil). Sağ yarı aynalanarak üretilir,
# böylece labirent her zaman simetrik olur. 9. satırın uçları tüneldir.
_LEFT_HALF = [
    "###############",
    "#o.....#.......",
    "#.###..#.#####.",
    "#..............",
    "#.###.#.###.###",
    "#.....#...#....",
    "#####.###.#.###",
    "#####.#........",
    "#####.#.##.###-",
    "...........#   ",
    "#####.#.##.####",
    "#####.#........",
    "#.........#....",
    "#.###.###.#.###",
    "#o.............",
    "##.#.#.#####.##",
    "#....#.........",
    "#.#######.#####",
    "#..............",
    "###############",
]

PLAYER_START = (14, 14)
HOUSE_EXIT = (14, 7)      # kapının hemen üstü
HOUSE_CENTER = (14, 9)    # hayalet evinin içi


class Maze:
    PELLET_POINTS = 10
    POWER_POINTS = 50

    def __init__(self) -> None:
        self.grid: list[list[str]] = []
        self.width = self.height = 0
        self.remaining = 0
        self.reset()

    def reset(self) -> None:
        self.grid = [list(row + row[-2::-1]) for row in _LEFT_HALF]
        self.height = len(self.grid)
        self.width = len(self.grid[0])
        px, py = PLAYER_START
        self.grid[py][px] = EMPTY
        self.remaining = sum(c in (PELLET, POWER) for row in self.grid for c in row)

    def wrap(self, x: int, y: int) -> tuple[int, int]:
        """Yatay tünel geçişi: sol kenardan çıkan sağdan girer."""
        return x % self.width, y

    def cell(self, x: int, y: int) -> str:
        x, y = self.wrap(x, y)
        if not 0 <= y < self.height:
            return WALL
        return self.grid[y][x]

    def is_wall(self, x: int, y: int, allow_door: bool = False) -> bool:
        c = self.cell(x, y)
        if c == WALL:
            return True
        if c == DOOR:
            return not allow_door
        return False

    def eat(self, x: int, y: int) -> str | None:
        """Hücredeki yemi yer; yenen türü (PELLET/POWER) ya da None döner."""
        x, y = self.wrap(x, y)
        c = self.grid[y][x]
        if c in (PELLET, POWER):
            self.grid[y][x] = EMPTY
            self.remaining -= 1
            return c
        return None
