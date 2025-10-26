from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PacingEngine:
    """Maps timing heuristics to mission beats. Placeholder only."""
    event_spacing_seconds: int

    def next_beat_at(self, start_time_s: int, n: int) -> int:
        """Return the timestamp for the nth beat after start_time_s."""
        return start_time_s + n * self.event_spacing_seconds
