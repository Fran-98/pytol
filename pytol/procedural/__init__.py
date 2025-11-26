"""
Procedural mission generation system for pytol.

This package provides a seeded, reproducible pipeline for generating
coherent, terrain-aware VTOL VR missions:
- MissionDirector: Grammar-based narrative planning
- PCG: Procedural content generation with intelligent placement
- WorldState: In-memory mission state database
- CompilerAdapter: Conversion from WorldState to Mission objects
"""

from .mission_director import MissionConfig, MissionPlan, PlanObjective, MissionDirector
from .pcg import PCG
from .world_state import WorldState
from .compiler_adapter import apply_world_state_to_mission
from .unit_templates import UnitLibrary
from .grammar import Grammar

__all__ = [
    "MissionConfig",
    "MissionPlan",
    "PlanObjective",
    "MissionDirector",
    "PCG",
    "WorldState",
    "apply_world_state_to_mission",
    "UnitLibrary",
    "Grammar",
]
