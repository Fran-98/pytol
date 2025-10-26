from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
@dataclass
class TargetBias:
    """
    Numeric weights to tilt target selection.

    Positive values increase preference for the feature; 'water' acts as a
    penalty when > 0 (i.e., larger weight reduces score if point is water).
    """
    cities: float = 0.0   # weight for city density (0..1)
    roads: float = 0.0    # weight for being close to roads (~0 or 1)
    open: float = 0.0     # weight for open areas (1 - city density)
    water: float = 0.0    # penalty weight applied if near sea level


@dataclass
class TeamSpec:
    """
    Minimal force composition and posture for a side.

    Note: This remains abstract intentionally. Concrete unit templates and
    placements are decided downstream by the engine and map-aware policies.
    """
    name: str = "Allied"
    doctrine: str = "standard"  # e.g., "defense-in-depth", "raid"
    budget: int = 100000
    intent_tags: List[str] = field(default_factory=list)


@dataclass
class ProceduralMissionSpec:
    """
    Contract for the procedural engine input. This is the surface API a dynamic
    campaign engine will call.

    Required map context is provided either via map_id + vtol_directory or via
    an absolute map_path. Scenario metadata is kept minimal to avoid coupling.
    """
    # Scenario metadata
    scenario_id: str
    scenario_name: str
    description: str = ""
    vehicle: str = "AV-42C"

    # Map context
    map_id: str = ""
    vtol_directory: str = ""
    map_path: str = ""

    # Mission intent
    mission_type: str = "strike"  # e.g., strike|cas|sead|intercept|transport
    duration_minutes: int = 30
    difficulty: str = "normal"  # easy|normal|hard
    time_of_day: Optional[str] = None  # day|dusk|night|None=engine chooses
    weather: Optional[str] = None  # clear|windy|stormy|custom

    # Target selection (prefer legacy booleans or use a single bias object)
    prefer_cities: Optional[bool] = None      # legacy convenience flag
    prefer_roads: Optional[bool] = None       # legacy convenience flag
    prefer_open: Optional[bool] = None        # legacy convenience flag
    avoid_water: Optional[bool] = True        # legacy convenience flag
    target_bias: Optional[TargetBias] = None  # numeric weights override legacy flags when provided

    # Teams
    allied: TeamSpec = field(default_factory=lambda: TeamSpec(name="Allied"))
    enemy: TeamSpec = field(default_factory=lambda: TeamSpec(name="Enemy"))

    # Randomness and reproducibility
    seed: Optional[int] = None
    extra: Dict[str, object] = field(default_factory=dict)

    def resolve_map_args(self) -> Dict[str, str]:
        """Build the argument set for Mission(...) construction.

        Returns:
            Dict with vehicle, map_id or map_path, and vtol_directory keys.
        """
        args: Dict[str, str] = {"vehicle": self.vehicle}
        if self.map_path:
            args["map_path"] = self.map_path
        else:
            # Accept empty vtol_directory if VTOL_VR_DIR env is present; Mission handles it.
            args["map_id"] = self.map_id
            if self.vtol_directory:
                args["vtol_directory"] = self.vtol_directory
        return args
