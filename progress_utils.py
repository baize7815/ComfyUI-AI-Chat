"""Small compatibility wrapper around ComfyUI's progress bar."""

from __future__ import annotations


class ProgressTracker:
    def __init__(self, total: int) -> None:
        self.total = max(1, int(total))
        self.current = 0
        self._bar = None
        try:
            from comfy.utils import ProgressBar

            self._bar = ProgressBar(self.total)
        except Exception:
            self._bar = None

    def advance(self, amount: int = 1) -> None:
        self.current = min(self.total, self.current + max(0, int(amount)))
        if self._bar is None:
            return
        try:
            self._bar.update_absolute(self.current, self.total)
        except Exception:
            self._bar = None
