# mission_builder.py
import os
import shutil

class EventTarget:
    """Represents a target for a Trigger Event."""
    def __init__(self, target_type, target_id, event_name, params=None):
        self.target_type = target_type
        self.target_id = target_id
        self.event_name = event_name
        self.params = params or []

class ParamInfo:
    """Represents a parameter for an EventTarget."""
    def __init__(self, name, param_type, value):
        self.name = name
        self.type = param_type
        self.value = value

def _format_value(val):
    """Helper function to format values for the VTS file."""
    if val is None:
        return "null"
    if isinstance(val, bool):
        # Format as True/False
        return str(val)
    if val == "null":
        # Handle the specific string "null" without quotes
        return "null"
    if isinstance(val, str):
        # Default string formatting (no quotes, as VTS doesn't use them)
        return val
    if isinstance(val, (int, float)):
        return str(val)
    return str(val)

def _format_vector(vec):
    """Format vector with full precision and uppercase E notation."""
    formatted = []
    for v in vec:
        # Convert to string with full precision
        s = f"{v}"
        # Replace lowercase e with uppercase E for scientific notation
        s = s.replace('e', 'E')
        formatted.append(s)
    return f"({formatted[0]}, {formatted[1]}, {formatted[2]})"

def _format_point_list(points):
    """Formats a list of vector points into a VTS-compatible string."""
    return ";".join([_format_vector(p) for p in points])

def _format_id_list(ids):
    """Formats a list of IDs into a VTS-compatible string."""
    return ";".join(map(str, ids))

def _format_block(name, content_str, indent_level=1):
    """Helper function to format a VTS block with correct indentation."""
    indent = "\t" * indent_level
    eol = "\n"  # Use LF, not CRLF!
    if not content_str.strip():
        return f"{indent}{name}{eol}{indent}{{{eol}{indent}}}{eol}"
    return f"{indent}{name}{eol}{indent}{{{eol}{content_str}{indent}}}{eol}"

