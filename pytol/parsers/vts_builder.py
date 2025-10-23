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
    Waypoint, StaticObject, Base, BriefingNote
)

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

        # --- Default Game Properties --- (No changes needed here)
        self.game_version = "1.12.6f1"; self.campaign_id = ""; self.campaign_order_idx = -1
        self.multiplayer = False; self.allowed_equips = "gau-8;m230;h70-x7;h70-4x4;h70-x19;mk82x1;mk82x2;mk82x3;mk82HDx1;mk82HDx2;mk82HDx3;agm89x1;gbu38x1;gbu38x2;gbu38x3;gbu39x3;gbu39x4u;cbu97x1;hellfirex4;maverickx1;maverickx3;cagm-6;sidewinderx1;sidewinderx2;sidewinderx3;iris-t-x1;iris-t-x2;iris-t-x3;sidearmx1;sidearmx2;sidearmx3;marmx1;av42_gbu12x1;av42_gbu12x2;av42_gbu12x3;42c_aim9ex2;42c_aim9ex1;"
        self.force_equips = False; self.norm_forced_fuel = 1; self.equips_configurable = True
        self.base_budget = 100000; self.is_training = False; self.infinite_ammo = False
        self.inf_ammo_reload_delay = 5; self.fuel_drain_mult = 1; self.rtb_wpt_id = ""; self.refuel_wpt_id = ""
        self.env_name = ""; self.selectable_env = False; self.wind_dir = 0; self.wind_speed = 0
        self.wind_variation = 0; self.wind_gusts = 0; self.default_weather = 0; self.custom_time_of_day = 11
        self.override_location = False; self.override_latitude = 0; self.override_longitude = 0
        self.month = 1; self.day = 1; self.year = 2024; self.time_of_day_speed = 1
        self.qs_mode = "Anywhere"; self.qs_limit = -1

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

        # --- NEW: Internal ID Management ---
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

    def add_unit(self, 
                 unit_obj: Unit, 
                 editor_placement_mode: str = "Ground", 
                 on_carrier: bool = False, 
                 mp_select_enabled: bool = True) -> int:
        
        """Adds a Unit object to the mission."""
        # Units use instanceID managed here, not _get_or_assign_id
        if not isinstance(unit_obj, Unit):
            raise TypeError(f"unit_obj must be a Unit dataclass, not {type(unit_obj)}")
        uid = len(self.units)
        unit_data = {
            'unit_obj': unit_obj, 'unitInstanceID': uid,
            'lastValidPlacement': unit_obj.global_position,
            'editorPlacementMode': editor_placement_mode,
            'onCarrier': on_carrier, 'mpSelectEnabled': mp_select_enabled
        }
        self.units.append(unit_data)
        print(f"Unit '{unit_obj.unit_name}' added (ID: {uid})")
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

    def add_waypoint(self, waypoint_obj: Waypoint, waypoint_id: Optional[int] = None) -> str:
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

    def add_resource(self, res_id: str, path: str): # Unchanged
        """Adds a resource to the ResourceManifest."""
        self.resource_manifest[res_id] = path

    def add_conditional(self, conditional_obj: Conditional, conditional_id: Optional[str] = None) -> str:
        """Adds a Conditional object, assigning an ID if needed."""
        if not isinstance(conditional_obj, Conditional):
            raise TypeError("conditional_obj must be a Conditional dataclass.")
        assigned_id = self._get_or_assign_id(conditional_obj, "_pytol_cond", conditional_id)
        # Conditionals don't have an 'id' field in their dataclass
        print(f"Conditional added with ID '{assigned_id}'.")
        return assigned_id


    # --- Internal VTS Generation Methods ---

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
        wpts_c = "".join([
            f"\t\tWAYPOINT{eol}\t\t{{{eol}"
            f"\t\t\tid = {w.id}{eol}"
            f"\t\t\tname = {w.name}{eol}"
            f"\t\t\tglobalPoint = {_format_vector(w.global_point)}{eol}"
            f"\t\t}}{eol}" for w in self.waypoints
        ])

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
                            f"{params_c}\t\t\t\t}}{eol}"
            event_info = _format_block('EventInfo', f"\t\t\t\teventName = {eol}{targets_c}", 3)

            triggers_c += f"\t\tTriggerEvent{eol}\t\t{{{eol}" \
                        f"\t\t\tid = {t.id}{eol}" \
                        f"\t\t\tenabled = {t.enabled}{eol}" \
                        f"\t\t\ttriggerType = {t.trigger_type}{eol}" \
                        f"\t\t\tname = {t.name}{eol}" \
                        f"{props_c}{event_info}\t\t}}{eol}"

        # --- OBJECTIVES --- (Handles potential object links)
        objectives_list = []
        for o in self.objectives: # o is Objective object
            # Resolve potential object links before formatting
            waypoint_id = o.waypoint
            
            if isinstance(o.waypoint, Waypoint):
                waypoint_id = o.waypoint.id
            if not type(waypoint_id) == int:
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

            start_event_info_content = "\t\t\t\teventName = Start Event" + eol
            start_event_info_block = _format_block("EventInfo", start_event_info_content, 4)
            start_event_block = _format_block('startEvent', start_event_info_block, 3)

            fail_event_info_content = "\t\t\t\teventName = Failed Event" + eol
            fail_event_info_block = _format_block("EventInfo", fail_event_info_content, 4)
            fail_event_block = _format_block('failEvent', fail_event_info_block, 3)

            complete_event_info_content = "\t\t\t\teventName = Completed Event" + eol
            complete_event_info_block = _format_block("EventInfo", complete_event_info_content, 4)
            complete_event_block = _format_block('completeEvent', complete_event_info_block, 3)

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

        return { # Return final dictionary
            "UNITS": units_c, "PATHS": paths_c, "WAYPOINTS": wpts_c, "UNITGROUPS": ug_c,
            "TRIGGER_EVENTS": triggers_c, "OBJECTIVES": objs_c, "StaticObjects": statics_c,
            "BASES": bases_c, "Briefing": briefing_c, "ResourceManifest": resources_c,
            "Conditionals": conditionals_c
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
        vts += _format_block("WEATHER_PRESETS", "")
        vts += _format_block("UNITS", c["UNITS"])
        vts += _format_block("PATHS", c["PATHS"])
        vts += _format_block("WAYPOINTS", c["WAYPOINTS"])
        vts += _format_block("UNITGROUPS", c["UNITGROUPS"])
        vts += _format_block("TimedEventGroups", "") # TODO
        vts += _format_block("TRIGGER_EVENTS", c["TRIGGER_EVENTS"])
        vts += _format_block("OBJECTIVES", c["OBJECTIVES"])
        vts += _format_block("OBJECTIVES_OPFOR", "") # TODO
        vts += _format_block("StaticObjects", c["StaticObjects"])
        vts += _format_block("Conditionals", c["Conditionals"])
        vts += _format_block("ConditionalActions", "") # TODO
        vts += _format_block("RandomEvents", "") # TODO
        vts += _format_block("EventSequences", "") # TODO
        vts += _format_block("BASES", c["BASES"])
        vts += _format_block("GlobalValues", "") # TODO
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