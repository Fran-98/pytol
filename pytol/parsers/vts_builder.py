"""
Core module for constructing and saving VTOL VR mission files (.vts).
Includes automatic ID management for linked objects.
"""

import os
import shutil
from dataclasses import fields, is_dataclass
from typing import Dict, List, Any, Optional, Union

# --- Pytol Class Imports ---
from pytol.classes.conditionals import Conditional
from pytol.classes.units import Unit
from pytol.classes.objectives import Objective
from pytol.classes.mission_objects import (
    EventTarget, ParamInfo, Path, Trigger,
    Waypoint, StaticObject, Base, BriefingNote,
    TimedEventGroup, TimedEventInfo, GlobalValue, 
    ConditionalAction, EventSequence, SequenceEvent,
    RandomEvent
)
from pytol.classes.actions import GlobalValueActions
from pytol.terrain.mission_terrain_helper import MissionTerrainHelper
from pytol.terrain.terrain_calculator import TerrainCalculator
from pytol.classes.units import UNIT_CLASS_TO_ACTION_CLASS
from pytol.misc.logger import create_logger

# --- Constants ---
from pytol.classes.conditionals import CLASS_TO_ID

# --- VTS Formatting Helpers ---
# (_format_value, _format_vector, _format_point_list, _format_id_list, _format_block remain the same)
def _format_value(val: Any) -> str:
    """Helper function to format Python values into VTS-compatible strings."""
    if val is None: return "null"
    if isinstance(val, bool): return str(val)
    if val == "null": return "null"
    if isinstance(val, str): return val
    if isinstance(val, (int, float)): return str(val)
    return str(val)

def _format_vector(vec: List[float]) -> str:
    """Format a 3-element list as a VTS vector string."""
    formatted = [f"{v}".replace('e', 'E') for v in vec]
    return f"({formatted[0]}, {formatted[1]}, {formatted[2]})"

def _format_point_list(points: List[List[float]]) -> str:
    """Formats a list of vector points into a VTS-compatible string."""
    return ";".join([_format_vector(p) for p in points])

def _format_id_list(ids: List[Any]) -> str:
    """Formats a list of IDs into a VTS-compatible string."""
    return ";".join(map(str, ids))

def _format_block(name: str, content_str: str, indent_level: int = 1) -> str:
    """Helper function to format a VTS block with correct indentation."""
    indent = "\t" * indent_level
    eol = "\n"
    if not content_str.strip():
        return f"{indent}{name}{eol}{indent}{{{eol}{indent}}}{eol}"
    return f"{indent}{name}{eol}{indent}{{{eol}{content_str}{indent}}}{eol}"

def _snake_to_camel(snake_str: str) -> str:
    """Converts a snake_case string to camelCase."""
    components = snake_str.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])

# --- Main Mission Class ---

