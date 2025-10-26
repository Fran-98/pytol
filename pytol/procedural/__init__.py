"""
Procedural mission generation scaffolding for pytol.

This package provides high-level building blocks to assemble coherent,
terrain-aware VTOL VR missions while keeping a clean contract with a future
dynamic campaign engine.

Modules are intentionally lightweight and typed; most classes expose small,
clear interfaces and can be swapped out without breaking the facade.
"""

from .spec import ProceduralMissionSpec, TargetBias
from .engine import ProceduralMissionEngine
from .validation import (
    ProceduralGenerationError,
    InvalidTargetError,
    InvalidRouteError,
    InvalidSpawnLocationError,
)

__all__ = [
    "ProceduralMissionSpec",
    "ProceduralMissionEngine",
    "TargetBias",
    "ProceduralGenerationError",
    "InvalidTargetError",
    "InvalidRouteError",
    "InvalidSpawnLocationError",
]
