from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from pytol.terrain.mission_terrain_helper import MissionTerrainHelper


@dataclass
class ControlMap:
    """
    Computes a coarse "who controls where" field over the map.

    The implementation is intentionally deferred; this class exposes a minimal
    interface the rest of the engine can depend on without locking in a method
    (heuristic vs. learned vs. scripted).
    """
    helper: MissionTerrainHelper

    def control_at(self, x: float, z: float) -> float:
        """
        Returns a signed control score at (x,z):
        -1.0 = strongly enemy controlled, 0 = contested, +1.0 = strongly allied.

        Placeholder implementation returns 0.0.
        """
        _ = (x, z)
        return 0.0

    def nearest_frontline(self, x: float, z: float, max_radius: float = 50000) -> Tuple[float, float]:
        """Returns the nearest point on the estimated frontline to (x, z).

        Placeholder returns the query point.
        """
        return (x, z)
