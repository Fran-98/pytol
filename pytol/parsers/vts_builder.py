# mission_builder.py
import os
import shutil

class EventTarget:
    def __init__(self, target_type, target_id, event_name, params=None):
        self.target_type = target_type
        self.target_id = target_id
        self.event_name = event_name
        self.params = params or []

class ParamInfo:
    def __init__(self, name, param_type, value):
        self.name = name
        self.type = param_type
        self.value = value

def _format_value(val):
    if isinstance(val, bool): 
        return str(val)
    if isinstance(val, str): 
        return val
    if isinstance(val, (int, float)): 
        return str(val)
    return str(val)

def _format_vector(vec):
    return f"({vec[0]:.6f}, {vec[1]:.6f}, {vec[2]:.6f})"

def _format_point_list(points):
    return ";".join([_format_vector(p) for p in points])

def _format_id_list(ids):
    return ";".join(map(str, ids))

def _format_block(name, content_str, indent_level=1):
    indent = "\t" * indent_level
    if not content_str.strip():
        return f"{indent}{name}\n{indent}{{\n{indent}}}\n"
    return f"{indent}{name}\n{indent}{{\n{content_str}{indent}}}\n"

class Mission:
    def __init__(self, scenario_name, scenario_id, description, vehicle="F/A-26B", map_id: str = "", map_path: str = "", vtol_directory: str = ''):
        self.scenario_name = scenario_name
        self.scenario_id = scenario_id

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
        
        self.scenario_description = description
        self.vehicle = vehicle
        
        self.units, self.paths, self.waypoints, self.trigger_events, self.objectives, self.static_objects, self.bases, self.briefing_notes = [], [], [], [], [], [], [], []
        self.unit_groups = {"ALLIED": {}, "ENEMY": {}}
        self.timed_event_groups = []
        self.resource_manifest = {}
        self.conditionals_raw = "" # Para pegar código de Conditionals directamente

        self.allowed_equips = "fa26_droptank;fa26_gun;"
        self.rtb_wpt_id = ""
        self.refuel_wpt_id = ""

    def add_unit(self, unit_id, unit_name, global_position, rotation, unit_fields=None):
        uid = len(self.units)
        self.units.append({'unitID': unit_id, 'unitName': unit_name, 'globalPosition': global_position, 'rotation': rotation, 'unitInstanceID': uid, 'unit_fields': unit_fields or {}})
        print(f"Unidad '{unit_name}' añadida (ID de Instancia: {uid})")
        return uid

    def add_path(self, path_id, name, points, loop=False, path_mode="Smooth"):
        self.paths.append({'id': path_id, 'name': name, 'points': points, 'loop': loop, 'pathMode': path_mode})

    def add_waypoint(self, waypoint_id, name, global_point):
        self.waypoints.append({'id': waypoint_id, 'name': name, 'globalPoint': global_point})

    def add_unit_to_group(self, team, group_name, unit_instance_id):
        team_upper = team.upper()
        if team_upper not in self.unit_groups: 
            return
        if group_name not in self.unit_groups[team_upper]:
            self.unit_groups[team_upper][group_name] = []
        self.unit_groups[team_upper][group_name].append(unit_instance_id)

    def add_objective(self, objective_id, name, info, obj_type, fields, required=True, waypoint="", prereqs=None, auto_set_waypoint=True):
        self.objectives.append({'id': objective_id, 'name': name, 'info': info, 'type': obj_type, 'fields': fields, 'required': required, 'waypoint': waypoint, 'prereqs': prereqs or [], 'auto_set_waypoint': auto_set_waypoint})

    def add_static_object(self, prefab_id, global_pos, rotation):
        sid = len(self.static_objects)
        self.static_objects.append({'id': sid, 'prefabID': prefab_id, 'globalPos': global_pos, 'rotation': rotation})
        return sid
    
    def add_trigger_event(self, event_id, name, trigger_type, event_targets, enabled=True, **kwargs):
        trigger = {'id': event_id, 'name': name, 'type': trigger_type, 'targets': event_targets, 'enabled': enabled, 'props': kwargs}
        self.trigger_events.append(trigger)
    
    def add_base(self, base_id, team, name=""): self.bases.append({'id': base_id, 'team': team, 'name': name})
    def add_briefing_note(self, text): self.briefing_notes.append({'text': text})
    def add_resource(self, res_id, path): self.resource_manifest[res_id] = path
    def set_conditionals_raw(self, raw_string): self.conditionals_raw = raw_string
    
    def _generate_content_string(self):
        """Inner generation of the VTS content string."""
        # Units
        units_c = ""
        for u in self.units:
            fields_c = "".join([f"\t\t\t\t{k} = {_format_value(v)}\n" for k,v in u['unit_fields'].items()])
            units_c += f"\t\tUnitSpawner\n\t\t{{\n" \
                       f"\t\t\tunitName = {u['unitName']}\n" \
                       f"\t\t\tglobalPosition = {_format_vector(u['globalPosition'])}\n" \
                       f"\t\t\tunitInstanceID = {u['unitInstanceID']}\n" \
                       f"\t\t\tunitID = {u['unitID']}\n" \
                       f"\t\t\trotation = {_format_vector(u['rotation'])}\n" \
                       f"{_format_block('UnitFields', fields_c, 3)}\t\t}}\n"
        
        # Paths y Waypoints
        paths_c = "".join([f"\t\tPATH\n\t\t{{\n\t\t\tid = {p['id']}\n\t\t\tname = {p['name']}\n\t\t\tloop = {p['loop']}\n\t\t\tpoints = {_format_point_list(p['points'])}\n\t\t\tpathMode = {p['pathMode']}\n\t\t}}\n" for p in self.paths])
        wpts_c = "".join([f"\t\tWAYPOINT\n\t\t{{\n\t\t\tid = {w['id']}\n\t\t\tname = {w['name']}\n\t\t\tglobalPoint = {_format_vector(w['globalPoint'])}\n\t\t}}\n" for w in self.waypoints])
        
        # Unit Groups
        ug_c = ""
        for team, groups in self.unit_groups.items():
            team_c = "".join([f"\t\t\t{name} = 2;{_format_id_list(ids)};\n" for name, ids in groups.items()])
            ug_c += _format_block(team, team_c, 2)
        
        # Trigger Events
        triggers_c = ""
        for t in self.trigger_events:
            props_c = "".join([f"\t\t\t{k} = {v}\n" for k, v in t['props'].items()])
            targets_c = ""
            for target in t['targets']:
                params_c = "".join([f"\t\t\t\t\tParamInfo\n\t\t\t\t\t{{\n\t\t\t\t\t\ttype = {p.type}\n\t\t\t\t\t\tvalue = {p.value}\n\t\t\t\t\t\tname = {p.name}\n\t\t\t\t\t}}\n" for p in target.params])
                targets_c += f"\t\t\t\tEventTarget\n\t\t\t\t{{\n\t\t\t\t\ttargetType = {target.target_type}\n\t\t\t\t\ttargetID = {target.target_id}\n\t\t\t\t\teventName = {target.event_name}\n{params_c}\t\t\t\t}}\n"
            event_info = _format_block('EventInfo', f"\t\t\t\teventName = \n{targets_c}", 3)
            triggers_c += f"\t\tTriggerEvent\n\t\t{{\n\t\t\tid = {t['id']}\n\t\t\tenabled = {t['enabled']}\n\t\t\ttriggerType = {t['type']}\n{props_c}{event_info}\t\t}}\n"
        
        # Objectives
        objectives_list = []
        for o in self.objectives:
            fields_content = "".join([f"\t\t\t\t{k} = {_format_value(v)}\n" for k,v in o['fields'].items()])
            fields_block = _format_block('fields', fields_content, 3)
            
            obj_str = f"\t\tObjective\n\t\t{{\n" \
                        f"\t\t\tobjectiveName = {o['name']}\n" \
                        f"\t\t\tobjectiveInfo = {o['info']}\n" \
                        f"\t\t\tobjectiveID = {o['id']}\n" \
                        f"\t\t\trequired = {o['required']}\n" \
                        f"\t\t\twaypoint = {o['waypoint']}\n" \
                        f"\t\t\tautoSetWaypoint = {o['auto_set_waypoint']}\n" \
                        f"\t\t\tstartMode = {'PreReqs' if o['prereqs'] else 'Immediate'}\n" \
                        f"\t\t\tobjectiveType = {o['type']}\n" \
                        f"\t\t\tpreReqObjectives = {_format_id_list(o['prereqs'])};\n" \
                        f"{fields_block}" \
                        f"\t\t}}\n"
            objectives_list.append(obj_str)
        
        objs_c = "".join(objectives_list)
        
        # Static Objects
        statics_c = "".join([f"\t\tStaticObject\n\t\t{{\n\t\t\tprefabID = {s['prefabID']}\n\t\t\tid = {s['id']}\n\t\t\tglobalPos = {_format_vector(s['globalPos'])}\n\t\t\trotation = {_format_vector(s['rotation'])}\n\t\t}}\n" for s in self.static_objects])
        
        # Bases y Briefing
        bases_c = "".join([f"\t\tBaseInfo\n\t\t{{\n\t\t\tid = {b['id']}\n\t\t\toverrideBaseName = {b['name']}\n\t\t\tbaseTeam = {b['team']}\n\t\t}}\n" for b in self.bases])
        briefing_c = "".join([f"\t\tBRIEFING_NOTE\n\t\t{{\n\t\t\ttext = {n['text']}\n\t\t\timagePath = \n\t\t\taudioClipPath = \n\t\t}}\n" for n in self.briefing_notes])

        # Resource Manifest
        resources_c = "".join([f"\t\t{k} = {v}\n" for k, v in self.resource_manifest.items()])

        return {
            "UNITS": units_c, "PATHS": paths_c, "WAYPOINTS": wpts_c, "UNITGROUPS": ug_c,
            "TRIGGER_EVENTS": triggers_c, "OBJECTIVES": objs_c, "StaticObjects": statics_c,
            "BASES": bases_c, "Briefing": briefing_c, "ResourceManifest": resources_c
        }

    def _save_to_file(self, path):
        c = self._generate_content_string()
        vts = "CustomScenario\n{\n"
        vts += f"\tscenarioName = {self.scenario_name}\n"
        vts += f"\tscenarioID = {self.scenario_id}\n"
        vts += f"\tscenarioDescription = {self.scenario_description}\n"
        vts += f"\tmapID = {self.map_id}\n"
        vts += f"\tvehicle = {self.vehicle}\n"
        vts += f"\trtbWptID = {self.rtb_wpt_id}\n"
        vts += f"\trefuelWptID = {self.refuel_wpt_id}\n"
        
        vts += _format_block("UNITS", c["UNITS"])
        vts += _format_block("PATHS", c["PATHS"])
        vts += _format_block("WAYPOINTS", c["WAYPOINTS"])
        vts += _format_block("UNITGROUPS", c["UNITGROUPS"])
        vts += _format_block("TimedEventGroups", "") # Aún como placeholder
        vts += _format_block("TRIGGER_EVENTS", c["TRIGGER_EVENTS"])
        vts += _format_block("OBJECTIVES", c["OBJECTIVES"])
        vts += _format_block("StaticObjects", c["StaticObjects"])
        vts += _format_block("Conditionals", self.conditionals_raw)
        vts += _format_block("BASES", c["BASES"])
        vts += _format_block("Briefing", c["Briefing"])
        vts += _format_block("ResourceManifest", c["ResourceManifest"])
        vts += "}\n"
        
        with open(path, 'w') as f: 
            f.write(vts)
        print(f"\n✅ Mission saved '{path}'")

    def save_mission(self, base_path):
        """Saves the mission .vts file and associated map folder to the specified base path."""
        mission_dir = os.path.join(base_path, self.scenario_id)
        os.makedirs(mission_dir, exist_ok=True)
        shutil.copytree(self.map_path, os.path.join(mission_dir, self.map_id), dirs_exist_ok=True)
        vts_path = os.path.join(mission_dir, f"{self.scenario_id}.vts")
        self._save_to_file(vts_path)
        return mission_dir
    
    