from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SpawnController:
    """Determines when and how many reinforcements/QRF to spawn. Placeholder only."""
    difficulty: str = "normal"

    def qrf_probability(self, minute: int) -> float:
        if self.difficulty == "easy":
            return 0.05 if minute > 10 else 0.0
        if self.difficulty == "hard":
            return 0.2 if minute > 5 else 0.05
        return 0.1 if minute > 8 else 0.02