class Mission:
    """
    Main class for building a VTOL VR mission.
    This class holds all scenario data and provides methods to add
    units, waypoints, objectives, etc.
    """
    def __init__(self, scenario_name, scenario_id, description, vehicle="AV-42C", map_id: str = "", map_path: str = "", vtol_directory: str = ''):
        self.scenario_name = scenario_name
        self.scenario_id = scenario_id
        self.scenario_description = description if description else ""
        self.vehicle = vehicle

        # --- Map Handling ---
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
            raise ValueError("Either map_id or map_path must be provided, and VTOL_VR_DIR must be set if using only map_id.")
        
        # --- Default Game Properties ---
        # These properties are required for the game to load the mission
        self.game_version = "1.12.6f1" # Target game version
        self.campaign_id = ""
        self.campaign_order_idx = -1
        self.multiplayer = False
        # Default 'allowedEquips' for AV-42C
        self.allowed_equips = "gau-8;m230;h70-x7;h70-4x4;h70-x19;mk82x1;mk82x2;mk82x3;mk82HDx1;mk82HDx2;mk82HDx3;agm89x1;gbu38x1;gbu38x2;gbu38x3;gbu39x3;gbu39x4u;cbu97x1;hellfirex4;maverickx1;maverickx3;cagm-6;sidewinderx1;sidewinderx2;sidewinderx3;iris-t-x1;iris-t-x2;iris-t-x3;sidearmx1;sidearmx2;sidearmx3;marmx1;av42_gbu12x1;av42_gbu12x2;av42_gbu12x3;42c_aim9ex2;42c_aim9ex1;"
        self.force_equips = False
        self.norm_forced_fuel = 1
        self.equips_configurable = True
        self.base_budget = 100000
        self.is_training = False
        self.infinite_ammo = False
        self.inf_ammo_reload_delay = 5
        self.fuel_drain_mult = 1
        self.env_name = "day"
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
        # --- End Default Properties ---

        # --- Mission-specific Properties ---
        self.rtb_wpt_id = ""
        self.refuel_wpt_id = ""
        
        # --- Mission Data Lists ---
        self.units, self.paths, self.waypoints, self.trigger_events, self.objectives, self.static_objects, self.briefing_notes = [], [], [], [], [], [], []
        
        self.unit_groups = {} 
        
        # Add default bases required by the game
        self.bases = [
            {'id': 0, 'team': 'Allied', 'name': ''},
            {'id': 1, 'team': 'Allied', 'name': ''}
        ]
        
        self.timed_event_groups = []
        self.resource_manifest = {}
        self.conditionals_raw = "" # Used to inject raw VTS code for Conditionals

    def add_unit(self, unit_id, unit_name, global_position, rotation, 
                 start_mode="Cold", initial_speed=0, unit_group="null", 
                 receive_friendly_damage=True, editor_placement_mode="Ground", 
                 on_carrier=False, mp_select_enabled=True, **other_unit_fields):
        """
        Adds a new unit (like the player or AI) to the mission.

        Args:
            unit_id (str): The prefab ID of the unit (e.g., "PlayerSpawn", "a-wing").
            unit_name (str): The display name of the unit in-game.
            global_position (tuple): The (x, y, z) coordinates. Must be high precision.
            rotation (tuple): The (x, y, z) rotation. Must be high precision.
            start_mode (str, optional): "Cold", "Hot", "Airborne", etc.
            initial_speed (int, optional): Starting speed, usually for airborne.
            unit_group (str, optional): The unit group (e.g., "Allied:Alpha"). Defaults to "null".
            **other_unit_fields: Any other fields to add to the UnitFields block.

        Returns:
            int: The unitInstanceID of the newly created unit.
        """
        uid = len(self.units)
        
        unit_fields = {
            'startMode': start_mode,
            'initialSpeed': initial_speed,
            'unitGroup': unit_group,
            'receiveFriendlyDamage': receive_friendly_damage,
        }
        # Add any other custom fields
        unit_fields.update(other_unit_fields)

        unit_data = {
            'unitID': unit_id,
            'unitName': unit_name,
            'globalPosition': global_position,
            'unitInstanceID': uid,
            'rotation': rotation,
            'unit_fields': unit_fields,
            
            # Add required game-default fields for the UnitSpawner
            'lastValidPlacement': global_position, # Mirrors globalPosition
            'editorPlacementMode': editor_placement_mode,
            'onCarrier': on_carrier,
            'mpSelectEnabled': mp_select_enabled
        }
        
        self.units.append(unit_data)
        print(f"Unidad '{unit_name}' añadida (ID de Instancia: {uid})")
        return uid

    def add_path(self, path_id, name, points, loop=False, path_mode="Smooth"):
        """Adds a PATH block for AI units to follow."""
        self.paths.append({'id': path_id, 'name': name, 'points': points, 'loop': loop, 'pathMode': path_mode})

    def add_waypoint(self, waypoint_id, name, global_point):
        """Adds a WAYPOINT block."""
        self.waypoints.append({'id': waypoint_id, 'name': name, 'globalPoint': global_point})

    def add_unit_to_group(self, team, group_name, unit_instance_id):
        """Assigns a unit (by its instance ID) to a unit group."""
        team_upper = team.upper()
        if team_upper not in self.unit_groups:
            self.unit_groups[team_upper] = {}
        
        if group_name not in self.unit_groups[team_upper]:
            self.unit_groups[team_upper][group_name] = []
        
        self.unit_groups[team_upper][group_name].append(unit_instance_id)

    def add_objective(self, objective_id, name, info, obj_type, fields, required=True, waypoint="", prereqs=None, auto_set_waypoint=True):
        """Adds an OBJECTIVE block."""
        self.objectives.append({'id': objective_id, 'name': name, 'info': info, 'type': obj_type, 'fields': fields, 'required': required, 'waypoint': waypoint, 'prereqs': prereqs or [], 'auto_set_waypoint': auto_set_waypoint})

    def add_static_object(self, prefab_id, global_pos, rotation):
        """Adds a StaticObject block (e.g., buildings, scenery)."""
        sid = len(self.static_objects)
        self.static_objects.append({'id': sid, 'prefabID': prefab_id, 'globalPos': global_pos, 'rotation': rotation})
        return sid
    
    def add_trigger_event(self, event_id, name, trigger_type, event_targets, enabled=True, **kwargs):
        """Adds a TRIGGER_EVENTS block."""
        trigger = {'id': event_id, 'name': name, 'type': trigger_type, 'targets': event_targets, 'enabled': enabled, 'props': kwargs}
        self.trigger_events.append(trigger)
    
    def add_base(self, base_id, team, name=""): 
        """Adds a BaseInfo block. Note: Default bases 0 and 1 are already added."""
        self.bases.append({'id': base_id, 'team': team, 'name': name})
        
    def add_briefing_note(self, text):
        """Adds a briefing note to the Briefing block."""
        self.briefing_notes.append({'text': text})

    def add_resource(self, res_id, path):
        """Adds a resource to the ResourceManifest."""
        self.resource_manifest[res_id] = path

    def set_conditionals_raw(self, raw_string):
        """Sets the raw string content for the Conditionals block."""
        self.conditionals_raw = raw_string
    
    def _generate_content_string(self):
        """
        Internal function to generate the content for all VTS blocks.
        
        Returns:
            dict: A dictionary mapping block names (e.g., "UNITS") to their
                formatted string content.
        """
        eol = "\n"  # Use CRLF throughout
        
        # Units
        units_c = ""
        for u in self.units:
            fields_c = "".join([f"\t\t\t\t{k} = {_format_value(v)}{eol}" for k,v in u['unit_fields'].items()])
            units_c += f"\t\tUnitSpawner{eol}\t\t{{{eol}" \
                    f"\t\t\tunitName = {u['unitName']}{eol}" \
                    f"\t\t\tglobalPosition = {_format_vector(u['globalPosition'])}{eol}" \
                    f"\t\t\tunitInstanceID = {u['unitInstanceID']}{eol}" \
                    f"\t\t\tunitID = {u['unitID']}{eol}" \
                    f"\t\t\trotation = {_format_vector(u['rotation'])}{eol}" \
                    f"\t\t\tlastValidPlacement = {_format_vector(u['lastValidPlacement'])}{eol}" \
                    f"\t\t\teditorPlacementMode = {u['editorPlacementMode']}{eol}" \
                    f"\t\t\tonCarrier = {u['onCarrier']}{eol}" \
                    f"\t\t\tmpSelectEnabled = {u['mpSelectEnabled']}{eol}" \
                    f"{_format_block('UnitFields', fields_c, 3)}\t\t}}{eol}"
        
        # Paths
        paths_c = ""
        for p in self.paths:
            paths_c += f"\t\tPATH{eol}\t\t{{{eol}" \
                    f"\t\t\tid = {p['id']}{eol}" \
                    f"\t\t\tname = {p['name']}{eol}" \
                    f"\t\t\tloop = {p['loop']}{eol}" \
                    f"\t\t\tpoints = {_format_point_list(p['points'])}{eol}" \
                    f"\t\t\tpathMode = {p['pathMode']}{eol}" \
                    f"\t\t}}{eol}"
        
        # Waypoints
        wpts_c = ""
        for w in self.waypoints:
            wpts_c += f"\t\tWAYPOINT{eol}\t\t{{{eol}" \
                    f"\t\t\tid = {w['id']}{eol}" \
                    f"\t\t\tname = {w['name']}{eol}" \
                    f"\t\t\tglobalPoint = {_format_vector(w['globalPoint'])}{eol}" \
                    f"\t\t}}{eol}"
        
        # Unit Groups
        ug_c = ""
        for team, groups in self.unit_groups.items():
            team_c = "".join([f"\t\t\t{name} = 2;{_format_id_list(ids)};{eol}" for name, ids in groups.items()])
            ug_c += _format_block(team, team_c, 2)
        
        # Trigger Events
        triggers_c = ""
        for t in self.trigger_events:
            props_c = "".join([f"\t\t\t{k} = {v}{eol}" for k, v in t['props'].items()])
            targets_c = ""
            for target in t['targets']:
                params_c = ""
                for p in target.params:
                    params_c += f"\t\t\t\t\tParamInfo{eol}\t\t\t\t\t{{{eol}" \
                            f"\t\t\t\t\t\ttype = {p.type}{eol}" \
                            f"\t\t\t\t\t\tvalue = {p.value}{eol}" \
                            f"\t\t\t\t\t\tname = {p.name}{eol}" \
                            f"\t\t\t\t\t}}{eol}"
                targets_c += f"\t\t\t\tEventTarget{eol}\t\t\t\t{{{eol}" \
                            f"\t\t\t\t\ttargetType = {target.target_type}{eol}" \
                            f"\t\t\t\t\ttargetID = {target.target_id}{eol}" \
                            f"\t\t\t\t\teventName = {target.event_name}{eol}" \
                            f"{params_c}\t\t\t\t}}{eol}"
            event_info = _format_block('EventInfo', f"\t\t\t\teventName = {eol}{targets_c}", 3)
            triggers_c += f"\t\tTriggerEvent{eol}\t\t{{{eol}" \
                        f"\t\t\tid = {t['id']}{eol}" \
                        f"\t\t\tenabled = {t['enabled']}{eol}" \
                        f"\t\t\ttriggerType = {t['type']}{eol}" \
                        f"{props_c}{event_info}\t\t}}{eol}"
        
        # Objectives
        objectives_list = []
        for o in self.objectives:
            fields_content = "".join([f"\t\t\t\t{k} = {_format_value(v)}{eol}" for k,v in o['fields'].items()])
            fields_block = _format_block('fields', fields_content, 3)
            
            obj_str = f"\t\tObjective{eol}\t\t{{{eol}" \
                    f"\t\t\tobjectiveName = {o['name']}{eol}" \
                    f"\t\t\tobjectiveInfo = {o['info']}{eol}" \
                    f"\t\t\tobjectiveID = {o['id']}{eol}" \
                    f"\t\t\trequired = {o['required']}{eol}" \
                    f"\t\t\twaypoint = {o['waypoint']}{eol}" \
                    f"\t\t\tautoSetWaypoint = {o['auto_set_waypoint']}{eol}" \
                    f"\t\t\tstartMode = {'PreReqs' if o['prereqs'] else 'Immediate'}{eol}" \
                    f"\t\t\tobjectiveType = {o['type']}{eol}" \
                    f"\t\t\tpreReqObjectives = {_format_id_list(o['prereqs'])};{eol}" \
                    f"{fields_block}" \
                    f"\t\t}}{eol}"
            objectives_list.append(obj_str)
        
        objs_c = "".join(objectives_list)
        
        # Static Objects
        statics_c = ""
        for s in self.static_objects:
            statics_c += f"\t\tStaticObject{eol}\t\t{{{eol}" \
                        f"\t\t\tprefabID = {s['prefabID']}{eol}" \
                        f"\t\t\tid = {s['id']}{eol}" \
                        f"\t\t\tglobalPos = {_format_vector(s['globalPos'])}{eol}" \
                        f"\t\t\trotation = {_format_vector(s['rotation'])}{eol}" \
                        f"\t\t}}{eol}"
        
        # Bases
        bases_c = ""
        for b in self.bases:
            # Add the required empty CUSTOM_DATA block
            custom_data_block = _format_block('CUSTOM_DATA', '', 3)
            bases_c += f"\t\tBaseInfo{eol}\t\t{{{eol}" \
                    f"\t\t\tid = {b['id']}{eol}" \
                    f"\t\t\toverrideBaseName = {b['name']}{eol}" \
                    f"\t\t\tbaseTeam = {b['team']}{eol}" \
                    f"{custom_data_block}\t\t}}{eol}"

        # Briefing
        briefing_c = ""
        for n in self.briefing_notes:
            briefing_c += f"\t\tBRIEFING_NOTE{eol}\t\t{{{eol}" \
                        f"\t\t\ttext = {n['text']}{eol}" \
                        f"\t\t\timagePath = {eol}" \
                        f"\t\t\taudioClipPath = {eol}" \
                        f"\t\t}}{eol}"

        # Resource Manifest
        resources_c = "".join([f"\t\t{k} = {v}{eol}" for k, v in self.resource_manifest.items()])

        return {
            "UNITS": units_c, "PATHS": paths_c, "WAYPOINTS": wpts_c, "UNITGROUPS": ug_c,
            "TRIGGER_EVENTS": triggers_c, "OBJECTIVES": objs_c, "StaticObjects": statics_c,
            "BASES": bases_c, "Briefing": briefing_c, "ResourceManifest": resources_c
        }

    def _save_to_file(self, path):
        c = self._generate_content_string()
        eol = "\n"
        vts = f"CustomScenario{eol}{{{eol}"

        # Root properties
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

        # Block order (same as editor)
        vts += _format_block("WEATHER_PRESETS", "")
        vts += _format_block("UNITS", c["UNITS"])
        vts += _format_block("PATHS", c["PATHS"])
        vts += _format_block("WAYPOINTS", c["WAYPOINTS"])
        vts += _format_block("UNITGROUPS", c["UNITGROUPS"])
        vts += _format_block("TimedEventGroups", "")
        vts += _format_block("TRIGGER_EVENTS", c["TRIGGER_EVENTS"])
        vts += _format_block("OBJECTIVES", c["OBJECTIVES"])
        vts += _format_block("OBJECTIVES_OPFOR", "")
        vts += _format_block("StaticObjects", c["StaticObjects"])
        vts += _format_block("Conditionals", self.conditionals_raw)
        vts += _format_block("ConditionalActions", "")
        vts += _format_block("RandomEvents", "")
        vts += _format_block("EventSequences", "")
        vts += _format_block("BASES", c["BASES"])
        vts += _format_block("GlobalValues", "")
        vts += _format_block("Briefing", c["Briefing"])

        if c["ResourceManifest"]:
            vts += _format_block("ResourceManifest", c["ResourceManifest"])

        vts += f"}}{eol}"

        # Write with CRLF enforced and no BOM
        with open(path, "wb") as f:
            f.write(vts.encode("utf-8"))

        print(f"✅ Mission saved '{path}' (UTF-8 no BOM, CRLF line endings)")

    def save_mission(self, base_path):
        """
        Saves the mission .vts file and copies the associated map folder
        into the specified base path.

        Args:
            base_path (str): The root directory to save the mission folder to
                             (e.g., ".../VTOL VR/CustomScenarios").

        Returns:
            str: The path to the newly created mission directory.
        """
        mission_dir = os.path.join(base_path, self.scenario_id)
        os.makedirs(mission_dir, exist_ok=True)
        
        # Copy the map data into the mission folder
        shutil.copytree(self.map_path, os.path.join(mission_dir, self.map_id), dirs_exist_ok=True)
        
        # Save the .vts file
        vts_path = os.path.join(mission_dir, f"{self.scenario_id}.vts")
        self._save_to_file(vts_path)
        
        return mission_dir