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
                 vtol_directory: str = ''):
        """Initializes a new VTOL VR Mission."""
        self.scenario_name = scenario_name
        self.scenario_id = scenario_id
        self.scenario_description = description if description else ""
        self.vehicle = vehicle

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

        self.tc = TerrainCalculator(self.map_id, self.map_path, vtol_directory)
        self.helper = MissionTerrainHelper(self.tc)

        # --- Default Game Properties --- (No changes needed here)
        self.game_version = "1.12.6f1"
        self.campaign_id = ""
        self.campaign_order_idx = -1
        self.multiplayer = False
        self.allowed_equips = "gau-8;m230;h70-x7;h70-4x4;h70-x19;mk82x1;mk82x2;mk82x3;mk82HDx1;mk82HDx2;mk82HDx3;agm89x1;gbu38x1;gbu38x2;gbu38x3;gbu39x3;gbu39x4u;cbu97x1;hellfirex4;maverickx1;maverickx3;cagm-6;sidewinderx1;sidewinderx2;sidewinderx3;iris-t-x1;iris-t-x2;iris-t-x3;sidearmx1;sidearmx2;sidearmx3;marmx1;av42_gbu12x1;av42_gbu12x2;av42_gbu12x3;42c_aim9ex2;42c_aim9ex1;"
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
        elif isinstance(obj, Conditional):
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
                    print(f"Warning: {obj_type_name} object was already added with ID '{assigned_id}'. Ignoring user ID '{user_provided_id}'.")
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
                print(f"Assigning automatic integer ID '{assigned_id}' to {obj_type_name} '{getattr(obj, 'name', '')}'")
            else: # Should only be string type left (Conditionals)
                assigned_id = f"{prefix}_{assigned_id}" # Format the string ID using the counter number
                print(f"Assigning automatic string ID '{assigned_id}' to {obj_type_name} '{getattr(obj, 'name', '')}'")

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
        uid = len(self.units)

        # --- Attach Action Helper ---
        ActionClass = UNIT_CLASS_TO_ACTION_CLASS.get(type(unit_obj))
        if ActionClass:
            # Pass the instance ID (uid) as the target_id for VTS events
            unit_obj.actions = ActionClass(target_id=uid)
            print(f"  > Attached actions helper '{ActionClass.__name__}' to unit {uid}")
        else:
            print(f"  > Warning: No action helper found for unit type {type(unit_obj).__name__}")

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
            print(f"Placing unit {uid} ('{unit_obj.unit_name}') on carrier.")
            editor_mode = "Ground" # Assuming ground mode for carrier placement
        elif placement == "ground":
            if use_smart_placement:
                print(f"Attempting smart placement for unit {uid} at ({x:.2f}, {z:.2f})...")
                try:
                    # Use the comprehensive smart placement function from TerrainCalculator
                    placement_info = self.tc.get_smart_placement(x, z, initial_yaw)
                    placement_type = placement_info['type']
                    final_pos = list(placement_info['position'])
                    final_rot = list(placement_info['rotation']) # Use rotation from smart placement
                    print(f"  > Smart placement result: {placement_type} at {final_pos[1]:.2f}m")

                    # Set editor mode based on type
                    if placement_type in ['static_prefab_roof', 'city_roof', 'road', 'terrain']:
                        editor_mode = "Ground"

                    # Override rotation if alignment is disabled for terrain/road
                    if placement_type in ['terrain', 'road'] and not align_to_surface:
                        print("  > Disabling surface alignment (keeping original yaw).")
                        final_rot = [0.0, initial_yaw, 0.0] # Keep only yaw
                    elif placement_type in ['static_prefab_roof', 'city_roof']:
                        # Roofs are typically flat, keep only yaw regardless of align_to_surface
                        print("  > Setting flat rotation for roof placement.")
                        final_rot = [0.0, initial_yaw, 0.0] # Keep only yaw


                except Exception as e:
                    print(f"Warning: Smart placement failed for unit {uid}: {e}. Falling back.")
                    # Fallback to simple ground placement using get_asset_placement
                    try:
                        placement_info = self.tc.get_asset_placement(x, z, initial_yaw)
                        final_pos = list(placement_info['position'])
                        final_rot = list(placement_info['rotation'])
                        editor_mode = "Ground"
                        if not align_to_surface:
                            print("  > Disabling surface alignment (Fallback - keeping original yaw).")
                            final_rot = [0.0, initial_yaw, 0.0]
                        print(f"  > Fallback placement: terrain at {final_pos[1]:.2f}m")
                    except Exception as e2:
                        print(f"Warning: Fallback placement failed for unit {uid}: {e2}. Using original Y.")
                        final_pos = initial_pos # Revert to original position
                        final_rot = initial_rot
                        editor_mode = "Air" # Final fallback

            else: # Simple ground placement (use_smart_placement is False)
                print(f"Placing unit {uid} ('{unit_obj.unit_name}') on ground (simple) at ({x:.2f}, {z:.2f}).")
                try:
                    # Use get_asset_placement for simple height + optional rotation
                    placement_info = self.tc.get_asset_placement(x, z, initial_yaw)
                    final_pos = list(placement_info['position'])
                    final_rot = list(placement_info['rotation'])
                    editor_mode = "Ground"
                    if not align_to_surface:
                        print("  > Disabling surface alignment (Simple - keeping original yaw).")
                        final_rot = [0.0, initial_yaw, 0.0] # Keep only yaw
                    print(f"  > Simple placement: terrain at {final_pos[1]:.2f}m")
                except Exception as e:
                    print(f"Warning: Simple ground placement failed for unit {uid}: {e}. Using original Y.")
                    final_pos = initial_pos # Revert to original
                    final_rot = initial_rot
                    editor_mode = "Air" # Fallback

        elif placement == "sea":
            print(f"Placing unit {uid} ('{unit_obj.unit_name}') on sea at ({x:.2f}, {z:.2f}).")
            adjusted_y = self.tc.get_terrain_height(x, z)
            final_pos[1] = max(adjusted_y, 0) # Use terrain height but >= 0
            editor_mode = "Water"
            # Sea is flat, clear X/Z rotation, keep original yaw
            final_rot = [0.0, initial_yaw, 0.0]

        elif placement == "relative_airborne":
            if altitude_agl is None:
                raise ValueError("altitude_agl must be provided for placement='relative_airborne'")
            print(f"Placing unit {uid} ('{unit_obj.unit_name}') at {altitude_agl}m AGL above ({x:.2f}, {z:.2f}).")
            ground_y = self.tc.get_terrain_height(x, z)
            final_pos[1] = ground_y + altitude_agl
            editor_mode = "Air"
            # Keep original rotation

        elif placement == "airborne":
            print(f"Placing unit {uid} ('{unit_obj.unit_name}') airborne at provided coordinates.")
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
        print(f"Unit '{unit_obj.unit_name}' added (ID: {uid}) with final pos: [{final_pos[0]:.2f}, {final_pos[1]:.2f}, {final_pos[2]:.2f}] rot: [{final_rot[0]:.2f}, {final_rot[1]:.2f}, {final_rot[2]:.2f}] mode: {editor_mode}")
        return uid
    
    def add_path(self, path_obj: Path, path_id: Optional[int] = None) -> str:
        """Adds a Path object, assigning an ID if needed."""
        if not isinstance(path_obj, Path):
            raise TypeError("path_obj must be a Path dataclass.")
        assigned_id = self._get_or_assign_id(path_obj, "_pytol_path", path_id)
        # Ensure the object has the final ID stored if it has an 'id' field
        if hasattr(path_obj, 'id') and path_obj.id != assigned_id:
             path_obj.id = assigned_id
        print(f"Ruta '{path_obj.name}' added with ID '{assigned_id}'.")
        return assigned_id

    def add_waypoint(self, waypoint_obj: Waypoint, waypoint_id: Optional[int] = None) -> int:
        """Adds a Waypoint object, assigning an ID if needed."""
        if not isinstance(waypoint_obj, Waypoint):
            raise TypeError("waypoint_obj must be a Waypoint dataclass.")
        assigned_id = self._get_or_assign_id(waypoint_obj, "_pytol_wpt", waypoint_id)
        if waypoint_obj.id != assigned_id:
            waypoint_obj.id = assigned_id
        print(f"Waypoint '{waypoint_obj.name}' added with ID '{assigned_id}'.")
        return assigned_id

    def add_unit_to_group(self, team: str, group_name: str, unit_instance_id: int): # Unchanged
        """Assigns a unit (by its instance ID) to a unit group."""
        team_upper = team.upper(); group = self.unit_groups.setdefault(team_upper, {})
        group.setdefault(group_name, []).append(unit_instance_id)

    def add_objective(self, objective_obj: Objective) -> int:
        """Adds an Objective object, ensuring its ID is tracked."""
        if not isinstance(objective_obj, Objective):
            raise TypeError("objective_obj must be an Objective dataclass.")
        # Objective ID is required and comes *from* the object
        assigned_id = self._get_or_assign_id(objective_obj, "_pytol_obj")
        print(f"Objetivo '{objective_obj.name}' (ID: {assigned_id}) tracked.")
        return assigned_id

    def add_static_object(self, static_obj: StaticObject) -> int:
        """Adds a StaticObject object. ID is its index."""
        if not isinstance(static_obj, StaticObject):
            raise TypeError("static_obj must be a StaticObject dataclass.")
        sid = self._static_object_next_id
        self.static_objects.append(static_obj)
        self._static_object_next_id += 1
        print(f"StaticObject '{static_obj.prefab_id}' added (ID: {sid})")
        return sid

    def add_trigger_event(self, trigger_obj: Trigger) -> int:
        """Adds a Trigger object, ensuring its ID is tracked."""
        if not isinstance(trigger_obj, Trigger):
            raise TypeError("trigger_obj must be a Trigger dataclass.")
        # Trigger ID is required and comes *from* the object
        assigned_id = self._get_or_assign_id(trigger_obj, "_pytol_trig")
        print(f"Trigger '{trigger_obj.name}' (ID: {assigned_id}) tracked.")
        return assigned_id

    def add_base(self, base_obj: Base): # Unchanged logic, just type hint
        """Adds a Base object."""
        if not isinstance(base_obj, Base):
            raise TypeError("base_obj must be a Base dataclass.")
        if any(b.id == base_obj.id for b in self.bases):
             print(f"Warning: Base ID {base_obj.id} already exists.")
        self.bases.append(base_obj)
        print(f"Base '{base_obj.name or base_obj.id}' added (ID: {base_obj.id}).")

    def add_briefing_note(self, note_obj: BriefingNote): # Unchanged logic, just type hint
        """Adds a BriefingNote object."""
        if not isinstance(note_obj, BriefingNote):
            raise TypeError("note_obj must be a BriefingNote dataclass.")
        self.briefing_notes.append(note_obj)

    def add_resource(self, res_id: int, path: str): # TODO: Pass path to file in system and then copy that img or audio to the mission folder
        """Adds a resource to the ResourceManifest."""
        if res_id in self.resource_manifest:
            print(f"Warning: Overwriting resource with ID {res_id}")
        self.resource_manifest[res_id] = path

    def add_conditional(self, conditional_obj: Conditional, conditional_id: Optional[str] = None) -> str:
        """Adds a Conditional object, assigning an ID if needed."""
        if not isinstance(conditional_obj, Conditional):
            raise TypeError("conditional_obj must be a Conditional dataclass.")
        assigned_id = self._get_or_assign_id(conditional_obj, "_pytol_cond", conditional_id)
        # Conditionals don't have an 'id' field in their dataclass
        print(f"Conditional added with ID '{assigned_id}'.")
        return assigned_id

    def add_global_value(self, gv_obj: GlobalValue):
        """Adds a GlobalValue object to the mission."""
        if not isinstance(gv_obj, GlobalValue):
            raise TypeError("gv_obj must be a GlobalValue dataclass.")
        if gv_obj.name in self.global_values:
            print(f"Warning: GlobalValue name '{gv_obj.name}' already exists. Overwriting.")
        self.global_values[gv_obj.name] = gv_obj
        print(f"GlobalValue '{gv_obj.name}' added (initial value: {gv_obj.initial_value}).")

    def add_conditional_action(self, ca_obj: ConditionalAction):
        """Adds a ConditionalAction object to the mission."""
        if not isinstance(ca_obj, ConditionalAction):
            raise TypeError("ca_obj must be a ConditionalAction dataclass.")
        if any(ca.id == ca_obj.id for ca in self.conditional_actions):
            print(f"Warning: ConditionalAction ID {ca_obj.id} already exists.")
        # Ensure the linked conditional ID actually exists (optional check)
        if ca_obj.conditional_id not in self.conditionals:
            print(f"Warning: ConditionalAction '{ca_obj.name}' links to non-existent Conditional ID '{ca_obj.conditional_id}'.")

        self.conditional_actions.append(ca_obj)
        print(f"ConditionalAction '{ca_obj.name}' added (ID: {ca_obj.id}), linked to Conditional '{ca_obj.conditional_id}'.")

    def add_timed_event_group(self, timed_event_group_obj: TimedEventGroup):
        """Adds a TimedEventGroup object to the mission."""
        if not isinstance(timed_event_group_obj, TimedEventGroup):
            raise TypeError("timed_event_group_obj must be a TimedEventGroup dataclass.")
        if any(g.group_id == timed_event_group_obj.group_id for g in self.timed_event_groups):
            print(f"Warning: TimedEventGroup ID {timed_event_group_obj.group_id} already exists.")
        self.timed_event_groups.append(timed_event_group_obj)
        print(f"TimedEventGroup '{timed_event_group_obj.group_name}' added (ID: {timed_event_group_obj.group_id}).")
    

    def add_event_sequence(self, seq_obj: EventSequence):
        """Adds an EventSequence object to the mission."""
        if not isinstance(seq_obj, EventSequence):
            raise TypeError("seq_obj must be an EventSequence dataclass.")
        if any(seq.id == seq_obj.id for seq in self.event_sequences):
            print(f"Warning: EventSequence ID {seq_obj.id} already exists.")
        # Optional: Check linked conditionals within sequence events
        for event in seq_obj.events:
            if isinstance(event.conditional, str) and event.conditional not in self.conditionals:
                print(f"Warning: EventSequence '{seq_obj.sequence_name}' step '{event.node_name}' links to non-existent Conditional ID '{event.conditional}'.")

        self.event_sequences.append(seq_obj)
        print(f"EventSequence '{seq_obj.sequence_name}' added (ID: {seq_obj.id}).")

    def add_random_event(self, re_obj: RandomEvent):
        """Adds a RandomEvent object (container for actions) to the mission."""
        if not isinstance(re_obj, RandomEvent):
            raise TypeError("re_obj must be a RandomEvent dataclass.")
        if any(re.id == re_obj.id for re in self.random_events):
            print(f"Warning: RandomEvent ID {re_obj.id} already exists.")
        # Optional: Check linked conditionals within action options
        for action_option in re_obj.action_options:
            if isinstance(action_option.conditional, str) and action_option.conditional not in self.conditionals:
                print(f"Warning: RandomEvent '{re_obj.name}' action ID {action_option.id} links to non-existent Conditional ID '{action_option.conditional}'.")

        self.random_events.append(re_obj)
        print(f"RandomEvent '{re_obj.name}' added (ID: {re_obj.id}).")

    def _format_conditional(self, cond_id: str, cond: Conditional) -> str: # Unchanged
        """Formats a single Conditional dataclass into a VTS string."""
        # ... (implementation remains the same, uses cond_id passed in) ...
        eol = "\n"; indent = "\t\t"
        cond_type = CLASS_TO_ID.get(cond.__class__)
        if not cond_type: raise TypeError(f"Unknown conditional type: {cond.__class__.__name__}")
        content_c = f"{indent}\tid = {cond_id}{eol}{indent}\ttype = {cond_type}{eol}"
        if not is_dataclass(cond): return ""
        for f in fields(cond):
            value = getattr(cond, f.name); key_name = f.name
            if value is None: continue
            formatted_value = ";".join(map(str, value)) + ";" if isinstance(value, list) else _format_value(value)
            content_c += f"{indent}\t{key_name} = {formatted_value}{eol}"
        return f"{indent}Conditional{eol}{indent}{{{eol}{content_c}{indent}}}{eol}"


    def _generate_content_string(self) -> Dict[str, str]:
        """Internal function to generate the content for all VTS blocks."""
        eol = "\n"

        # --- UNITS --- (No ID changes needed)
        units_c = ""
        for u_data in self.units:
            u = u_data['unit_obj']
            fields_c = "".join([f"\t\t\t\t{_snake_to_camel(k)} = {_format_value(v)}{eol}" for k,v in u.unit_fields.items()])

            # Add spawnChance and spawnFlags lines
            spawn_chance_line = f"\t\t\tspawnChance = {u_data.get('spawn_chance', 100)}{eol}"
            spawn_flags_val = u_data.get('spawn_flags')
            spawn_flags_line = f"\t\t\tspawnFlags = {spawn_flags_val if spawn_flags_val is not None else ''}{eol}" # Ensure empty string if None

            units_c += f"\t\tUnitSpawner{eol}\t\t{{{eol}" \
                    f"\t\t\tunitName = {u.unit_name}{eol}" \
                    f"\t\t\tglobalPosition = {_format_vector(u.global_position)}{eol}" \
                    f"\t\t\tunitInstanceID = {u_data['unitInstanceID']}{eol}" \
                    f"\t\t\tunitID = {u.unit_id}{eol}" \
                    f"\t\t\trotation = {_format_vector(u.rotation)}{eol}" \
                    f"{spawn_chance_line}" \
                    f"\t\t\tlastValidPlacement = {_format_vector(u_data['lastValidPlacement'])}{eol}" \
                    f"{spawn_flags_line}" \
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
            team_c = "".join([f"\t\t\t{name} = 2;{_format_id_list(ids)};{eol}" for name, ids in groups.items()])
            ug_c += _format_block(team, team_c, 2)

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

            props_c = "".join([f"\t\t\t{k} = {_format_value(v)}{eol}" for k, v in resolved_props.items()])

            targets_c = "" # EventTarget formatting remains the same
            for target in t.event_targets:
                params_c = "".join([
                    f"\t\t\t\t\tParamInfo{eol}\t\t\t\t\t{{{eol}"
                    f"\t\t\t\t\t\ttype = {p.type}{eol}"
                    f"\t\t\t\t\t\tvalue = {_format_value(p.value)}{eol}" # Use format_value for param values
                    f"\t\t\t\t\t\tname = {p.name}{eol}"
                    f"\t\t\t\t\t}}{eol}" for p in target.params
                ])
                targets_c += f"\t\t\t\tEventTarget{eol}\t\t\t\t{{{eol}" \
                            f"\t\t\t\t\ttargetType = {target.target_type}{eol}" \
                            f"\t\t\t\t\ttargetID = {target.target_id}{eol}" \
                            f"\t\t\t\t\teventName = {target.event_name}{eol}" \
                            f"\t\t\t\t\t\tmethodName = {target.method_name or target.event_name}{eol}" \
                            f"{params_c}\t\t\t\t}}{eol}"
            event_info = _format_block('EventInfo', f"\t\t\t\teventName = {eol}{targets_c}", 3)

            triggers_c += f"\t\tTriggerEvent{eol}\t\t{{{eol}" \
                        f"\t\t\tid = {t.id}{eol}" \
                        f"\t\t\tenabled = {t.enabled}{eol}" \
                        f"\t\t\ttriggerType = {t.trigger_type}{eol}" \
                        f"\t\t\tname = {t.name}{eol}" \
                        f"{props_c}{event_info}\t\t}}{eol}"

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
                        param_info_block = f"\t\t\t\t\t\tParamInfo{eol}\t\t\t\t\t\t{{{eol}" \
                                        f"\t\t\t\t\t\t\ttype = {p.type}{eol}" \
                                        f"\t\t\t\t\t\t\tvalue = {_format_value(param_value)}{eol}" \
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
                        print(f"Warning: targetID for UnitGroup '{target.target_id}' should likely be an integer.")
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
                events_c += f"\t\t\t\tTimedEventInfo{eol}\t\t\t\t{{{eol}" \
                            f"\t\t\t\t\teventName = {event_info.event_name}{eol}" \
                            f"\t\t\t\t\ttime = {_format_value(event_info.time)}{eol}" \
                            f"{targets_c}\t\t\t\t}}{eol}"

            # Format TimedEventGroup block
            teg_c += f"\t\tTimedEventGroup{eol}\t\t{{{eol}" \
                    f"\t\t\tgroupName = {group.group_name}{eol}" \
                    f"\t\t\tgroupID = {group.group_id}{eol}" \
                    f"\t\t\tbeginImmediately = {group.begin_immediately}{eol}" \
                    f"\t\t\tinitialDelay = {_format_value(group.initial_delay)}{eol}" \
                    f"{events_c}\t\t}}{eol}"
        
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
                        print(f"Warning: Invalid type for objective prereq: {type(prereq)}. Skipping.")


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
                        param_info_block = f"\t\t\t\t\tParamInfo{eol}\t\t\t\t\t{{{eol}" \
                                           f"\t\t\t\t\t\ttype = {p.type}{eol}" \
                                           f"\t\t\t\t\t\tvalue = {_format_value(param_value)}{eol}" \
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
                              print(f"Warning: EventTarget for Unit should use integer unitInstanceID, got {target.target_id}. Attempting conversion.")
                              try: target_id_val = int(target.target_id)
                              except ValueError: print(f"  > Error: Could not convert Unit target ID to int for objective {o.objective_id}")
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
                    event_info_content = f"\t\t\t\teventName = {event_info_name}{eol}{targets_c}"
                else:
                    event_info_content = f"\t\t\t\teventName = {event_info_name}{eol}" # Empty if no targets

                event_info_block = _format_block("EventInfo", event_info_content, 4)
                return _format_block(event_block_name, event_info_block, 3)

            # Generate the blocks using the helper function
            start_event_block = format_objective_event("startEvent", "Start Event", o.start_event_targets)
            fail_event_block = format_objective_event("failEvent", "Failed Event", o.fail_event_targets)
            complete_event_block = format_objective_event("completeEvent", "Completed Event", o.complete_event_targets)

            obj_str = f"\t\tObjective{eol}\t\t{{{eol}" \
                    f"\t\t\tobjectiveName = {o.name}{eol}" \
                    f"\t\t\tobjectiveInfo = {o.info}{eol}" \
                    f"\t\t\tobjectiveID = {o.objective_id}{eol}" \
                    f"\t\t\torderID = {o.orderID}{eol}" \
                    f"\t\t\trequired = {o.required}{eol}" \
                    f"\t\t\tcompletionReward = {o.completionReward}{eol}" \
                    f"\t\t\twaypoint = {waypoint_id}{eol}" \
                    f"\t\t\tautoSetWaypoint = {o.auto_set_waypoint}{eol}" \
                    f"\t\t\tstartMode = {'PreReqs' if prereq_ids else 'Immediate'}{eol}" \
                    f"\t\t\tobjectiveType = {o.type}{eol}" \
                    f"{start_event_block}" \
                    f"{fail_event_block}" \
                    f"{complete_event_block}" \
                    f"\t\t\tpreReqObjectives = {_format_id_list(prereq_ids)};{eol}" \
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
        for name, gv in self.global_values.items():
            gv_c += f"\t\tGlobalValue{eol}\t\t{{{eol}" \
                    f"\t\t\tname = {gv.name}{eol}" \
                    f"\t\t\tinitialValue = {_format_value(gv.initial_value)}{eol}" \
                    f"\t\t}}{eol}"

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
                              print(f"Warning: Could not find unitInstanceID for Unit param value in CondAction {ca.id}")
                    # TODO: Add checks for Conditional, etc. if actions can use them as param values

                    # --- Format ParamInfo block (with ParamAttrInfo) ---
                    param_info_block = f"\t\t\t\t\tParamInfo{eol}\t\t\t\t\t{{{eol}" \
                                       f"\t\t\t\t\t\ttype = {p.type}{eol}" \
                                       f"\t\t\t\t\t\tvalue = {_format_value(param_value)}{eol}" \
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
                        print(f"Warning: targetID for GlobalValue should be string name, got {target.target_id}")
                        target_id_val = str(target.target_id)
                elif target.target_type == "Unit":
                    if isinstance(target.target_id, Unit): # If Unit object passed
                         found_id = next((u['unitInstanceID'] for u in self.units if u['unit_obj'] is target.target_id), None)
                         if found_id is not None:
                              target_id_val = found_id
                         else:
                              print(f"Warning: Could not find unitInstanceID for Unit target ID in CondAction {ca.id}")
                    elif not isinstance(target.target_id, int): # Ensure it's an int if not an object
                         print(f"Warning: EventTarget for Unit should use integer unitInstanceID, got {target.target_id}. Attempting conversion.")
                         try: target_id_val = int(target.target_id)
                         except ValueError: print(f"  > Error: Could not convert Unit target ID to int for CondAction {ca.id}")
                elif target.target_type == "Waypoint":
                    if isinstance(target.target_id, Waypoint):
                        target_id_val = self._get_or_assign_id(target.target_id, "_pytol_wpt")
                    # Ensure it's an int if already provided
                    elif not isinstance(target_id_val, int):
                         try: target_id_val = int(target_id_val)
                         except ValueError: print(f"Warning: Waypoint target ID should be int, got {target_id_val}")
                elif target.target_type == "Path":
                     if isinstance(target.target_id, Path):
                          target_id_val = self._get_or_assign_id(target.target_id, "_pytol_path")
                     elif not isinstance(target_id_val, int):
                         try: target_id_val = int(target_id_val)
                         except ValueError: print(f"Warning: Path target ID should be int, got {target_id_val}")
                elif target.target_type == "Conditional":
                     if isinstance(target.target_id, Conditional):
                          target_id_val = self._get_or_assign_id(target.target_id, "_pytol_cond") # Ensure added, get ID
                     elif not isinstance(target_id_val, str):
                          print(f"Warning: Conditional target ID should be string, got {target_id_val}")
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
                            if found_id is not None: param_value = found_id
                            else: print(f"Warning: Could not find unitInstanceID for Unit param value in RandomEvent {re.id}, Action {action.id}")
                        # Format ParamInfo (with ParamAttrInfo)
                        param_info_block = f"\t\t\t\t\t\tParamInfo{eol}\t\t\t\t\t\t{{{eol}" \
                                           f"\t\t\t\t\t\t\ttype = {p.type}{eol}" \
                                           f"\t\t\t\t\t\t\tvalue = {_format_value(param_value)}{eol}" \
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
                         if isinstance(target.target_id, GlobalValue): target_id_val = target.target_id.name
                         elif not isinstance(target.target_id, str): target_id_val = str(target.target_id)
                    elif target.target_type == "Unit":
                         if isinstance(target.target_id, Unit):
                              found_id = next((u['unitInstanceID'] for u in self.units if u['unit_obj'] is target.target_id), None)
                              if found_id is not None: target_id_val = found_id
                              else: print(f"Warning: Could not find unitInstanceID for Unit target ID in RandomEvent {re.id}, Action {action.id}")
                         elif not isinstance(target.target_id, int):
                              try: target_id_val = int(target.target_id)
                              except ValueError: print(f"Warning: Unit target ID not int for RandomEvent {re.id}, Action {action.id}")
                    # ... etc. for Waypoint, Path, Conditional ...

                    # Format EventTarget
                    targets_c += f"\t\t\t\t\tEventTarget{eol}\t\t\t\t\t{{{eol}" \
                                f"\t\t\t\t\t\ttargetType = {target.target_type}{eol}" \
                                f"\t\t\t\t\t\ttargetID = {_format_value(target_id_val)}{eol}" \
                                f"\t\t\t\t\t\teventName = {target.event_name}{eol}" \
                                f"\t\t\t\t\t\tmethodName = {target.method_name or target.event_name}{eol}" \
                                f"{params_c}\t\t\t\t\t}}{eol}"

                # Format the EVENT_INFO block for this ACTION
                event_info_content = f"\t\t\t\t\teventName = {eol}{targets_c}"
                event_info_block = _format_block("EVENT_INFO", event_info_content, 5) # Indent 5

                # Resolve the ACTION's conditional link
                action_cond_id_val_str = "0" # Default is "0"
                if action.conditional:
                     if isinstance(action.conditional, Conditional):
                          action_cond_id_val_str = self._get_or_assign_id(action.conditional, "_pytol_cond")
                     elif isinstance(action.conditional, str):
                          action_cond_id_val_str = action.conditional
                          if action_cond_id_val_str not in self.conditionals:
                               print(f"Warning: RandomEvent Action {action.id} uses unknown conditional ID '{action_cond_id_val_str}'")
                     else: # Allow integer 0
                          try: action_cond_id_val_str = str(int(action.conditional))
                          except ValueError: print(f"Warning: Invalid conditional link '{action.conditional}' in RandomEvent Action.")
                # Format the nested CONDITIONAL block (using ID 0 as per example)
                # TODO: This assumes the internal conditional structure is simple; might need adjustment
                conditional_block_inner = f"\t\t\t\t\tCONDITIONAL{eol}\t\t\t\t\t{{{eol}" \
                                          f"\t\t\t\t\t\tid = {action_cond_id_val_str}{eol}" \
                                          f"\t\t\t\t\t\toutputNodePos = (0, 0, 0){eol}" \
                                          f"\t\t\t\t\t}}{eol}"


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
                actions_c += _format_block("ACTION", action_block_content, 4) # Indent 4

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
                        if isinstance(p.value, GlobalValue): param_value = p.value.name
                        elif isinstance(p.value, Waypoint): param_value = self._get_or_assign_id(p.value, "_pytol_wpt")
                        elif isinstance(p.value, Path): param_value = self._get_or_assign_id(p.value, "_pytol_path")
                        elif isinstance(p.value, Unit):
                            found_id = next((u['unitInstanceID'] for u in self.units if u['unit_obj'] is p.value), None)
                            if found_id is not None: param_value = found_id
                            else: print(f"Warning: Could not find unitInstanceID for Unit param value in EventSequence {seq.id}")
                        # Format ParamInfo (with ParamAttrInfo)
                        param_info_block = f"\t\t\t\t\tParamInfo{eol}\t\t\t\t\t{{{eol}" \
                                           f"\t\t\t\t\t\ttype = {p.type}{eol}" \
                                           f"\t\t\t\t\t\tvalue = {_format_value(param_value)}{eol}" \
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
                event_info_content = f"\t\t\t\teventName = {eol}{targets_c}"
                event_info_block = _format_block("EventInfo", event_info_content, 4)
                # Resolve conditional link
                cond_id_val_str = "0"
                if event.conditional:
                     if isinstance(event.conditional, Conditional): cond_id_val_str = self._get_or_assign_id(event.conditional, "_pytol_cond")
                     elif isinstance(event.conditional, str): cond_id_val_str = event.conditional
                     else:
                         try: cond_id_val_str = str(int(event.conditional))
                         except ValueError: print(f"Warning: Invalid conditional link '{event.conditional}' in sequence event.")
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
                    f"{events_c}\t\t}}{eol}"

        # --- GLOBAL VALUES ---
        gv_c = ""
        for name, gv in self.global_values.items():
            # Example VTS uses 'gv { data = id;name;;value; }' format
            # This seems editor specific. Let's try a simpler format first.
            # TODO: Verify correct GlobalValue block format if this doesn't work.
            gv_c += f"\t\tGlobalValue{eol}\t\t{{{eol}" \
                    f"\t\t\tname = {gv.name}{eol}" \
                    f"\t\t\tinitialValue = {_format_value(gv.initial_value)}{eol}" \
                    f"\t\t}}{eol}"
            # Alternate format based on example1.vts 'gv { data = ... }'
            # gv_id = list(self.global_values.keys()).index(name) # Get index as ID
            # gv_data = f"{gv_id};{gv.name};;{_format_value(gv.initial_value)};"
            # gv_c += f"\t\tgv{eol}\t\t{{{eol}" \
            #         f"\t\t\tdata = {gv_data}{eol}" \
            #         # Ignoring ListOrderIndex, ListFolderName
            #         f"\t\t}}{eol}"


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
            "UNITS": units_c, "PATHS": paths_c, "WAYPOINTS": wpts_c, "UNITGROUPS": ug_c,
            "TRIGGER_EVENTS": triggers_c, "OBJECTIVES": objs_c, "StaticObjects": statics_c,
            "BASES": bases_c,"Conditionals": conditionals_c, "ConditionalActions": ca_c,
            "RandomEvents": re_c, "EventSequences": es_c, "GlobalValues": gv_c,
            "Briefing": briefing_c, "ResourceManifest": resources_c,
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
            f"\tforceEquips = {self.force_equips}",
            f"\tnormForcedFuel = {self.norm_forced_fuel}",
            f"\tequipsConfigurable = {self.equips_configurable}",
            f"\tbaseBudget = {self.base_budget}",
            f"\tisTraining = {self.is_training}",
            f"\trtbWptID = {self.rtb_wpt_id}",
            f"\trefuelWptID = {self.refuel_wpt_id}",
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
        ]
        vts += eol.join(root_props) + eol

        # --- VTS Block Order (Important!) ---
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
        vts += _format_block("ConditionalActions", "")
        vts += _format_block("RandomEvents", "")
        vts += _format_block("EventSequences", "")
        vts += _format_block("BASES", c["BASES"])
        vts += _format_block("GlobalValues", "")
        vts += _format_block("Briefing", c["Briefing"])

        if c["ResourceManifest"]:
            vts += _format_block("ResourceManifest", c["ResourceManifest"])

        vts += f"}}{eol}"

        # Write as binary UTF-8 to enforce LF line endings and no BOM
        with open(path, "wb") as f:
            f.write(vts.encode("utf-8"))

        print(f"✅ Mission saved '{path}' (UTF-8 no BOM, LF line endings)")

    def save_mission(self, base_path: str) -> str:
        """
        Saves the mission .vts file and copies the associated map folder
        into the specified base path.
        """
        mission_dir = os.path.join(base_path, self.scenario_id)
        os.makedirs(mission_dir, exist_ok=True)
        
        shutil.copytree(
            self.map_path, 
            os.path.join(mission_dir, self.map_id), 
            dirs_exist_ok=True
        )
        
        vts_path = os.path.join(mission_dir, f"{self.scenario_id}.vts")
        self._save_to_file(vts_path)
        
        return mission_dir