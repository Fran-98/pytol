__version__ = "0.2.0"

# --- Core Mission Building ---
from .parsers.vts_builder import Mission
from .parsers.vtc_builder import Campaign

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

# --- Procedural Engine (scaffold) ---
from .procedural import ProceduralMissionSpec, ProceduralMissionEngine

# --- Equipment System ---
from .resources.equipment import (
    EquipmentBuilder,
    LoadoutPresets,
    get_available_vehicles,
    get_equipment_for_vehicle,
    search_equipment,
    EquipmentNotFoundError,
    InvalidLoadoutError
)

from .misc.logger import create_logger
_logger = create_logger(verbose=False, name="pytol")
_logger.info(f"Pytol {__version__} loaded.")

# --- Visualization (Optional) ---
# Import visualization if pyvista is available
try:
    from .visualization import MissionVisualizer, TerrainVisualizer
    _viz_available = True
except ImportError:
    _viz_available = False
    MissionVisualizer = None
    TerrainVisualizer = None

if _viz_available:
    _logger.info("  -> Visualization module available (pyvista detected)")
