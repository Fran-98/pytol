__version__ = "0.2.0"

# --- Core Mission Building ---
from .parsers.vts_builder import Mission

# --- Object Creation Factories ---
from .classes.units import create_unit
from .classes.objectives import create_objective
from .classes.conditionals import create_conditional

# --- Essential Dataclasses ---
from .classes.mission_objects import (
    Waypoint,
    Path,
    Trigger,
    Base,
    BriefingNote,
    StaticObject,
    TimedEventGroup,
    TimedEventInfo,
    EventTarget,
    ParamInfo,
    GlobalValue,
    ConditionalAction,
    RandomEvent,
    RandomEventAction,
    EventSequence,
    SequenceEvent,
    Conditional
)

from .classes.conditionals import ConditionalTree

# --- Terrain Helpers ---
from .terrain.terrain_calculator import TerrainCalculator
from .terrain.mission_terrain_helper import MissionTerrainHelper

print(f"Pytol {__version__} loaded.")