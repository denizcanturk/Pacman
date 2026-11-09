"""InputHandler: bloklamayan, thread tabanlı klavye girdisi yakalama."""

from __future__ import annotations

import os
import queue
import select
import sys
import termios
import threading
import tty

ESCAPE_SEQUENCES = {
    b"\x1b[A": "up", b"\x1b[B": "down", b"\x1b[C": "right", b"\x1b[D": "left",
    b"\x1bOA": "up", b"\x1bOB": "down", b"\x1bOC": "right", b"\x1bOD": "left",
}
KEYS = {
    b"w": "up", b"s": "down", b"a": "left", b"d": "right",
    b"p": "pause", b" ": "pause", b"q": "quit", b"r": "restart",
}


class InputHandler:
    def __init__(self, stream=None) -> None:
        self.stream = stream or sys.stdin
        self.events: queue.Queue[str] = queue.Queue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._old_attrs = None

    def __enter__(self) -> InputHandler:
        self.fd = self.stream.fileno()
        self._old_attrs = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)  # satır tamponu ve yankı kapalı
        self._thread = threading.Thread(target=self._reader, name="input", daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=0.5)
        if self._old_attrs is not None:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self._old_attrs)

    def _reader(self) -> None:
        while not self._stop.is_set():
            ready, _, _ = select.select([self.fd], [], [], 0.05)
            if ready:
                data = os.read(self.fd, 64)
                if not data:
                    self.events.put("quit")
                    return
                for cmd in self.parse(data):
                    self.events.put(cmd)

    @staticmethod
    def parse(data: bytes) -> list[str]:
        cmds: list[str] = []
        i = 0
        while i < len(data):
            seq = data[i:i + 3]
            if seq in ESCAPE_SEQUENCES:
                cmds.append(ESCAPE_SEQUENCES[seq])
                i += 3
                continue
            key = data[i:i + 1].lower()
            if key in KEYS:
                cmds.append(KEYS[key])
            elif key == b"\x03":  # Ctrl+C (cbreak'te ISIG açık ama yine de)
                cmds.append("quit")
            i += 1
        return cmds

    def poll(self) -> list[str]:
        """Biriken komutları bloklamadan döndürür."""
        cmds = []
        while True:
            try:
                cmds.append(self.events.get_nowait())
            except queue.Empty:
                return cmds
