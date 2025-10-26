from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional


@dataclass
class RandomizedChoices:
    mission_type: str
    difficulty: str
    time_of_day: Optional[str]
    weather: Optional[str]
    duration_minutes: int


class Randomizer:
    """
    Seeded random chooser for mission attributes. Use to ensure reproducible
    results across runs when a seed is provided.
    """

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    def choose(self,
               mission_type: Optional[str],
               difficulty: Optional[str],
               time_of_day: Optional[str],
               weather: Optional[str],
               duration_minutes: Optional[int]) -> RandomizedChoices:
        mission_type = self._pick(mission_type, ["strike", "cas", "sead", "intercept", "transport"])  # type: ignore
        difficulty = self._pick(difficulty, ["easy", "normal", "hard"])  # type: ignore
        time_of_day = self._pick(time_of_day, ["day", "dusk", "night"], allow_none=True)  # type: ignore
        weather = self._pick(weather, [None, "clear", "windy", "stormy"])  # type: ignore
        duration_minutes = duration_minutes or self.rng.choice([20, 25, 30, 35, 40])
        return RandomizedChoices(mission_type, difficulty, time_of_day, weather, duration_minutes)

    def _pick(self, value, options, allow_none: bool = False):
        if value in (None, "", "random"):
            choice = self.rng.choice(options)
            if allow_none and choice is None:
                return None
            return choice
        return value