class Mission:
    """
    Main class for building VTOL VR missions (.vts), handling object linking and ID generation.
    """
    def __init__(self,
                 scenario_name: str,
                 scenario_id: str,
                 description: str,
                 vehicle: str = "AV-42C",
                 map_id: str = "",
                 map_path: str = "",
                 vtol_directory: str = '',
                 verbose: bool = True,
                 strict: bool = False):
        """Initializes a new VTOL VR Mission.
        
        Args:
            strict: If True, validate mission integrity before saving.
        """
        self.scenario_name = scenario_name
        self.scenario_id = scenario_id
        self.scenario_description = description if description else ""
        self.vehicle = vehicle
        self.verbose = verbose
        self.strict = strict
        
        # Initialize logger
        self.logger = create_logger(verbose=verbose, name="Mission")

        # --- Map Handling --- (No changes needed here)
        if map_path:
            self.map_path = map_path
            self.map_id = os.path.basename(map_path)
        elif map_id and os.getenv('VTOL_VR_DIR'):
            self.map_path = os.path.join(os.getenv('VTOL_VR_DIR'), "CustomMaps", map_id)
            self.map_id = map_id
        elif map_id and vtol_directory:
                self.map_path = os.path.join(vtol_directory, "CustomMaps", map_id)
                self.map_id = map_id
        else:
            raise ValueError("Map information could not be resolved.")

        self.tc = TerrainCalculator(self.map_id, self.map_path, vtol_directory, verbose=verbose)
        self.helper = MissionTerrainHelper(self.tc, verbose=verbose)

        # --- Default Game Properties --- (No changes needed here)
        self.game_version = "1.12.6f1"
        self.campaign_id = ""
        self.campaign_order_idx = -1
        self.multiplayer = False
        self.allowed_equips = "gau-8;m230;h70-x7;h70-4x4;h70-x19;mk82x1;mk82x2;mk82x3;mk82HDx1;mk82HDx2;mk82HDx3;agm89x1;gbu38x1;gbu38x2;gbu38x3;gbu39x3;gbu39x4u;cbu97x1;hellfirex4;maverickx1;maverickx3;cagm-6;sidewinderx1;sidewinderx2;sidewinderx3;iris-t-x1;iris-t-x2;iris-t-x3;sidearmx1;sidearmx2;sidearmx3;marmx1;av42_gbu12x1;av42_gbu12x2;av42_gbu12x3;42c_aim9ex2;42c_aim9ex1;"
        self.forced_equips = ";;;;;;;"  # Forced equipment slots (semicolon-separated)
        self.force_equips = False
        self.norm_forced_fuel = 1
        self.equips_configurable = True
        self.base_budget = 100000
        self.is_training = False
        self.infinite_ammo = False
        self.inf_ammo_reload_delay = 5
        self.fuel_drain_mult = 1
        self.rtb_wpt_id = ""
        self.refuel_wpt_id = ""
        self.bullseye_id: Optional[int] = None
        
        # Multiplayer-specific properties
        self.mp_player_count = 2
        self.auto_player_count = True
        self.override_allied_player_count = 0
        self.override_enemy_player_count = 0
        self.score_per_death_a = 0
        self.score_per_death_b = 0
        self.score_per_kill_a = 0
        self.score_per_kill_b = 0
        self.mp_budget_mode = "Life"  # or "Shared"
        self.rtb_wpt_id_b = ""
        self.refuel_wpt_id_b = ""
        self.separate_briefings = False
        self.base_budget_b = 100000
        
        # Environment properties
        self.env_name = ""
        self.selectable_env = False
        self.wind_dir = 0
        self.wind_speed = 0
        self.wind_variation = 0
        self.wind_gusts = 0
        self.default_weather = 0
        self.custom_time_of_day = 11
        self.override_location = False
        self.override_latitude = 0
        self.override_longitude = 0
        self.month = 1
        self.day = 1
        self.year = 2024
        self.time_of_day_speed = 1
        self.qs_mode = "Anywhere"
        self.qs_limit = -1

        # --- Mission Data Lists/Dicts ---
        self.units: List[Dict] = [] # Stores dicts: {'unit_obj': Unit, 'unitInstanceID': int, ...}
        self.paths: List[Path] = []
        self.waypoints: List[Waypoint] = []
        self.trigger_events: List[Trigger] = []
        self.objectives: List[Objective] = []
        self.static_objects: List[StaticObject] = []
        self._static_object_next_id = 0 # Static object IDs are just their index
        self.briefing_notes: List[BriefingNote] = []
        self.bases: List[Base] = [Base(id=0, team='Allied'), Base(id=1, team='Allied')]
        self.conditionals: Dict[str, Conditional] = {} # Keyed by assigned string ID
        self.unit_groups: Dict[str, Dict[str, List[int]]] = {}
        self.resource_manifest: Dict[str, str] = {}
        self.timed_event_groups: List[Any] = []
        self.timed_event_groups: List[TimedEventGroup] = []

        # --- Internal ID Management ---
        self._id_counters: Dict[str, int] = {
            "Waypoint": 0, "Path": 0, "Trigger": 0,
            "Objective": 0, "Conditional": 0,

            # Units use instanceID, Bases use user ID, StaticObjects use index
        }
        # Maps Python object ID (id(obj)) to assigned VTS string ID
        self._waypoints_map: Dict[int] = {}
        self._paths_map: Dict[int] = {}
        self._conditionals_map: Dict[int, str] = {}
        # Triggers and Objectives use user-provided integer IDs, map int ID to object
        self._triggers_map: Dict[int, Trigger] = {}
        self._objectives_map: Dict[int, Objective] = {}

        self.global_values: Dict[str, GlobalValue] = {} # Keyed by name
        self.conditional_actions: List[ConditionalAction] = []
        self._id_counters["ConditionalAction"] = 0

        self.event_sequences: List[EventSequence] = []
        self.random_events: List[RandomEvent] = []

    # ========== Equipment Helper Methods ==========
    
    def set_allowed_equips_for_vehicle(self, vehicle_name: Optional[str] = None):
        """
        Automatically populate allowed_equips based on the vehicle from the equipment database.
        
        Args:
            vehicle_name: Vehicle name (e.g., "F/A-26B"). If None, uses self.vehicle.
        
        Example:
            mission.set_allowed_equips_for_vehicle()  # Uses mission's vehicle
            mission.set_allowed_equips_for_vehicle("AV-42C")  # Override
        """
        from pytol.resources.equipment import get_equipment_for_vehicle
        
        vehicle = vehicle_name or self.vehicle
        try:
            equips = get_equipment_for_vehicle(vehicle)
            self.allowed_equips = ";".join(equips) + ";"
            self.logger.info(f"✓ Set {len(equips)} allowed equipment items for {vehicle}")
        except KeyError as e:
            self.logger.warning(f"{e}")
    
    def set_forced_equips(self, equip_list: List[str]):
        """
        Set forced equipment loadout.
        
        Args:
            equip_list: List of equipment IDs (one per hardpoint).
                       Use empty string for empty slots.
        
        Example:
            mission.set_forced_equips([
                "fa26_gun",       # HP1: Gun
                "fa26_aim9x2",    # HP2: 2x AIM-9
                "fa26_droptank",  # HP3: Fuel tank
                "",               # HP4: Empty
                "fa26_droptank",  # HP5: Fuel tank
                "fa26_aim9x2",    # HP6: 2x AIM-9
                ""                # HP7: Empty
            ])
        """
        self.forced_equips = ";".join(equip_list) + ";"
        self.force_equips = True
        self.logger.info(f"✓ Set forced loadout: {len([e for e in equip_list if e])} equipped hardpoints")
    
    def use_loadout_preset(self, preset_name: str):
        """
        Use a pre-configured loadout preset.
        
        Args:
            preset_name: Name of preset (e.g., "fa26_air_to_air", "av42_cas")
        
        Available presets:
            - fa26_air_to_air: F/A-26B air superiority
            - fa26_cas: F/A-26B close air support
            - fa26_strike: F/A-26B precision strike
            - av42_transport: AV-42C light transport
            - av42_cas: AV-42C close air support
            - f45_stealth_strike: F-45A stealth strike
        
        Example:
            mission.use_loadout_preset("fa26_air_to_air")
        """
        from pytol.resources.equipment import LoadoutPresets
        
        try:
            loadout = LoadoutPresets.get_preset(preset_name)
            self.set_forced_equips(loadout)
        except ValueError as e:
            self.logger.error(f"{e}")
    
    # ========== End Equipment Methods ==========
    
    # ========== Base Discovery Methods ==========
    
    def get_available_bases(self):
        """
        Returns a list of all bases (airbases, carriers, FOBs) available on the map.
        
        Returns:
            list: List of base dictionaries with keys:
                - id: Base ID from map
                - name: Base name
                - prefab_type: Type (airbase1, airbase2, carrier1, etc.)
                - position: [x, y, z] coordinates
                - rotation: [pitch, yaw, roll] in degrees
                - footprint: Bounding box dimensions
        
        Example:
            bases = mission.get_available_bases()
            for base in bases:
                self.logger.info(f"{base['name']} at {base['position']}")
        """
        if not hasattr(self, 'tc') or self.tc is None:
            self.logger.warning("TerrainCalculator not initialized. Cannot retrieve bases.")
            return []
        
        return self.tc.get_all_bases()
    
    def get_base_by_name(self, name: str):
        """
        Find a base by name (case-insensitive partial match).
        
        Args:
            name: Base name or partial name to search for
        
        Returns:
            dict: Base information, or None if not found
        
        Example:
            northeast_base = mission.get_base_by_name("Northeast")
        """
        if not hasattr(self, 'tc') or self.tc is None:
            self.logger.warning("TerrainCalculator not initialized.")
            return None
        
        return self.tc.get_base_by_name(name)
    
    def get_nearest_base(self, x, z):
        """
        Find the nearest base to a given coordinate.
        
        Args:
            x: X world coordinate
            z: Z world coordinate
        
        Returns:
            tuple: (base_dict, distance_in_meters) or (None, None)
        
        Example:
            base, dist = mission.get_nearest_base(50000, 100000)
            self.logger.info(f"Nearest base: {base['name']} ({dist:.0f}m away)")
        """
        if not hasattr(self, 'tc') or self.tc is None:
            self.logger.warning("TerrainCalculator not initialized.")
            return None, None
        
        return self.tc.get_nearest_base(x, z)
    
    # ========== End Base Discovery Methods ==========

    def _get_or_assign_id(self, obj: Any, prefix: str, user_provided_id: Optional[Union[str, int]] = None) -> Union[str, int]:
        """
        Gets the assigned VTS ID for an object, or assigns one if not yet added.

        This method handles adding the object to the correct mission list/dict
        and managing the internal ID maps and counters.

        Args:
            obj: The Pytol object (Waypoint, Path, Conditional, etc.).
            prefix: The prefix for auto-generated IDs (e.g., "_pytol_wpt").
            user_provided_id: An optional ID provided by the user.

        Returns:
            The unique string or integer ID assigned to the object for VTS.

        Raises:
            TypeError: If the object type is not recognized.
            ValueError: If a user-provided ID conflicts.
        """
        obj_py_id = id(obj) # Use Python's unique object ID for mapping

        # --- Determine target map, list/dict, and ID type ---
        from pytol.classes.conditionals import ConditionalTree
        
        target_map = None
        target_list_or_dict = None
        id_type = "string" # Most are strings

        if isinstance(obj, Waypoint):
            id_type = "int"
            target_map = self._waypoints_map
            target_list_or_dict = self.waypoints
            obj_type_name = "Waypoint"
        elif isinstance(obj, Path):
            id_type = "int"
            target_map = self._paths_map
            target_list_or_dict = self.paths
            obj_type_name = "Path"
        elif isinstance(obj, (Conditional, ConditionalTree)):
            target_map = self._conditionals_map
            target_list_or_dict = self.conditionals # This is a dict
            obj_type_name = "Conditional"
        elif isinstance(obj, Trigger):
            id_type = "int"
            target_map = self._triggers_map # Maps int ID -> object
            target_list_or_dict = self.trigger_events
            obj_type_name = "Trigger"
            user_provided_id = getattr(obj, 'id', None) # ID comes from object
            if user_provided_id is None:
                raise ValueError("Trigger object must have an 'id' attribute.")
        elif isinstance(obj, Objective):
            id_type = "int"
            target_map = self._objectives_map # Maps int ID -> object
            target_list_or_dict = self.objectives
            obj_type_name = "Objective"
            user_provided_id = getattr(obj, 'objective_id', None) # ID comes from object
            if user_provided_id is None:
                raise ValueError("Objective object must have an 'objective_id' attribute.")
        else:
            raise TypeError(f"Unsupported object type for ID assignment: {type(obj)}")

        # --- Check if already added ---
        if id_type == "string":
            if obj_py_id in target_map:
                assigned_id = target_map[obj_py_id]
                # If user provided an ID, ensure it matches the already assigned one
                if user_provided_id is not None and user_provided_id != assigned_id:
                    self.logger.warning(f"{obj_type_name} object was already added with ID '{assigned_id}'. Ignoring user ID '{user_provided_id}'.")
                return assigned_id
        else: # Int ID type (Trigger, Objective)
            if user_provided_id in target_map:
                 # Check if the ID maps to the *same* object
                 if target_map[user_provided_id] is obj:
                     return user_provided_id
                 else:
                     raise ValueError(f"{obj_type_name} ID {user_provided_id} is already assigned to a different object.")

        # --- Assign New ID ---
        assigned_id = user_provided_id
        if assigned_id is None:
            # Get the next available integer ID from the counter
            counter = self._id_counters[obj_type_name]
            assigned_id = counter # Assign the integer ID
            self._id_counters[obj_type_name] += 1 # Increment for next time

            # Print appropriate message based on type
            if id_type == "int":
                self.logger.info(f"Assigning automatic integer ID '{assigned_id}' to {obj_type_name} '{getattr(obj, 'name', '')}'")
            else: # Should only be string type left (Conditionals)
                assigned_id = f"{prefix}_{assigned_id}" # Format the string ID using the counter number
                self.logger.info(f"Assigning automatic string ID '{assigned_id}' to {obj_type_name} '{getattr(obj, 'name', '')}'")

        # --- Add object to mission list/dict and map ---
        if isinstance(target_list_or_dict, list):
            target_list_or_dict.append(obj)
            if id_type == "string":
                target_map[obj_py_id] = assigned_id
            else: # int ID
                target_map[assigned_id] = obj
        elif isinstance(target_list_or_dict, dict): # Conditionals
             if assigned_id in target_list_or_dict: # Should only happen if user provided duplicate string ID
                 raise ValueError(f"{obj_type_name} ID '{assigned_id}' already exists.")
             target_list_or_dict[assigned_id] = obj
             target_map[obj_py_id] = assigned_id # Also map Python ID -> string ID
        else:
            # Should not happen
            raise TypeError("Internal error: target_list_or_dict is not list or dict.")

        # --- Assign ID back to object if it's a dataclass field ---
        # This simplifies formatting later, object now stores its final ID
        if id_type == "string" and hasattr(obj, 'id'):
             obj.id = assigned_id
        elif id_type == "int":
             # Already checked that ID exists on object
             pass

        return assigned_id
    @property
    def global_actions(self):
        """Provides access to action helpers for defined Global Values."""
        # This creates a dictionary-like object where keys are GV names
        # and values are the corresponding action helper instances.
        class GlobalActionAccessor:
            def __init__(self, mission_instance):
                self._mission = mission_instance

            def __getitem__(self, gv_name: str) -> GlobalValueActions:
                if gv_name not in self._mission.global_values:
                    raise KeyError(f"GlobalValue '{gv_name}' is not defined in the mission.")
                return GlobalValueActions(target_id=gv_name)

            def __getattr__(self, gv_name: str) -> GlobalValueActions:
                # Allow access like mission.global_actions.myValue
                try:
                    return self[gv_name]
                except KeyError:
                    raise AttributeError(f"'GlobalActionAccessor' object has no attribute '{gv_name}' (or GlobalValue not defined)")

        return GlobalActionAccessor(self)
    
    def add_unit(self,
             unit_obj: Unit,
             placement: str = "airborne",
             use_smart_placement: Optional[bool] = None,
             altitude_agl: Optional[float] = None,
             align_to_surface: bool = True, # Use terrain slope for rotation
             on_carrier: bool = False,
             mp_select_enabled: bool = True,
             spawn_chance: int = 100,
             spawn_flags: Optional[str] = None
            ) -> int:
        """
        Adds a Unit, handles terrain placement, and attaches actions helper.

        Args:
            unit_obj: Instance of a Unit dataclass.
            placement: "airborne", "ground", "sea", "relative_airborne".
            use_smart_placement: If True (default for "ground"), uses detailed placement
                                (roads, roofs). If False, uses simpler terrain height.
            altitude_agl: Altitude AGL for "relative_airborne".
            align_to_surface: If True and placing on terrain/road, adjust pitch/roll.
            on_carrier: If True, overrides terrain placement.
            mp_select_enabled: If selectable in MP.

        Returns:
            The unitInstanceID.
        """
        if not isinstance(unit_obj, Unit):
            raise TypeError(f"unit_obj must be a Unit dataclass, not {type(unit_obj)}")

        # --- Unit Instance ID ---
        uid = len(self.units) + 1  # Start IDs at 1 instead of 0

        # --- Attach Action Helper ---
        ActionClass = UNIT_CLASS_TO_ACTION_CLASS.get(type(unit_obj))
        if ActionClass:
            # Pass the instance ID (uid) as the target_id for VTS events
            unit_obj.actions = ActionClass(target_id=uid)
            self.logger.info(f"  > Attached actions helper '{ActionClass.__name__}' to unit {uid}")
        else:
            self.logger.warning(f"  > No action helper found for unit type {type(unit_obj).__name__}")

        # --- Determine Default Smart Placement ---
        if use_smart_placement is None:
            use_smart_placement = (placement == "ground")

        # --- Placement Logic ---
        initial_pos = list(unit_obj.global_position)
        initial_rot = list(unit_obj.rotation)
        final_pos = list(initial_pos)
        final_rot = list(initial_rot)
        editor_mode = "Air"

        x, z = final_pos[0], final_pos[2]
        initial_yaw = initial_rot[1]

        if on_carrier:
            self.logger.info(f"Placing unit {uid} ('{unit_obj.unit_name}') on carrier.")
            editor_mode = "Ground" # Assuming ground mode for carrier placement
        elif placement == "ground":
            if use_smart_placement:
                self.logger.info(f"Attempting smart placement for unit {uid} at ({x:.2f}, {z:.2f})...")
                try:
                    # Use the comprehensive smart placement function from TerrainCalculator
                    placement_info = self.tc.get_smart_placement(x, z, initial_yaw)
                    placement_type = placement_info['type']
                    final_pos = list(placement_info['position'])
                    final_rot = list(placement_info['rotation']) # Use rotation from smart placement
                    self.logger.info(f"  > Smart placement result: {placement_type} at {final_pos[1]:.2f}m")

                    # Set editor mode based on type
                    if placement_type in ['static_prefab_roof', 'city_roof', 'road', 'terrain']:
                        editor_mode = "Ground"

                    # Override rotation if alignment is disabled for terrain/road
                    if placement_type in ['terrain', 'road'] and not align_to_surface:
                        self.logger.info("  > Disabling surface alignment (keeping original yaw).")
                        final_rot = [0.0, initial_yaw, 0.0] # Keep only yaw
                    elif placement_type in ['static_prefab_roof', 'city_roof']:
                        # Roofs are typically flat, keep only yaw regardless of align_to_surface
                        self.logger.info("  > Setting flat rotation for roof placement.")
                        final_rot = [0.0, initial_yaw, 0.0] # Keep only yaw


                except Exception as e:
                    self.logger.warning(f"Smart placement failed for unit {uid}: {e}. Falling back.")
                    # Fallback to simple ground placement using get_asset_placement
                    try:
                        placement_info = self.tc.get_asset_placement(x, z, initial_yaw)
                        final_pos = list(placement_info['position'])
                        final_rot = list(placement_info['rotation'])
                        editor_mode = "Ground"
                        if not align_to_surface:
                            self.logger.info("  > Disabling surface alignment (Fallback - keeping original yaw).")
                            final_rot = [0.0, initial_yaw, 0.0]
                        self.logger.info(f"  > Fallback placement: terrain at {final_pos[1]:.2f}m")
                    except Exception as e2:
                        self.logger.warning(f"Fallback placement failed for unit {uid}: {e2}. Using original Y.")
                        final_pos = initial_pos # Revert to original position
                        final_rot = initial_rot
                        editor_mode = "Air" # Final fallback

            else: # Simple ground placement (use_smart_placement is False)
                self.logger.info(f"Placing unit {uid} ('{unit_obj.unit_name}') on ground (simple) at ({x:.2f}, {z:.2f}).")
                try:
                    # Use get_asset_placement for simple height + optional rotation
                    placement_info = self.tc.get_asset_placement(x, z, initial_yaw)
                    final_pos = list(placement_info['position'])
                    final_rot = list(placement_info['rotation'])
                    editor_mode = "Ground"
                    if not align_to_surface:
                        self.logger.info("  > Disabling surface alignment (Simple - keeping original yaw).")
                        final_rot = [0.0, initial_yaw, 0.0] # Keep only yaw
                    self.logger.info(f"  > Simple placement: terrain at {final_pos[1]:.2f}m")
                except Exception as e:
                    self.logger.warning(f"Simple ground placement failed for unit {uid}: {e}. Using original Y.")
                    final_pos = initial_pos # Revert to original
                    final_rot = initial_rot
                    editor_mode = "Air" # Fallback

        elif placement == "sea":
            self.logger.info(f"Placing unit {uid} ('{unit_obj.unit_name}') on sea at ({x:.2f}, {z:.2f}).")
            adjusted_y = self.tc.get_terrain_height(x, z)
            final_pos[1] = max(adjusted_y, 0) # Use terrain height but >= 0
            editor_mode = "Water"
            # Sea is flat, clear X/Z rotation, keep original yaw
            final_rot = [0.0, initial_yaw, 0.0]

        elif placement == "relative_airborne":
            if altitude_agl is None:
                raise ValueError("altitude_agl must be provided for placement='relative_airborne'")
            self.logger.info(f"Placing unit {uid} ('{unit_obj.unit_name}') at {altitude_agl}m AGL above ({x:.2f}, {z:.2f}).")
            ground_y = self.tc.get_terrain_height(x, z)
            final_pos[1] = ground_y + altitude_agl
            editor_mode = "Air"
            # Keep original rotation

        elif placement == "airborne":
            self.logger.info(f"Placing unit {uid} ('{unit_obj.unit_name}') airborne at provided coordinates.")
            editor_mode = "Air"
            # Keep original position/rotation

        else:
            raise ValueError(f"Invalid placement type: '{placement}'.")

        # --- Update Unit Object and Store Data ---
        unit_obj.global_position = final_pos
        unit_obj.rotation = final_rot

        unit_data = {
            'unit_obj': unit_obj,
            'unitInstanceID': uid,
            'lastValidPlacement': final_pos,
            'editorPlacementMode': editor_mode,
            'onCarrier': on_carrier,
            'mpSelectEnabled': mp_select_enabled,
            'spawn_chance': spawn_chance,
            'spawn_flags': spawn_flags
        }
        self.units.append(unit_data)
        self.logger.info(f"Unit '{unit_obj.unit_name}' added (ID: {uid}) with final pos: [{final_pos[0]:.2f}, {final_pos[1]:.2f}, {final_pos[2]:.2f}] rot: [{final_rot[0]:.2f}, {final_rot[1]:.2f}, {final_rot[2]:.2f}] mode: {editor_mode}")
        return uid
    
    def add_path(self, path_obj: Path, path_id: Optional[int] = None) -> str:
        """Adds a Path object, assigning an ID if needed."""
        if not isinstance(path_obj, Path):
            raise TypeError("path_obj must be a Path dataclass.")
        assigned_id = self._get_or_assign_id(path_obj, "_pytol_path", path_id)
        # Ensure the object has the final ID stored if it has an 'id' field
        if hasattr(path_obj, 'id') and path_obj.id != assigned_id:
             path_obj.id = assigned_id
        self.logger.info(f"Ruta '{path_obj.name}' added with ID '{assigned_id}'.")
        return assigned_id

    def add_waypoint(self, waypoint_obj: Waypoint, waypoint_id: Optional[int] = None) -> int:
        """Adds a Waypoint object, assigning an ID if needed."""
        if not isinstance(waypoint_obj, Waypoint):
            raise TypeError("waypoint_obj must be a Waypoint dataclass.")
        assigned_id = self._get_or_assign_id(waypoint_obj, "_pytol_wpt", waypoint_id)
        if waypoint_obj.id != assigned_id:
            waypoint_obj.id = assigned_id
        self.logger.info(f"Waypoint '{waypoint_obj.name}' added with ID '{assigned_id}'.")
        return assigned_id

    def add_unit_at_base_spawn(self,
                                unit_obj: Unit,
                                base_index: int = 0,
                                category: str = 'hangar',
                                spawn_index: int = 0,
                                base_type: str = None,
                                mp_select_enabled: bool = True,
                                spawn_chance: int = 100) -> int:
        """
        Add a unit at a specific base spawn point (hangar, helipad, etc.).
        
        Note: This is for actual spawn points only (hangar/helipad/bigplane).
        For placing objectives at reference points (runway/tower/barracks), use
        select_spawn_point() or get_reference_points() directly.
        
        Args:
            unit_obj: Unit dataclass instance to add
            base_index: Which base to use (0 = first, 1 = second, etc.)
            category: Spawn category ('hangar', 'helipad', 'bigplane')
            spawn_index: Which spawn in category (0 = first, -1 = random)
            base_type: Optional filter for base type ('airbase1', 'airbase2', 'airbase3')
            mp_select_enabled: If selectable in multiplayer
            spawn_chance: Spawn probability (0-100)
        
        Returns:
            Unit instance ID
            
        Examples:
            # Add player at first hangar of first airbase
            mission.add_unit_at_base_spawn(player_unit, base_index=0, category='hangar', spawn_index=0)
            
            # Add unit at random helipad of second airbase
            mission.add_unit_at_base_spawn(heli_unit, base_index=1, category='helipad', spawn_index=-1)
            
            # Add unit at first airbase2 on map
            mission.add_unit_at_base_spawn(unit, base_type='airbase2', category='hangar')
            
        For reference points (objectives/waypoints):
            from pytol.resources.base_spawn_points import select_spawn_point, get_reference_points
            
            # Get runway endpoint for waypoint
            runway_pos, runway_yaw = select_spawn_point(base, category='runway', index=0)
            
            # Get all runway points
            runways = get_reference_points('airbase1', 'runway')
        """
        from pytol.resources.base_spawn_points import select_spawn_point, get_available_bases
        
        # Get available bases
        bases = get_available_bases(self.tc, base_type)
        
        if not bases:
            type_msg = f" of type '{base_type}'" if base_type else ""
            raise ValueError(f"No bases{type_msg} found on map '{self.map_id}'")
        
        # Select base
        if base_index >= len(bases):
            self.logger.warning(f"Base index {base_index} out of range (only {len(bases)} bases), using last base")
            base_index = len(bases) - 1
        
        base = bases[base_index]
        
        # Get spawn point
        try:
            pos, yaw = select_spawn_point(base, category=category, index=spawn_index, fallback_to_center=True)
        except ValueError as e:
            self.logger.error(f"Failed to select spawn point: {e}")
            raise
        
        # Update unit position and rotation
        unit_obj.global_position = list(pos)
        unit_obj.rotation = [0.0, yaw, 0.0]
        
        self.logger.info(f"Placing unit '{unit_obj.unit_name}' at {base.get('prefab_type', 'unknown')} {category} spawn")
        
        # Add unit with ground placement (no smart placement since we have exact position)
        return self.add_unit(
            unit_obj,
            placement="ground",
            use_smart_placement=False,
            align_to_surface=False,
            mp_select_enabled=mp_select_enabled,
            spawn_chance=spawn_chance
        )

    def add_unit_to_group(self, team: str, group_name: str, unit_instance_id: int): # Unchanged
        """Assigns a unit (by its instance ID) to a unit group."""
        team_upper = team.upper()
        group = self.unit_groups.setdefault(team_upper, {})
        group.setdefault(group_name, []).append(unit_instance_id)

    def add_objective(self, objective_obj: Objective) -> int:
        """Adds an Objective object, ensuring its ID is tracked."""
        if not isinstance(objective_obj, Objective):
            raise TypeError("objective_obj must be an Objective dataclass.")
        # Objective ID is required and comes *from* the object
        assigned_id = self._get_or_assign_id(objective_obj, "_pytol_obj")
        self.logger.info(f"Objetivo '{objective_obj.name}' (ID: {assigned_id}) tracked.")
        return assigned_id

    def add_static_object(self, static_obj: StaticObject) -> int:
        """Adds a StaticObject object. ID is its index."""
        if not isinstance(static_obj, StaticObject):
            raise TypeError("static_obj must be a StaticObject dataclass.")
        sid = self._static_object_next_id
        self.static_objects.append(static_obj)
        self._static_object_next_id += 1
        self.logger.info(f"StaticObject '{static_obj.prefab_id}' added (ID: {sid})")
        return sid

    def add_trigger_event(self, trigger_obj: Trigger) -> int:
        """Adds a Trigger object, ensuring its ID is tracked."""
        if not isinstance(trigger_obj, Trigger):
            raise TypeError("trigger_obj must be a Trigger dataclass.")
        # Trigger ID is required and comes *from* the object
        assigned_id = self._get_or_assign_id(trigger_obj, "_pytol_trig")
        self.logger.info(f"Trigger '{trigger_obj.name}' (ID: {assigned_id}) tracked.")
        return assigned_id

    def add_base(self, base_obj: Base): # Unchanged logic, just type hint
        """Adds a Base object."""
        if not isinstance(base_obj, Base):
            raise TypeError("base_obj must be a Base dataclass.")
        if any(b.id == base_obj.id for b in self.bases):
             self.logger.warning(f"Base ID {base_obj.id} already exists.")
        self.bases.append(base_obj)
        self.logger.info(f"Base '{base_obj.name or base_obj.id}' added (ID: {base_obj.id}).")

    def add_briefing_note(self, note_obj: BriefingNote): # Unchanged logic, just type hint
        """Adds a BriefingNote object."""
        if not isinstance(note_obj, BriefingNote):
            raise TypeError("note_obj must be a BriefingNote dataclass.")
        self.briefing_notes.append(note_obj)

    def add_resource(self, res_id: int, path: str):
        """
        Adds a resource and automatically copies the file to the mission output directory.
        
        Args:
            res_id: Unique integer identifier for the resource
            path: Source path to the resource file on your system (absolute or relative to current working directory)
            
        Examples:
            # Add audio briefing
            mission.add_resource(1, "C:/MyMissions/audio/briefing.wav")
            # This will copy briefing.wav to: <mission_folder>/audio/briefing.wav
            
            # Add custom image
            mission.add_resource(2, "./images/custom_hud.png")
            # This will copy custom_hud.png to: <mission_folder>/images/custom_hud.png
            
        Note:
            Files are copied automatically when save_mission() is called.
            The file extension determines the subdirectory:
            - .wav → audio/
            - .png, .jpg, .jpeg → images/
            
        Raises:
            FileNotFoundError: If the source file doesn't exist
        """
        if res_id in self.resource_manifest:
            self.logger.warning(f"Overwriting resource with ID {res_id}")
        
        # Validate source file exists
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Resource file not found: {path}")
        
        # Store the source path for later copying during save_mission()
        self.resource_manifest[res_id] = path

    def add_conditional(self, conditional_obj, conditional_id: Optional[str] = None) -> str:
        """Adds a Conditional object or ConditionalTree, assigning an ID if needed."""
        from pytol.classes.conditionals import ConditionalTree
        
        if not isinstance(conditional_obj, (Conditional, ConditionalTree)):
            raise TypeError("conditional_obj must be a Conditional dataclass or ConditionalTree.")
        assigned_id = self._get_or_assign_id(conditional_obj, "_pytol_cond", conditional_id)
        # Conditionals don't have an 'id' field in their dataclass
        self.logger.info(f"Conditional added with ID '{assigned_id}'.")
        return assigned_id

    def add_global_value(self, gv_obj: GlobalValue):
        """Adds a GlobalValue object to the mission."""
        if not isinstance(gv_obj, GlobalValue):
            raise TypeError("gv_obj must be a GlobalValue dataclass.")
        if gv_obj.name in self.global_values:
            self.logger.warning(f"GlobalValue name '{gv_obj.name}' already exists. Overwriting.")
        self.global_values[gv_obj.name] = gv_obj
        self.logger.info(f"GlobalValue '{gv_obj.name}' added (initial value: {gv_obj.initial_value}).")

    def add_conditional_action(self, ca_obj: ConditionalAction):
        """Adds a ConditionalAction object to the mission."""
        if not isinstance(ca_obj, ConditionalAction):
            raise TypeError("ca_obj must be a ConditionalAction dataclass.")
        if any(ca.id == ca_obj.id for ca in self.conditional_actions):
            self.logger.warning(f"ConditionalAction ID {ca_obj.id} already exists.")
        # Ensure the linked conditional ID actually exists (optional check)
        if ca_obj.conditional_id not in self.conditionals:
            self.logger.warning(f"ConditionalAction '{ca_obj.name}' links to non-existent Conditional ID '{ca_obj.conditional_id}'.")

        self.conditional_actions.append(ca_obj)
        self.logger.info(f"ConditionalAction '{ca_obj.name}' added (ID: {ca_obj.id}), linked to Conditional '{ca_obj.conditional_id}'.")

    def add_timed_event_group(self, timed_event_group_obj: TimedEventGroup):
        """Adds a TimedEventGroup object to the mission."""
        if not isinstance(timed_event_group_obj, TimedEventGroup):
            raise TypeError("timed_event_group_obj must be a TimedEventGroup dataclass.")
        if any(g.group_id == timed_event_group_obj.group_id for g in self.timed_event_groups):
            self.logger.warning(f"TimedEventGroup ID {timed_event_group_obj.group_id} already exists.")
        self.timed_event_groups.append(timed_event_group_obj)
        self.logger.info(f"TimedEventGroup '{timed_event_group_obj.group_name}' added (ID: {timed_event_group_obj.group_id}).")
    

    def add_event_sequence(self, seq_obj: EventSequence):
        """Adds an EventSequence object to the mission."""
        if not isinstance(seq_obj, EventSequence):
            raise TypeError("seq_obj must be an EventSequence dataclass.")
        if any(seq.id == seq_obj.id for seq in self.event_sequences):
            self.logger.warning(f"EventSequence ID {seq_obj.id} already exists.")
        # Optional: Check linked conditionals within sequence events
        for event in seq_obj.events:
            if isinstance(event.conditional, str) and event.conditional not in self.conditionals:
                self.logger.warning(f"EventSequence '{seq_obj.sequence_name}' step '{event.node_name}' links to non-existent Conditional ID '{event.conditional}'.")

        self.event_sequences.append(seq_obj)
        self.logger.info(f"EventSequence '{seq_obj.sequence_name}' added (ID: {seq_obj.id}).")

    def add_random_event(self, re_obj: RandomEvent):
        """Adds a RandomEvent object (container for actions) to the mission."""
        if not isinstance(re_obj, RandomEvent):
            raise TypeError("re_obj must be a RandomEvent dataclass.")
        if any(re.id == re_obj.id for re in self.random_events):
            self.logger.warning(f"RandomEvent ID {re_obj.id} already exists.")
        # Optional: Check linked conditionals within action options
        for action_option in re_obj.action_options:
            if isinstance(action_option.conditional, str) and action_option.conditional not in self.conditionals:
                self.logger.warning(f"RandomEvent '{re_obj.name}' action ID {action_option.id} links to non-existent Conditional ID '{action_option.conditional}'.")

        self.random_events.append(re_obj)
        self.logger.info(f"RandomEvent '{re_obj.name}' added (ID: {re_obj.id}).")

    def _format_conditional(self, cond_id: str, cond) -> str:
        """
        Formats a Conditional or ConditionalTree dataclass into the nested VTS structure,
        including editor position placeholders.
        """
        from pytol.classes.conditionals import ConditionalTree, Conditional
        
        # Check if this is a ConditionalTree (multiple COMPs)
        if isinstance(cond, ConditionalTree):
            return self._format_conditional_tree(cond_id, cond)
        
        eol = "\n"
        indent_conditional = "\t\t" # Indent for CONDITIONAL block
        indent_comp = "\t\t\t"     # Indent for COMP block contents

        # Check if this is an empty base Conditional (no COMPs)
        if cond.__class__ == Conditional:
            # Empty conditional - just output the CONDITIONAL block with id and outputNodePos
            return (f"{indent_conditional}CONDITIONAL{eol}"
                   f"{indent_conditional}{{{eol}"
                   f"{indent_comp}id = {cond_id}{eol}"
                   f"{indent_comp}outputNodePos = (0, 0, 0){eol}"
                   f"{indent_conditional}}}{eol}")

        cond_type_str = CLASS_TO_ID.get(cond.__class__)
        if not cond_type_str:
            raise TypeError(f"Unknown conditional object type: {cond.__class__.__name__}")

        # --- Build Inner COMP block content ---
        comp_content_lines = []
        comp_content_lines.append(f"{indent_comp}id = 0")
        comp_content_lines.append(f"{indent_comp}type = {cond_type_str}")
        comp_content_lines.append(f"{indent_comp}uiPos = (0, 0, 0)") # <-- ADDED uiPos

        if not is_dataclass(cond):
            self.logger.warning(f"Conditional object {cond_id} is not a dataclass.")
        else:
            for f in fields(cond):
                if f.name == 'internal_id': continue # Skip internal fields if any
                value = getattr(cond, f.name, None)
                if value is None: continue

                key_name_snake = f.name
                # Special case: c_value should remain in snake_case in VTS format
                if key_name_snake == 'c_value':
                    key_name_final = key_name_snake
                else:
                    key_name_final = _snake_to_camel(key_name_snake)
                formatted_value = ""

                # Special handling for global value references - convert name to ID
                if key_name_snake in ('gv', 'gv_a', 'gv_b') and isinstance(value, str):
                    # Find the index of the global value with this name
                    gv_id = -1  # Default to -1 if not found
                    for idx, gv in enumerate(self.global_values.values()):
                        if gv.name == value:
                            gv_id = idx
                            break
                    formatted_value = str(gv_id)
                elif isinstance(value, list):
                    # Ensure correct semicolon list format
                    formatted_value = ";".join(map(str, value)) + ";"
                else:
                    formatted_value = _format_value(value)

                comp_content_lines.append(f"{indent_comp}{key_name_final} = {formatted_value}")

        comp_content_str = eol.join(comp_content_lines) + eol
        comp_block_str = _format_block("COMP", comp_content_str, 3)

        # --- Build Outer CONDITIONAL block content ---
        conditional_content_str = (
            f"{indent_comp}id = {cond_id}{eol}"
            f"{indent_comp}outputNodePos = (0, 0, 0){eol}" # <-- ADDED outputNodePos
            f"{indent_comp}root = 0{eol}"
            f"{comp_block_str}"
        )

        # Manually construct the outer block
        return f"{indent_conditional}CONDITIONAL{eol}{indent_conditional}{{{eol}{conditional_content_str}{indent_conditional}}}{eol}"

    def _format_conditional_tree(self, cond_id: str, tree) -> str:
        """
        Formats a ConditionalTree with multiple COMP blocks into a single CONDITIONAL block.
        """
        eol = "\n"
        indent_conditional = "\t\t"
        indent_comp = "\t\t\t"
        
        # Build all COMP blocks
        comp_blocks = []
        for comp_id in sorted(tree.components.keys()):
            cond = tree.components[comp_id]
            cond_type_str = CLASS_TO_ID.get(cond.__class__)
            if not cond_type_str:
                raise TypeError(f"Unknown conditional object type: {cond.__class__.__name__}")
            
            # Build COMP block content
            comp_content_lines = []
            comp_content_lines.append(f"{indent_comp}id = {comp_id}")
            comp_content_lines.append(f"{indent_comp}type = {cond_type_str}")
            comp_content_lines.append(f"{indent_comp}uiPos = (0, 0, 0)")
            
            if is_dataclass(cond):
                # Collect all field outputs (except method_parameters which needs special handling)
                regular_fields = []
                method_params_block = None
                
                for f in fields(cond):
                    if f.name == 'internal_id':
                        continue
                    value = getattr(cond, f.name, None)
                    if value is None:
                        continue
                    
                    key_name_snake = f.name
                    # Special case: c_value should remain in snake_case in VTS format
                    if key_name_snake == 'c_value':
                        key_name_final = key_name_snake
                    else:
                        key_name_final = _snake_to_camel(key_name_snake)
                    
                    # Special handling for method_parameters - needs nested block structure
                    # Store it separately to add AFTER isNot
                    if key_name_snake == 'method_parameters' and isinstance(value, list):
                        param_value = ";".join(map(str, value)) + ";"
                        indent_param = "\t\t\t\t"
                        method_params_block = (
                            f"{indent_comp}{key_name_final}{eol}"
                            f"{indent_comp}{{{eol}"
                            f"{indent_param}value = {param_value}{eol}"
                            f"{indent_comp}}}"
                        )
                        continue
                    
                    # Special handling for global value references
                    formatted_value = ""
                    if key_name_snake in ('gv', 'gv_a', 'gv_b') and isinstance(value, str):
                        gv_id = -1
                        for idx, gv in enumerate(self.global_values.values()):
                            if gv.name == value:
                                gv_id = idx
                                break
                        formatted_value = str(gv_id)
                    elif isinstance(value, list):
                        formatted_value = ";".join(map(str, value)) + ";"
                    elif isinstance(value, str) and ';' in value and not value.endswith(';'):
                        # String contains semicolons (semicolon-separated list) - ensure trailing semicolon
                        formatted_value = value + ";"
                    else:
                        formatted_value = _format_value(value)
                    
                    regular_fields.append((key_name_snake, key_name_final, formatted_value))
                
                # Add regular fields first
                for key_snake, key_final, formatted_val in regular_fields:
                    comp_content_lines.append(f"{indent_comp}{key_final} = {formatted_val}")
                
                # Add methodParameters block AFTER other fields (especially after isNot)
                if method_params_block:
                    comp_content_lines.append(method_params_block)
            
            comp_content_str = eol.join(comp_content_lines) + eol
            comp_block_str = _format_block("COMP", comp_content_str, 3)
            comp_blocks.append(comp_block_str)
        
        # Build the CONDITIONAL block with all COMPs
        all_comps_str = "".join(comp_blocks)
        conditional_content_str = (
            f"{indent_comp}id = {cond_id}{eol}"
            f"{indent_comp}outputNodePos = (0, 0, 0){eol}"
            f"{indent_comp}root = {tree.root}{eol}"
            f"{all_comps_str}"
        )
        
        return f"{indent_conditional}CONDITIONAL{eol}{indent_conditional}{{{eol}{conditional_content_str}{indent_conditional}}}{eol}"

    def _generate_content_string(self) -> Dict[str, str]:
        """Internal function to generate the content for all VTS blocks."""
        eol = "\n"

        # --- UNITS --- (No ID changes needed)
        units_c = ""
        for u_data in self.units:
            u = u_data['unit_obj']
            
            # Build unit fields with proper ordering
            # Start with unitGroup first (if present), then other fields
            fields_c = ""
            if 'unit_group' in u.unit_fields:
                fields_c += f"\t\t\t\tunitGroup = {u.unit_fields['unit_group']}{eol}"
            
            # Add behavior field
            if 'behavior' in u.unit_fields:
                fields_c += f"\t\t\t\tbehavior = {u.unit_fields['behavior']}{eol}"
            
            # Always include defaultPath and waypoint (even if null) for ground units
            if 'default_path' in u.unit_fields:
                fields_c += f"\t\t\t\tdefaultPath = {_format_value(u.unit_fields['default_path'])}{eol}"
            elif 'behavior' in u.unit_fields:  # If it has behavior field, it's likely a ground unit
                fields_c += f"\t\t\t\tdefaultPath = null{eol}"
                
            if 'waypoint' in u.unit_fields:
                fields_c += f"\t\t\t\twaypoint = {_format_value(u.unit_fields['waypoint'])}{eol}"
            elif 'behavior' in u.unit_fields:  # If it has behavior field, it's likely a ground unit
                fields_c += f"\t\t\t\twaypoint = null{eol}"
            
            # Add remaining fields in specific order to match game editor output
            skip_fields = {'unit_group', 'behavior', 'default_path', 'waypoint'}
            # Order: engageEnemies, detectionMode, spawnOnStart, invincible, respawnable, receiveFriendlyDamage, then any others
            ordered_field_names = ['engage_enemies', 'detection_mode', 'spawn_on_start', 'invincible', 'respawnable', 'receive_friendly_damage']
            for field_name in ordered_field_names:
                if field_name in u.unit_fields:
                    fields_c += f"\t\t\t\t{_snake_to_camel(field_name)} = {_format_value(u.unit_fields[field_name])}{eol}"
            # Add any remaining fields not in the ordered list
            for k, v in u.unit_fields.items():
                if k not in skip_fields and k not in ordered_field_names:
                    fields_c += f"\t\t\t\t{_snake_to_camel(k)} = {_format_value(v)}{eol}"

            units_c += f"\t\tUnitSpawner{eol}\t\t{{{eol}" \
                    f"\t\t\tunitName = {u.unit_name}{eol}" \
                    f"\t\t\tglobalPosition = {_format_vector(u.global_position)}{eol}" \
                    f"\t\t\tunitInstanceID = {u_data['unitInstanceID']}{eol}" \
                    f"\t\t\tunitID = {u.unit_id}{eol}" \
                    f"\t\t\trotation = {_format_vector(u.rotation)}{eol}" \
                    f"\t\t\tlastValidPlacement = {_format_vector(u_data['lastValidPlacement'])}{eol}" \
                    f"\t\t\teditorPlacementMode = {u_data['editorPlacementMode']}{eol}" \
                    f"\t\t\tonCarrier = {u_data['onCarrier']}{eol}" \
                    f"\t\t\tmpSelectEnabled = {u_data['mpSelectEnabled']}{eol}" \
                    f"{_format_block('UnitFields', fields_c, 3)}\t\t}}{eol}"

        # --- PATHS --- (Uses ID from Path object)
        paths_c = "".join([
            f"\t\tPATH{eol}\t\t{{{eol}"
            f"\t\t\tid = {p.id}{eol}"
            f"\t\t\tname = {p.name}{eol}"
            f"\t\t\tloop = {p.loop}{eol}"
            f"\t\t\tpoints = {_format_point_list(p.points)}{eol}"
            f"\t\t\tpathMode = {p.path_mode}{eol}"
            f"\t\t}}{eol}" for p in self.paths
        ])

        # --- WAYPOINTS --- (Uses ID from Waypoint object)
        # Append individual waypoints
        wpts_c = "".join([
            f"\t\tWAYPOINT{eol}\t\t{{{eol}"
            f"\t\t\tid = {w.id}{eol}"
            f"\t\t\tname = {w.name}{eol}"
            f"\t\t\tglobalPoint = {_format_vector(w.global_point)}{eol}"
            f"\t\t}}{eol}" for w in self.waypoints
        ])

        if self.bullseye_id is not None:
            bullseye = f"\t\tbullseyeID = {self.bullseye_id}{eol}"
            wpts_c = bullseye + wpts_c

        # --- UNIT GROUPS --- (No ID changes needed)
        ug_c = ""

        for team, groups in self.unit_groups.items():
            team_upper = team.upper()
            # Format unit group assignments without count prefix
            team_c = "".join([f"\t\t\t{name} = 0;{_format_id_list(ids)};{eol}" for name, ids in groups.items()])
            # Add SETTINGS blocks for each group
            for name in groups.keys():
                team_c += f"\t\t\t{name}_SETTINGS{eol}\t\t\t{{{eol}\t\t\t\tsyncAltSpawns = False{eol}\t\t\t}}{eol}"
            if team_c:
                ug_c += _format_block(team_upper, team_c, 2)

        # --- TRIGGER EVENTS --- (Handles potential object links)
        triggers_c = ""
        for t in self.trigger_events: # t is Trigger object
            # Resolve potential object links to string IDs before formatting props
            resolved_props = {}
            for k, v in t.get_props_dict().items():
                 if k == 'conditional' and isinstance(v, Conditional):
                      resolved_props[k] = self._get_or_assign_id(v, "_pytol_cond") # Ensure conditional is added
                 elif k == 'waypoint' and isinstance(v, Waypoint):
                      resolved_props[k] = self._get_or_assign_id(v, "_pytol_wpt") # Ensure waypoint is added
                 # TODO: Handle 'unit' if it can be an object link? (Currently assumes string)
                 else:
                      resolved_props[k] = v

            props_c = "".join([f"\t\t\t{_snake_to_camel(k)} = {_format_value(v)}{eol}" for k, v in resolved_props.items()])

            targets_c = "" # EventTarget formatting with altTargetIdx
            for target in t.event_targets:
                params_c = ""
                for p in target.params:
                    # Convert list values to semicolon format (e.g., [2] -> "2;")
                    formatted_value = _format_id_list(p.value) + ";" if isinstance(p.value, list) else _format_value(p.value)
                    params_c += (f"\t\t\t\t\tParamInfo{eol}\t\t\t\t\t{{{eol}"
                                 f"\t\t\t\t\t\ttype = {p.type}{eol}"
                                 f"\t\t\t\t\t\tvalue = {formatted_value}{eol}"
                                 f"\t\t\t\t\t\tname = {p.name}{eol}"
                                 f"\t\t\t\t\t}}{eol}")
                targets_c += f"\t\t\t\tEventTarget{eol}\t\t\t\t{{{eol}" \
                            f"\t\t\t\t\ttargetType = {target.target_type}{eol}" \
                            f"\t\t\t\t\ttargetID = {target.target_id}{eol}" \
                            f"\t\t\t\t\teventName = {target.event_name}{eol}" \
                            f"\t\t\t\t\tmethodName = {target.method_name or target.event_name}{eol}" \
                            f"\t\t\t\t\taltTargetIdx = -1{eol}" \
                            f"{params_c}\t\t\t\t}}{eol}"
            event_info = _format_block('EventInfo', f"\t\t\t\teventName = {eol}{targets_c}", 3)

            # Add ListOrderIndex and ListFolderName, use eventName instead of name
            list_order_index = t.id * 10 if hasattr(t, 'id') else 0
            
            # Only include waypoint for Proximity triggers
            waypoint_line = ""
            if t.trigger_type == "Proximity":
                waypoint_line = f"\t\t\twaypoint = null{eol}"
            
            triggers_c += f"\t\tTriggerEvent{eol}\t\t{{{eol}" \
                        f"\t\t\tid = {t.id}{eol}" \
                        f"\t\t\tenabled = {t.enabled}{eol}" \
                        f"\t\t\ttriggerType = {t.trigger_type}{eol}" \
                        f"\t\t\tListOrderIndex = {list_order_index}{eol}" \
                        f"\t\t\tListFolderName = {eol}" \
                        f"{waypoint_line}" \
                        f"{props_c}\t\t\teventName = {t.name}{eol}" \
                        f"{event_info}\t\t}}{eol}"

        # --- TIMED EVENT GROUPS ---
        teg_c = ""
        for group in self.timed_event_groups: # group is TimedEventGroup
            events_c = ""
            for event_info in group.events: # event_info is TimedEventInfo
                targets_c = ""
                for target in event_info.event_targets: # target is EventTarget
                    params_c = ""
                    for p in target.params: # p is ParamInfo
                        # Resolve potential object links in param values
                        param_value = p.value
                        if isinstance(p.value, Waypoint):
                            param_value = self._get_or_assign_id(p.value, "_pytol_wpt")
                        elif isinstance(p.value, Path):
                            param_value = self._get_or_assign_id(p.value, "_pytol_path")
                        # TODO: Handle Unit or other object links if needed for specific actions

                        # Handle special ParamAttrInfo block if necessary (VTS specific)
                        # For now, just format the basic ParamInfo
                        # Convert list values to semicolon format (e.g., [2] -> "2;")
                        formatted_value = _format_id_list(param_value) + ";" if isinstance(param_value, list) else _format_value(param_value)
                        param_info_block = f"\t\t\t\t\t\tParamInfo{eol}\t\t\t\t\t\t{{{eol}" \
                                        f"\t\t\t\t\t\t\ttype = {p.type}{eol}" \
                                        f"\t\t\t\t\t\t\tvalue = {formatted_value}{eol}" \
                                        f"\t\t\t\t\t\t\tname = {p.name}{eol}"
                        
                        if p.attr_info:
                            attr_type = p.attr_info.get('type')
                            attr_data = p.attr_info.get('data')
                            if attr_type and attr_data:
                                param_info_block += f"\t\t\t\t\t\t\tParamAttrInfo{eol}\t\t\t\t\t\t\t{{{eol}" \
                                                    f"\t\t\t\t\t\t\t\ttype = {attr_type}{eol}" \
                                                    f"\t\t\t\t\t\t\t\tdata = {attr_data}{eol}" \
                                                    f"\t\t\t\t\t\t\t}}{eol}"
                        
                        param_info_block += f"\t\t\t\t\t\t}}{eol}"
                        params_c += param_info_block

                    # Handle UnitGroup Target ID (using manual integer for now)
                    target_id_val = target.target_id
                    if target.target_type == "UnitGroup" and not isinstance(target.target_id, int):
                        self.logger.warning(f"targetID for UnitGroup '{target.target_id}' should likely be an integer.")
                        # Attempt conversion, or raise error? For now, format as is.
                        target_id_val = _format_value(target.target_id)
                    elif target.target_type == "Unit":
                        # Ensure Unit targetID is the integer unitInstanceID
                        target_id_val = int(target.target_id) # Should already be int from action helper

                    targets_c += f"\t\t\t\t\tEventTarget{eol}\t\t\t\t\t{{{eol}" \
                                f"\t\t\t\t\t\ttargetType = {target.target_type}{eol}" \
                                f"\t\t\t\t\t\ttargetID = {target_id_val}{eol}" \
                                f"\t\t\t\t\t\teventName = {target.event_name}{eol}" \
                                f"\t\t\t\t\t\tmethodName = {target.method_name or target.event_name}{eol}" \
                                f"{params_c}\t\t\t\t\t}}{eol}"

                # Format TimedEventInfo block
                events_c += f"\t\t\tTimedEventInfo{eol}\t\t\t{{{eol}" \
                            f"\t\t\t\teventName = {event_info.event_name}{eol}" \
                            f"\t\t\t\ttime = {_format_value(event_info.time)}{eol}" \
                            f"{targets_c}\t\t\t}}{eol}"

            # Format TimedEventGroup block with ListOrderIndex and ListFolderName
            list_order_index = (group.group_id - 1) * 10 if hasattr(group, 'group_id') else 0
            teg_c += f"\t\tTimedEventGroup{eol}\t\t{{{eol}" \
                    f"\t\t\tgroupName = {group.group_name}{eol}" \
                    f"\t\t\tgroupID = {group.group_id}{eol}" \
                    f"\t\t\tbeginImmediately = {group.begin_immediately}{eol}" \
                    f"\t\t\tinitialDelay = {int(group.initial_delay) if isinstance(group.initial_delay, (int, float)) else _format_value(group.initial_delay)}{eol}" \
                    f"\t\t\tListOrderIndex = {list_order_index}{eol}" \
                    f"\t\t\tListFolderName = {eol}" \
                    f"{events_c}\t\t}}{eol}"
        
        # Add FOLDER_DATA block if there are any timed event groups
        if self.timed_event_groups:
            teg_c += f"\t\tFOLDER_DATA{eol}\t\t{{{eol}\t\t}}{eol}"
        
        # --- OBJECTIVES --- (Handles potential object links)
        objectives_list = []
        for o in self.objectives: # o is Objective object
            # Resolve potential object links before formatting
            waypoint_id = o.waypoint
            
            if isinstance(o.waypoint, Waypoint):
                waypoint_id = o.waypoint.id
            if type(waypoint_id) is not int:
                waypoint_id = ""
            prereq_ids = []
            if o.prereqs:
                for prereq in o.prereqs:
                    if isinstance(prereq, Objective):
                        # Ensure prereq objective is added and get its ID
                        prereq_id = self._get_or_assign_id(prereq, "_pytol_obj")
                        prereq_ids.append(prereq_id)
                    elif isinstance(prereq, int): # Allow passing integer IDs directly
                        prereq_ids.append(prereq)
                    else:
                        self.logger.warning(f"Invalid type for objective prereq: {type(prereq)}. Skipping.")


            fields_content = "".join([f"\t\t\t\t{_snake_to_camel(k)} = {_format_value(v)}{eol}" for k,v in o.fields.items()])
            fields_block = _format_block('fields', fields_content, 3)

            def format_objective_event(event_block_name: str, event_info_name: str, targets: List[EventTarget]) -> str:
                targets_c = ""
                for target in targets:
                    params_c = ""
                    for p in target.params:
                        # Resolve param value links if needed
                        param_value = p.value
                        if isinstance(p.value, Waypoint):
                             param_value = self._get_or_assign_id(p.value, "_pytol_wpt") # Ensure added, get ID
                        elif isinstance(p.value, Path):
                             param_value = self._get_or_assign_id(p.value, "_pytol_path") # Ensure added, get ID
                        # TODO: Add checks for Unit, Conditional, etc. if actions can target them via objects

                        # Format ParamInfo block (add ParamAttrInfo if present)
                        # Convert list values to semicolon format (e.g., [2] -> "2;")
                        formatted_value = _format_id_list(param_value) + ";" if isinstance(param_value, list) else _format_value(param_value)
                        param_info_block = f"\t\t\t\t\tParamInfo{eol}\t\t\t\t\t{{{eol}" \
                                           f"\t\t\t\t\t\ttype = {p.type}{eol}" \
                                           f"\t\t\t\t\t\tvalue = {formatted_value}{eol}" \
                                           f"\t\t\t\t\t\tname = {p.name}{eol}"
                        if p.attr_info:
                             attr_type = p.attr_info.get('type')
                             attr_data = p.attr_info.get('data')
                             if attr_type and attr_data:
                                  param_info_block += f"\t\t\t\t\t\t\tParamAttrInfo{eol}\t\t\t\t\t\t\t{{{eol}" \
                                                      f"\t\t\t\t\t\t\t\ttype = {attr_type}{eol}" \
                                                      f"\t\t\t\t\t\t\t\tdata = {attr_data}{eol}" \
                                                      f"\t\t\t\t\t\t\t}}{eol}"
                        param_info_block += f"\t\t\t\t\t}}{eol}"
                        params_c += param_info_block

                # Resolve target ID links
                target_id_val = target.target_id
                if target.target_type == "Unit":
                    # Ensure target_id is the integer unitInstanceID
                    if not isinstance(target.target_id, int):
                        self.logger.warning(f"EventTarget for Unit should use integer unitInstanceID, got {target.target_id}. Attempting conversion.")
                        try:
                            target_id_val = int(target.target_id)
                        except ValueError:
                            self.logger.error(f"  > Could not convert Unit target ID to int for objective {o.objective_id}")
                    elif target.target_type == "Waypoint" and isinstance(target.target_id, Waypoint):
                         target_id_val = self._get_or_assign_id(target.target_id, "_pytol_wpt")
                    elif target.target_type == "Path" and isinstance(target.target_id, Path):
                         target_id_val = self._get_or_assign_id(target.target_id, "_pytol_path")
                    # TODO: Add checks for Timed_Events, UnitGroup, System etc. if needed

                    targets_c += f"\t\t\t\tEventTarget{eol}\t\t\t\t{{{eol}" \
                                f"\t\t\t\t\ttargetType = {target.target_type}{eol}" \
                                f"\t\t\t\t\ttargetID = {_format_value(target_id_val)}{eol}" \
                                f"\t\t\t\t\teventName = {target.event_name}{eol}" \
                                f"\t\t\t\t\tmethodName = {target.method_name or target.event_name}{eol}" \
                                f"{params_c}\t\t\t\t}}{eol}"

                # Only create EventInfo content if there are targets
                if targets_c:
                    event_info_content = f"\t\t\t\t\teventName = {event_info_name}{eol}{targets_c}"
                else:
                    event_info_content = f"\t\t\t\t\teventName = {event_info_name}{eol}" # Empty if no targets

                event_info_block = _format_block("EventInfo", event_info_content, 4)
                return _format_block(event_block_name, event_info_block, 3)

            # Generate the blocks using the helper function
            start_event_block = format_objective_event("startEvent", "Start Event", o.start_event_targets)
            fail_event_block = format_objective_event("failEvent", "Failed Event", o.fail_event_targets)
            complete_event_block = format_objective_event("completeEvent", "Completed Event", o.complete_event_targets)

            if o.start_mode:
                start_mode_str = o.start_mode
            elif prereq_ids:
                start_mode_str = 'PreReqs'
            else:
                start_mode_str = 'Immediate'

            # Build fields block with successConditional and failConditional
            fields_content = ""
            
            # For Conditional objectives, always include both conditionals (even if null)
            if o.type == "Conditional":
                success_cond = o.fields.get('successConditional') or o.fields.get('success_conditional')
                fields_content += f"\t\t\t\tsuccessConditional = {_format_value(success_cond) if success_cond else 'null'}{eol}"
                fail_cond = o.fields.get('failConditional') or o.fields.get('fail_conditional')
                fields_content += f"\t\t\t\tfailConditional = {_format_value(fail_cond) if fail_cond else 'null'}{eol}"
            else:
                # For other objective types, only add if they exist
                if 'successConditional' in o.fields or 'success_conditional' in o.fields:
                    success_cond = o.fields.get('successConditional') or o.fields.get('success_conditional')
                    fields_content += f"\t\t\t\tsuccessConditional = {_format_value(success_cond)}{eol}"
                if 'failConditional' in o.fields or 'fail_conditional' in o.fields:
                    fail_cond = o.fields.get('failConditional') or o.fields.get('fail_conditional')
                    fields_content += f"\t\t\t\tfailConditional = {_format_value(fail_cond)}{eol}"
            
            # Add any other custom fields
            for k, v in o.fields.items():
                if k not in ['successConditional', 'success_conditional', 'failConditional', 'fail_conditional']:
                    fields_content += f"\t\t\t\t{_snake_to_camel(k)} = {_format_value(v)}{eol}"
            fields_block = _format_block('fields', fields_content, 3)

            obj_str = f"\t\tObjective{eol}\t\t{{{eol}" \
                    f"\t\t\tobjectiveName = {o.name}{eol}" \
                    f"\t\t\tobjectiveInfo = {o.info}{eol}" \
                    f"\t\t\tobjectiveID = {o.objective_id}{eol}" \
                    f"\t\t\torderID = {o.orderID}{eol}" \
                    f"\t\t\trequired = {o.required}{eol}" \
                    f"\t\t\tcompletionReward = {o.completionReward}{eol}" \
                    f"\t\t\twaypoint = null{eol}" \
                    f"\t\t\tautoSetWaypoint = {o.auto_set_waypoint}{eol}" \
                    f"\t\t\tstartMode = {start_mode_str}{eol}" \
                    f"\t\t\tobjectiveType = {o.type}{eol}" \
                    f"{start_event_block}" \
                    f"{fail_event_block}" \
                    f"{complete_event_block}" \
                    f"{fields_block}" \
                    f"\t\t}}{eol}"
            objectives_list.append(obj_str)
        objs_c = "".join(objectives_list)

        # --- STATIC OBJECTS --- (Uses index as ID)
        statics_c = "".join([
            f"\t\tStaticObject{eol}\t\t{{{eol}"
            f"\t\t\tprefabID = {s.prefab_id}{eol}"
            f"\t\t\tid = {i}{eol}" # ID is the index
            f"\t\t\tglobalPos = {_format_vector(s.global_pos)}{eol}"
            f"\t\t\trotation = {_format_vector(s.rotation)}{eol}"
            f"\t\t}}{eol}" for i, s in enumerate(self.static_objects)
        ])

        # --- BASES --- (Uses ID from Base object)
        bases_c = ""
        for b in self.bases:
            custom_data_block = _format_block('CUSTOM_DATA', '', 3)
            bases_c += f"\t\tBaseInfo{eol}\t\t{{{eol}" \
                    f"\t\t\tid = {b.id}{eol}" \
                    f"\t\t\toverrideBaseName = {b.name or ''}{eol}" \
                    f"\t\t\tbaseTeam = {b.team}{eol}" \
                    f"{custom_data_block}\t\t}}{eol}"

        # --- BRIEFING --- (No ID changes needed)
        briefing_c = "".join([
            f"\t\tBRIEFING_NOTE{eol}\t\t{{{eol}"
            f"\t\t\ttext = {n.text}{eol}"
            f"\t\t\timagePath = {n.image_path or ''}{eol}"
            f"\t\t\taudioClipPath = {n.audio_clip_path or ''}{eol}"
            f"\t\t}}{eol}" for n in self.briefing_notes
        ])

        # --- RESOURCE MANIFEST --- (No ID changes needed)
        resources_c = "".join([f"\t\t{k} = {v}{eol}" for k, v in self.resource_manifest.items()])

        # --- CONDITIONALS --- (Uses assigned string ID from dict key)
        conditionals_c = "".join([
             self._format_conditional(cond_id, cond_obj)
             for cond_id, cond_obj in self.conditionals.items()
        ])

        # --- GLOBAL VALUES ---
        gv_c = ""
        # Use enumerate to get an index 'i' which serves as the integer ID
        for i, (name, gv) in enumerate(self.global_values.items()):
            # Construct the 'data' string: ID;Name;;InitialValue;
            gv_data_str = f"{i};{gv.name};;{_format_value(gv.initial_value)};"
            list_order_index = i * 10
            # Format the 'gv' block using the data string with ListOrderIndex and ListFolderName
            gv_c += f"\t\tgv{eol}\t\t{{{eol}" \
                    f"\t\t\tdata = {gv_data_str}{eol}" \
                    f"\t\t\tListOrderIndex = {list_order_index}{eol}" \
                    f"\t\t\tListFolderName = {eol}" \
                    f"\t\t}}{eol}"
        
        # Add FOLDER_DATA block if there are any global values
        if self.global_values:
            gv_c += f"\t\tFOLDER_DATA{eol}\t\t{{{eol}\t\t}}{eol}"

        # --- CONDITIONAL ACTIONS ---
        ca_c = ""
        for ca in self.conditional_actions: # ca is ConditionalAction
            targets_c = ""
            # Reuse the EventTarget formatting logic
            for target in ca.actions:
                params_c = ""
                for p in target.params:
                    # --- Resolve param value links ---
                    param_value = p.value
                    if isinstance(p.value, GlobalValue):
                         param_value = p.value.name
                    elif isinstance(p.value, Waypoint):
                         param_value = self._get_or_assign_id(p.value, "_pytol_wpt") # Ensure added, get ID
                    elif isinstance(p.value, Path):
                         param_value = self._get_or_assign_id(p.value, "_pytol_path") # Ensure added, get ID
                    elif isinstance(p.value, Unit):
                         # Find the unitInstanceID for the unit object
                         found_id = next((u['unitInstanceID'] for u in self.units if u['unit_obj'] is p.value), None)
                         if found_id is not None:
                              param_value = found_id
                         else:
                              self.logger.warning(f"Could not find unitInstanceID for Unit param value in CondAction {ca.id}")
                    # TODO: Add checks for Conditional, etc. if actions can use them as param values

                    # --- Format ParamInfo block (with ParamAttrInfo) ---
                    # Convert list values to semicolon format (e.g., [2] -> "2;")
                    formatted_value = _format_id_list(param_value) + ";" if isinstance(param_value, list) else _format_value(param_value)
                    param_info_block = f"\t\t\t\t\tParamInfo{eol}\t\t\t\t\t{{{eol}" \
                                       f"\t\t\t\t\t\ttype = {p.type}{eol}" \
                                       f"\t\t\t\t\t\tvalue = {formatted_value}{eol}" \
                                       f"\t\t\t\t\t\tname = {p.name}{eol}"
                    if p.attr_info:
                         attr_type = p.attr_info.get('type')
                         attr_data = p.attr_info.get('data')
                         if attr_type and attr_data:
                              param_info_block += f"\t\t\t\t\t\t\tParamAttrInfo{eol}\t\t\t\t\t\t\t{{{eol}" \
                                                  f"\t\t\t\t\t\t\t\ttype = {attr_type}{eol}" \
                                                  f"\t\t\t\t\t\t\t\tdata = {attr_data}{eol}" \
                                                  f"\t\t\t\t\t\t\t}}{eol}"
                    param_info_block += f"\t\t\t\t\t}}{eol}"
                    params_c += param_info_block
                    # --- End ParamInfo Formatting ---

                # --- Resolve target ID links ---
                target_id_val = target.target_id
                if target.target_type == "GlobalValue":
                    if isinstance(target.target_id, GlobalValue):
                        target_id_val = target.target_id.name
                    elif not isinstance(target.target_id, str):
                        self.logger.warning(f"targetID for GlobalValue should be string name, got {target.target_id}")
                        target_id_val = str(target.target_id)
                elif target.target_type == "Unit":
                    if isinstance(target.target_id, Unit): # If Unit object passed
                         found_id = next((u['unitInstanceID'] for u in self.units if u['unit_obj'] is target.target_id), None)
                         if found_id is not None:
                              target_id_val = found_id
                         else:
                              self.logger.warning(f"Could not find unitInstanceID for Unit target ID in CondAction {ca.id}")
                    elif not isinstance(target.target_id, int): # Ensure it's an int if not an object
                         self.logger.warning(f"EventTarget for Unit should use integer unitInstanceID, got {target.target_id}. Attempting conversion.")
                         try:
                             target_id_val = int(target.target_id)
                         except ValueError:
                             self.logger.error(f"  > Could not convert Unit target ID to int for CondAction {ca.id}")
                elif target.target_type == "Waypoint":
                    if isinstance(target.target_id, Waypoint):
                        target_id_val = self._get_or_assign_id(target.target_id, "_pytol_wpt")
                    # Ensure it's an int if already provided
                    elif not isinstance(target_id_val, int):
                         try:
                             target_id_val = int(target_id_val)
                         except ValueError:
                             self.logger.warning(f"Waypoint target ID should be int, got {target_id_val}")
                elif target.target_type == "Path":
                     if isinstance(target.target_id, Path):
                          target_id_val = self._get_or_assign_id(target.target_id, "_pytol_path")
                     elif not isinstance(target_id_val, int):
                         try:
                             target_id_val = int(target_id_val)
                         except ValueError:
                             self.logger.warning(f"Path target ID should be int, got {target_id_val}")
                elif target.target_type == "Conditional":
                     if isinstance(target.target_id, Conditional):
                          target_id_val = self._get_or_assign_id(target.target_id, "_pytol_cond") # Ensure added, get ID
                     elif not isinstance(target_id_val, str):
                          self.logger.warning(f"Conditional target ID should be string, got {target_id_val}")
                          target_id_val = str(target_id_val)
                # TODO: Add resolutions for Timed_Events, UnitGroup, System etc. if needed
                # --- End Target ID Resolution ---


                # --- Format EventTarget ---
                targets_c += f"\t\t\t\tEventTarget{eol}\t\t\t\t{{{eol}" \
                            f"\t\t\t\t\ttargetType = {target.target_type}{eol}" \
                            f"\t\t\t\t\ttargetID = {_format_value(target_id_val)}{eol}" \
                            f"\t\t\t\t\teventName = {target.event_name}{eol}" \
                            f"\t\t\t\t\tmethodName = {target.method_name or target.event_name}{eol}" \
                            f"{params_c}\t\t\t\t}}{eol}"
                # --- End EventTarget Formatting ---

            # Format the EventInfo block containing the actions
            event_info_content = f"\t\t\t\teventName = Action{eol}{targets_c}" # Standard name is 'Action'
            event_info_block = _format_block("EventInfo", event_info_content, 3)

            # Format the ConditionalAction block
            # Resolve conditional link if object was passed
            cond_id_val = ca.conditional_id
            if isinstance(ca.conditional_id, Conditional):
                cond_id_val = self._get_or_assign_id(ca.conditional_id, "_pytol_cond") # Ensure added, get ID

            ca_c += f"\t\tConditionalAction{eol}\t\t{{{eol}" \
                    f"\t\t\tid = {ca.id}{eol}" \
                    f"\t\t\tname = {ca.name}{eol}" \
                    f"\t\t\tconditionalID = {cond_id_val}{eol}" \
                    f"{event_info_block}\t\t}}{eol}"
            
        # --- RANDOM EVENTS ---
        re_c = ""
        for re in self.random_events: # re is RandomEvent (the container)
            actions_c = "" # String for all ACTION blocks within this RANDOM_EVENT
            for action in re.action_options: # action is RandomEventAction
                targets_c = ""
                # Format EventTargets within this action
                for target in action.actions:
                    params_c = ""
                    for p in target.params:
                        # Resolve param value links
                        param_value = p.value
                        if isinstance(p.value, GlobalValue): param_value = p.value.name
                        elif isinstance(p.value, Waypoint): param_value = self._get_or_assign_id(p.value, "_pytol_wpt")
                        elif isinstance(p.value, Path): param_value = self._get_or_assign_id(p.value, "_pytol_path")
                        elif isinstance(p.value, Unit):
                            found_id = next((u['unitInstanceID'] for u in self.units if u['unit_obj'] is p.value), None)
                            if found_id is not None:
                                param_value = found_id
                            else:
                                self.logger.warning(f"Could not find unitInstanceID for Unit param value in RandomEvent {re.id}, Action {action.id}")
                        # Format ParamInfo (with ParamAttrInfo)
                        # Convert list values to semicolon format (e.g., [2] -> "2;")
                        formatted_value = _format_id_list(param_value) + ";" if isinstance(param_value, list) else _format_value(param_value)
                        param_info_block = f"\t\t\t\t\t\tParamInfo{eol}\t\t\t\t\t\t{{{eol}" \
                                           f"\t\t\t\t\t\t\ttype = {p.type}{eol}" \
                                           f"\t\t\t\t\t\t\tvalue = {formatted_value}{eol}" \
                                           f"\t\t\t\t\t\t\tname = {p.name}{eol}"
                        if p.attr_info:
                             attr_type = p.attr_info.get('type'); attr_data = p.attr_info.get('data')
                             if attr_type and attr_data:
                                  param_info_block += f"\t\t\t\t\t\t\t\tParamAttrInfo{eol}\t\t\t\t\t\t\t\t{{{eol}" \
                                                      f"\t\t\t\t\t\t\t\t\ttype = {attr_type}{eol}" \
                                                      f"\t\t\t\t\t\t\t\t\tdata = {attr_data}{eol}" \
                                                      f"\t\t\t\t\t\t\t\t}}{eol}"
                        param_info_block += f"\t\t\t\t\t\t}}{eol}"
                        params_c += param_info_block

                    # Resolve target ID links
                    target_id_val = target.target_id
                    # ... (Copy full target ID resolution logic from ConditionalActions/TimedEvents) ...
                    if target.target_type == "GlobalValue":
                         if isinstance(target.target_id, GlobalValue):
                             target_id_val = target.target_id.name
                         elif not isinstance(target.target_id, str):
                             target_id_val = str(target.target_id)
                    elif target.target_type == "Unit":
                         if isinstance(target.target_id, Unit):
                              found_id = next((u['unitInstanceID'] for u in self.units if u['unit_obj'] is target.target_id), None)
                              if found_id is not None:
                                  target_id_val = found_id
                              else:
                                  self.logger.warning(f"Could not find unitInstanceID for Unit target ID in RandomEvent {re.id}, Action {action.id}")
                         elif not isinstance(target.target_id, int):
                              try:
                                  target_id_val = int(target.target_id)
                              except ValueError:
                                  self.logger.warning(f"Unit target ID not int for RandomEvent {re.id}, Action {action.id}")
                    # ... etc. for Waypoint, Path, Conditional ...

                    # Format EventTarget
                    targets_c += f"\t\t\t\t\tEventTarget{eol}\t\t\t\t\t{{{eol}" \
                                f"\t\t\t\t\t\ttargetType = {target.target_type}{eol}" \
                                f"\t\t\t\t\t\ttargetID = {_format_value(target_id_val)}{eol}" \
                                f"\t\t\t\t\t\teventName = {target.event_name}{eol}" \
                                f"\t\t\t\t\t\tmethodName = {target.method_name or target.event_name}{eol}" \
                                f"\t\t\t\t\t\taltTargetIdx = -1{eol}" \
                                f"{params_c}\t\t\t\t\t}}{eol}"

                # Format the EVENT_INFO block for this ACTION
                event_info_content = f"\t\t\t\t\teventName = {eol}{targets_c}"
                event_info_block = _format_block("EVENT_INFO", event_info_content, 4) # Indent 4 (not 5!)

                # Resolve the ACTION's conditional link
                action_cond_id_val_str = "0" # Default is "0"
                if action.conditional:
                     if isinstance(action.conditional, Conditional):
                          action_cond_id_val_str = self._get_or_assign_id(action.conditional, "_pytol_cond")
                     elif isinstance(action.conditional, str):
                          action_cond_id_val_str = action.conditional
                          if action_cond_id_val_str not in self.conditionals:
                               self.logger.warning(f"RandomEvent Action {action.id} uses unknown conditional ID '{action_cond_id_val_str}'")
                     else: # Allow integer 0
                          try:
                              action_cond_id_val_str = str(int(action.conditional))
                          except ValueError:
                              self.logger.warning(f"Invalid conditional link '{action.conditional}' in RandomEvent Action.")
                
                # Format the nested CONDITIONAL block inside ACTION
                # This is always just a placeholder with id = 0 and no COMP blocks
                conditional_block_inner = f"\t\t\t\tCONDITIONAL{eol}\t\t\t\t{{{eol}" \
                                          f"\t\t\t\t\tid = 0{eol}" \
                                          f"\t\t\t\t\toutputNodePos = (0, 0, 0){eol}" \
                                          f"\t\t\t\t}}{eol}"


                # Format the ACTION block
                action_block_content = (
                    f"\t\t\t\tid = {action.id}{eol}"
                    f"\t\t\t\tactionName = {action.action_name}{eol}"
                    f"\t\t\t\tfixedWeight = {_format_value(action.fixed_weight)}{eol}"
                    f"\t\t\t\tgvWeight = {action.gv_weight_name or -1}{eol}" # Use -1 if no GV specified
                    f"\t\t\t\tuseGv = {action.use_gv_weight}{eol}"
                    f"{conditional_block_inner}" # Include the nested conditional block
                    f"{event_info_block}"        # Include the nested event info block
                )
                actions_c += _format_block("ACTION", action_block_content, 3) # Indent 3 (not 4!)

            # Format the outer RANDOM_EVENT block
            re_c += f"\t\tRANDOM_EVENT{eol}\t\t{{{eol}" \
                    f"\t\t\tid = {re.id}{eol}" \
                    f"\t\t\tnote = {re.name}{eol}" \
                    f"{actions_c}\t\t}}{eol}" # Include all ACTION blocks

        # --- EVENT SEQUENCES ---
        es_c = ""
        for seq in self.event_sequences: # seq is EventSequence
            events_c = ""
            for event in seq.events: # event is SequenceEvent
                targets_c = ""
                # Reuse EventTarget formatting logic
                for target in event.actions:
                    params_c = ""
                    for p in target.params:
                        # Resolve param value links
                        param_value = p.value
                        if isinstance(p.value, GlobalValue):
                            param_value = p.value.name
                        elif isinstance(p.value, Waypoint):
                            param_value = self._get_or_assign_id(p.value, "_pytol_wpt")
                        elif isinstance(p.value, Path):
                            param_value = self._get_or_assign_id(p.value, "_pytol_path")
                        elif isinstance(p.value, Unit):
                            found_id = next((u['unitInstanceID'] for u in self.units if u['unit_obj'] is p.value), None)
                            if found_id is not None:
                                param_value = found_id
                            else:
                                self.logger.warning(f"Could not find unitInstanceID for Unit param value in EventSequence {seq.id}")
                        # Format ParamInfo (with ParamAttrInfo)
                        # Convert list values to semicolon format (e.g., [2] -> "2;")
                        formatted_value = _format_id_list(param_value) + ";" if isinstance(param_value, list) else _format_value(param_value)
                        param_info_block = f"\t\t\t\t\tParamInfo{eol}\t\t\t\t\t{{{eol}" \
                                           f"\t\t\t\t\t\ttype = {p.type}{eol}" \
                                           f"\t\t\t\t\t\tvalue = {formatted_value}{eol}" \
                                           f"\t\t\t\t\t\tname = {p.name}{eol}"
                        if p.attr_info: # Add ParamAttrInfo formatting
                             attr_type = p.attr_info.get('type'); attr_data = p.attr_info.get('data')
                             if attr_type and attr_data:
                                  param_info_block += f"\t\t\t\t\t\t\tParamAttrInfo{eol}\t\t\t\t\t\t\t{{{eol}" \
                                                      f"\t\t\t\t\t\t\t\ttype = {attr_type}{eol}" \
                                                      f"\t\t\t\t\t\t\t\tdata = {attr_data}{eol}" \
                                                      f"\t\t\t\t\t\t\t}}{eol}"
                        param_info_block += f"\t\t\t\t\t}}{eol}"
                        params_c += param_info_block
                    # Resolve target ID links
                    target_id_val = target.target_id
                    # ... (Copy target ID resolution logic) ...
                    # Format EventTarget
                    targets_c += f"\t\t\t\tEventTarget{eol}\t\t\t\t{{{eol}" \
                                f"\t\t\t\t\ttargetType = {target.target_type}{eol}" \
                                f"\t\t\t\t\ttargetID = {_format_value(target_id_val)}{eol}" \
                                f"\t\t\t\t\teventName = {target.event_name}{eol}" \
                                f"\t\t\t\t\tmethodName = {target.method_name or target.event_name}{eol}" \
                                f"{params_c}\t\t\t\t}}{eol}"
                # Format EventInfo block
                event_info_content = f"\t\t\t\t\teventName = {eol}{targets_c}"
                event_info_block = _format_block("EventInfo", event_info_content, 4)
                # Resolve conditional link
                cond_id_val_str = "0"
                if event.conditional:
                     if isinstance(event.conditional, Conditional):
                         cond_id_val_str = self._get_or_assign_id(event.conditional, "_pytol_cond")
                     elif isinstance(event.conditional, str):
                         cond_id_val_str = event.conditional
                     else:
                         try:
                             cond_id_val_str = str(int(event.conditional))
                         except ValueError:
                             self.logger.warning(f"Invalid conditional link '{event.conditional}' in sequence event.")
                # Format EVENT block
                events_c += f"\t\t\tEVENT{eol}\t\t\t{{{eol}" \
                            f"\t\t\t\tconditional = {cond_id_val_str}{eol}" \
                            f"\t\t\t\tdelay = {_format_value(event.delay)}{eol}" \
                            f"\t\t\t\tnodeName = {event.node_name}{eol}" \
                            f"{event_info_block}\t\t\t}}{eol}"
            # Format SEQUENCE block
            es_c += f"\t\tSEQUENCE{eol}\t\t{{{eol}" \
                    f"\t\t\tid = {seq.id}{eol}" \
                    f"\t\t\tsequenceName = {seq.sequence_name}{eol}" \
                    f"\t\t\tstartImmediately = {seq.start_immediately}{eol}" \
                    f"\t\t\twhileLoop = {seq.while_loop}{eol}" \
                    f"\t\t\tListOrderIndex = {seq.id * 10}{eol}" \
                    f"\t\t\tListFolderName = {eol}" \
                    f"{events_c}\t\t}}{eol}"

        # --- BRIEFING ---
        briefing_c = "".join([
            f"\t\tBRIEFING_NOTE{eol}\t\t{{{eol}"
            f"\t\t\ttext = {n.text}{eol}"
            f"\t\t\timagePath = {n.image_path or ''}{eol}"
            f"\t\t\taudioClipPath = {n.audio_clip_path or ''}{eol}"
            f"\t\t}}{eol}" for n in self.briefing_notes
        ])

        # --- RESOURCE MANIFEST ---
        resources_c = "".join([f"\t\t{k} = {v}{eol}" for k, v in self.resource_manifest.items()])


        # --- Return final dictionary ---
        return {
            "UNITS": units_c,
            "PATHS": paths_c,
            "WAYPOINTS": wpts_c,
            "UNITGROUPS": ug_c,             
            "TRIGGER_EVENTS": triggers_c,
            "OBJECTIVES": objs_c,
            "StaticObjects": statics_c,
            "BASES": bases_c,                
            "Conditionals": conditionals_c,  
            "ConditionalActions": ca_c,    
            "RandomEvents": re_c,          
            "EventSequences": es_c,        
            "GlobalValues": gv_c,          
            "Briefing": briefing_c,        
            "ResourceManifest": resources_c, 
            "TimedEventGroups": teg_c      
        }
        

    def _save_to_file(self, path: str):
        """Internal method to generate and write the VTS file content."""
        c = self._generate_content_string()
        eol = "\n"
        vts = f"CustomScenario{eol}{{{eol}"

        # --- Root properties ---
        root_props = [
            f"\tgameVersion = {self.game_version}",
            f"\tcampaignID = {self.campaign_id}",
            f"\tcampaignOrderIdx = {self.campaign_order_idx}",
            f"\tscenarioName = {self.scenario_name}",
            f"\tscenarioID = {self.scenario_id}",
            f"\tscenarioDescription = {self.scenario_description}",
            f"\tmapID = {self.map_id}",
            f"\tvehicle = {self.vehicle}",
            f"\tmultiplayer = {self.multiplayer}",
            f"\tallowedEquips = {self.allowed_equips}",
            f"\tforcedEquips = {self.forced_equips}",
            f"\tforceEquips = {self.force_equips}",
            f"\tnormForcedFuel = {self.norm_forced_fuel}",
            f"\tequipsConfigurable = {self.equips_configurable}",
            f"\tbaseBudget = {self.base_budget}",
            f"\tisTraining = {self.is_training}",
            f"\trtbWptID = {self.rtb_wpt_id}",
            f"\trefuelWptID = {self.refuel_wpt_id}",
        ]
        
        # Add multiplayer-specific properties if multiplayer is enabled
        if self.multiplayer:
            root_props.extend([
                f"\tmpPlayerCount = {self.mp_player_count}",
                f"\tautoPlayerCount = {self.auto_player_count}",
                f"\toverrideAlliedPlayerCount = {self.override_allied_player_count}",
                f"\toverrideEnemyPlayerCount = {self.override_enemy_player_count}",
                f"\tscorePerDeath_A = {self.score_per_death_a}",
                f"\tscorePerDeath_B = {self.score_per_death_b}",
                f"\tscorePerKill_A = {self.score_per_kill_a}",
                f"\tscorePerKill_B = {self.score_per_kill_b}",
                f"\tmpBudgetMode = {self.mp_budget_mode}",
                f"\trtbWptID_B = {self.rtb_wpt_id_b}",
                f"\trefuelWptID_B = {self.refuel_wpt_id_b}",
                f"\tseparateBriefings = {self.separate_briefings}",
                f"\tbaseBudgetB = {self.base_budget_b}",
            ])
        
        # Add common properties
        root_props.extend([
            f"\tinfiniteAmmo = {self.infinite_ammo}",
            f"\tinfAmmoReloadDelay = {self.inf_ammo_reload_delay}",
            f"\tfuelDrainMult = {self.fuel_drain_mult}",
            f"\tenvName = {self.env_name}",
            f"\tselectableEnv = {self.selectable_env}",
            f"\twindDir = {self.wind_dir}",
            f"\twindSpeed = {self.wind_speed}",
            f"\twindVariation = {self.wind_variation}",
            f"\twindGusts = {self.wind_gusts}",
            f"\tdefaultWeather = {self.default_weather}",
            f"\tcustomTimeOfDay = {self.custom_time_of_day}",
            f"\toverrideLocation = {self.override_location}",
            f"\toverrideLatitude = {self.override_latitude}",
            f"\toverrideLongitude = {self.override_longitude}",
            f"\tmonth = {self.month}",
            f"\tday = {self.day}",
            f"\tyear = {self.year}",
            f"\ttimeOfDaySpeed = {self.time_of_day_speed}",
            f"\tqsMode = {self.qs_mode}",
            f"\tqsLimit = {self.qs_limit}",
        ])
        vts += eol.join(root_props) + eol

        vts += _format_block("WEATHER_PRESETS", "") # TODO
        vts += _format_block("UNITS", c["UNITS"])
        vts += _format_block("PATHS", c["PATHS"])
        vts += _format_block("WAYPOINTS", c["WAYPOINTS"])
        vts += _format_block("UNITGROUPS", c["UNITGROUPS"])           
        vts += _format_block("TimedEventGroups", c["TimedEventGroups"]) 
        vts += _format_block("TRIGGER_EVENTS", c["TRIGGER_EVENTS"])
        vts += _format_block("OBJECTIVES", c["OBJECTIVES"])
        vts += _format_block("OBJECTIVES_OPFOR", "") # TODO
        vts += _format_block("StaticObjects", c["StaticObjects"])
        vts += _format_block("Conditionals", c["Conditionals"])       
        vts += _format_block("ConditionalActions", c["ConditionalActions"]) 
        vts += _format_block("RandomEvents", c["RandomEvents"])         
        vts += _format_block("EventSequences", c["EventSequences"])     
        vts += _format_block("BASES", c["BASES"])                  
        vts += _format_block("GlobalValues", c["GlobalValues"])         
        vts += _format_block("Briefing", c["Briefing"])

        if c["ResourceManifest"]:
            vts += _format_block("ResourceManifest", c["ResourceManifest"])

        vts += f"}}{eol}"

        # Write as binary UTF-8 to enforce LF line endings and no BOM
        with open(path, "wb") as f:
            f.write(vts.encode("utf-8"))

        self.logger.info(f"✅ Mission saved '{path}' (UTF-8 no BOM, LF line endings)")

    def save_mission(self, base_path: str) -> str:
        """
        Saves the mission .vts file and copies the associated map folder
        into the specified base path. Also copies any resource files added
        via add_resource() to their appropriate subdirectories.
        """
        mission_dir = os.path.join(base_path, self.scenario_id)
        os.makedirs(mission_dir, exist_ok=True)
        
        shutil.copytree(
            self.map_path, 
            os.path.join(mission_dir, self.map_id), 
            dirs_exist_ok=True
        )
        
        # Copy resource files and update paths to relative
        if self.resource_manifest:
            for res_id, source_path in list(self.resource_manifest.items()):
                # Determine subdirectory based on file extension
                ext = os.path.splitext(source_path)[1].lower()
                if ext in ['.wav', '.ogg', '.mp3']:
                    subdir = 'audio'
                elif ext in ['.png', '.jpg', '.jpeg', '.bmp']:
                    subdir = 'images'
                else:
                    self.logger.warning(f"Unknown resource file extension '{ext}' for resource {res_id}")
                    subdir = 'resources'
                
                # Create subdirectory
                dest_dir = os.path.join(mission_dir, subdir)
                os.makedirs(dest_dir, exist_ok=True)
                
                # Copy file
                filename = os.path.basename(source_path)
                dest_path = os.path.join(dest_dir, filename)
                
                try:
                    shutil.copy2(source_path, dest_path)
                    # Update manifest to relative path
                    relative_path = f"{subdir}/{filename}"
                    self.resource_manifest[res_id] = relative_path
                    self.logger.info(f"✅ Copied resource {res_id}: {filename} → {relative_path}")
                except Exception as e:
                    self.logger.info(f"❌ Error copying resource {res_id} from '{source_path}': {e}")
        
        vts_path = os.path.join(mission_dir, f"{self.scenario_id}.vts")
        self._save_to_file(vts_path)
        
        return mission_dir
