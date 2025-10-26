from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from pytol.terrain.mission_terrain_helper import MissionTerrainHelper


@dataclass
class ThreatMap:
    """
    Encodes radar/SAM/AAA coverage and general hazard density, masking with LoS
    using MissionTerrainHelper as needed.
    """
    helper: MissionTerrainHelper

    def hazard_at(self, x: float, z: float, altitude_agl: float = 100.0) -> float:
        """
        Returns a hazard score [0..1] at (x,z,altitude).

        Placeholder returns 0.0.
        """
        _ = (x, z, altitude_agl)
        return 0.0

    def safe_point_near(self, x: float, z: float, radius: float = 5000) -> Tuple[float, float]:
        """Find a nearby lower-hazard point within radius. Placeholder passthrough."""
        return (x, z)
