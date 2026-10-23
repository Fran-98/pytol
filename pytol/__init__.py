__version__ = "0.7.0"  # single source: pyproject reads it via [tool.hatch.version]

# --- Core Mission Building ---
from .parsers.vts_builder import Mission, NATO_PHONETIC_ALPHABET
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
    ConditionalBlock,
    RandomEvent,
    RandomEventAction,
    EventSequence,
    SequenceEvent,
    WeatherPreset,
    Conditional
)

from .classes.conditionals import ConditionalTree

# --- Terrain Helpers ---
from .terrain.terrain_calculator import TerrainCalculator
from .terrain.mission_terrain_helper import MissionTerrainHelper

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

# --- Static Prefabs API ---
from .resources.resources import (
    get_static_prefabs_database,
    list_static_prefabs,
    list_static_prefab_names,
    get_static_prefab,
)

from .misc.logger import create_logger
_logger = create_logger(verbose=False, name="pytol")
_logger.info(f"Pytol {__version__} loaded.")

# --- Visualization (optional extras; stubs raise a helpful ImportError when the backend is missing) ---
from .visualization import Map2DVisualizer, save_mission_map, MissionVisualizer, TerrainVisualizer
