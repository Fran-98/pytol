from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass
class TimingModel:
    """Simple pacing model selecting ingress/egress leg lengths and event cadence."""
    duration_minutes: int = 30

    def ingress_egress_distances(self) -> Tuple[float, float]:
        """
        Derive approximate ingress/egress distances (meters) from target area.
        Placeholder uses a rough linear mapping.
        """
        # 1 minute ≈ 15 km at 900 km/h; use a conservative 8 km/min for mixed profiles
        total = max(10, self.duration_minutes) * 8000.0
        ingress = total * 0.4
        egress = total * 0.3
        return ingress, egress

    def event_spacing_seconds(self) -> int:
        """Return suggested seconds between minor beats (radio/info/spawns)."""
        if self.duration_minutes <= 20:
            return 90
        if self.duration_minutes <= 40:
            return 120
        return 150
