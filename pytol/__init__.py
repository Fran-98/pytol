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
    get_playable_vehicles,
    get_equipment_for_vehicle,
    search_equipment,
    EquipmentNotFoundError,
    InvalidLoadoutError
)

# --- Base Spawn Points ---
from .resources.base_spawn_points import (
    get_available_bases,
    select_spawn_point,
    get_spawn_points,
    get_reference_points,
    compute_world_from_base,
    get_spawn_by_category
)

from .misc.logger import create_logger
_logger = create_logger(verbose=False, name="pytol")
_logger.info(f"Pytol {__version__} loaded.")

# --- Visualization (Optional) ---
# Import 2D visualization (matplotlib)
try:
    from .visualization import Map2DVisualizer, save_mission_map
    _viz2d_available = True
except ImportError:
    _viz2d_available = False
    Map2DVisualizer = None
    save_mission_map = None

# Import 3D visualization (pyvista)
try:
    from .visualization import MissionVisualizer, TerrainVisualizer
    _viz3d_available = True
except ImportError:
    _viz3d_available = False
    MissionVisualizer = None
    TerrainVisualizer = None

if _viz2d_available:
    _logger.info("  -> 2D Visualization available (matplotlib detected)")
if _viz3d_available:
    _logger.info("  -> 3D Visualization available (pyvista detected)")
