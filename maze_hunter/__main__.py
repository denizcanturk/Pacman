import sys

from .engine import GameEngine
from .input_handler import InputHandler
from .renderer import TerminalRenderer


def main() -> int:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("Bu oyun etkileşimli bir terminal gerektirir.", file=sys.stderr)
        return 1
    engine = GameEngine(TerminalRenderer(), InputHandler())
    try:
        engine.run()
    except KeyboardInterrupt:
        pass
    print(f"Skor: {engine.score}  Seviye: {engine.level}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
