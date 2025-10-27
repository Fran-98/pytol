from __future__ import annotations

from dataclasses import dataclass, field

from .spec import ProceduralMissionSpec
from .timing_model import TimingModel
from .strategy_selector import StrategySelector
from .altitude_policy import AltitudePolicy
from .control_map import ControlMap
from .threat_map import ThreatMap
from .objective_manager import ObjectiveManager
from .pacing_engine import PacingEngine
from .radio import RadioCommsHelper
from .environment_controller import EnvironmentController
from .randomizer import Randomizer
from .validation import MissionValidator, InvalidTargetError, InvalidRouteError
from ..misc.logger import create_logger

# Heavy imports kept local inside methods to avoid side effects at import time


@dataclass
class ProceduralMissionEngine:
    """
    Facade that wires together the procedural subsystems to produce a Mission.

    This is intentionally minimal in behavior at this stage: it validates the
    spec, creates a Mission, applies environment/timing defaults, and returns
    the mission object ready for further augmentation or saving.
    """
    verbose: bool = False
    logger: any = field(init=False, repr=False)

    def __post_init__(self):
        self.logger = create_logger(verbose=self.verbose, name="ProceduralEngine")

    def _find_valid_objective_position(self, target_position, mission_type, helper):
        """
        Find a valid terrain position for objective placement.
        
        This ensures objectives are placed on accessible terrain while keeping
        the core mission system flexible for manual placement.
        """
        import math
        import random
        from ..misc.math_utils import generate_random_angle
        
        x, y, z = target_position
        tc = helper.tc
        
        # Check if original position is valid
        if self._is_valid_objective_position(target_position, mission_type, tc):
            return target_position
        
        # Search for a valid position nearby
        search_radius = 2000.0
        max_attempts = 30
        
        from pytol.misc.math_utils import generate_random_position_in_circle
        for attempt in range(max_attempts):
            # Gradually expand search radius with attempts
            current_max_radius = search_radius * (1 + attempt / max_attempts)
            test_x, test_z = generate_random_position_in_circle(
                (x, z), current_max_radius, min_distance=100
            )
            
            # Stay within map bounds
            if not (0 <= test_x <= tc.total_map_size_meters and 0 <= test_z <= tc.total_map_size_meters):
                continue
            
            test_y = tc.get_terrain_height(test_x, test_z)
            test_position = (test_x, test_y, test_z)
            
            if self._is_valid_objective_position(test_position, mission_type, tc):
                self.logger.info(f"Found valid objective position at {test_position}")
                return test_position
        
        # Fallback: use original position with corrected height
        corrected_y = tc.get_terrain_height(x, z)
        fallback_position = (x, corrected_y, z)
        self.logger.warning(f"Using potentially invalid objective position {fallback_position}")
        return fallback_position

    def _is_valid_objective_position(self, position, mission_type, tc):
        """Check if a position is valid for objective placement."""
        x, y, z = position
        
        # Avoid water for ground missions
        if y <= tc.min_height + 1.0:  # Near sea level
            if mission_type in ("strike", "cas", "sead", "transport"):
                return False
        
        # Check terrain slope
        from ..misc.math_utils import calculate_slope_from_normal
        normal = tc.get_terrain_normal(x, z)
        slope_degrees = calculate_slope_from_normal(normal)
        
        if mission_type in ("strike", "cas", "sead", "transport"):
            # Ground missions need reasonable terrain
            if slope_degrees > 25.0:
                return False
        else:
            # Air missions can handle steeper terrain
            if slope_degrees > 45.0:
                return False
        
        return True

    def generate(self, spec: ProceduralMissionSpec):
        """
        Build and return a pytol Mission based on the provided spec.

        Returns:
            Mission: A mission object (from pytol.parsers.vts_builder) populated
            with basic metadata, environment, and a simple route (ingress/target/egress waypoints).
        """
        from pytol.parsers.vts_builder import Mission  # local import
        from pytol.classes.mission_objects import Waypoint

        if not (spec.map_path or spec.map_id):
            raise ValueError("spec.map_path or spec.map_id must be provided")

        # Randomize attributes when set to None/"random" and honor seed for reproducibility
        choices = Randomizer(seed=spec.seed).choose(
            mission_type=spec.mission_type,
            difficulty=spec.difficulty,
            time_of_day=spec.time_of_day,
            weather=spec.weather,
            duration_minutes=spec.duration_minutes,
        )

        mission_args = spec.resolve_map_args()
        mission = Mission(
            scenario_name=spec.scenario_name,
            scenario_id=spec.scenario_id,
            description=spec.description,
            verbose=self.verbose,
            **mission_args,
        )
        mission.vehicle = spec.vehicle

        # Terrain-aware helpers
        helper = mission.helper
        _control = ControlMap(helper)
        _threat = ThreatMap(helper)
        
        # Create validator for error checking
        validator = MissionValidator(helper)

        # Timing & pacing
        timing = TimingModel(duration_minutes=choices.duration_minutes)
        event_spacing = timing.event_spacing_seconds()
        _pacing = PacingEngine(event_spacing_seconds=event_spacing)

        # Validate route parameters before generation
        ingress_m, egress_m = timing.ingress_egress_distances()
        route_check = validator.validate_route(ingress_m, egress_m, helper.tc.total_map_size_meters)
        route_check.raise_if_invalid(InvalidRouteError)

        # Route selection (seeded for reproducibility)
        selector = StrategySelector(helper)
        import random as rnd
        rng = rnd.Random(spec.seed)
        # Build target bias (new API) from spec; fallback to legacy flags
        from .spec import TargetBias
        tb = spec.target_bias
        if tb is None:
            tb = TargetBias(
                cities=0.3 if spec.prefer_cities else 0.0,
                roads=0.2 if spec.prefer_roads else 0.0,
                open=0.3 if spec.prefer_open else 0.0,
                water=1.0 if (spec.avoid_water is None or spec.avoid_water) else 0.0,
            )
        legacy_prefs = {"avoid_water": (spec.avoid_water if spec.avoid_water is not None else True)}
        route = selector.select(choices.mission_type, (ingress_m, egress_m), rng, tb, legacy_prefs)
        
        # Validate target location
        target_check = validator.validate_target_location(route.target, choices.mission_type)
        target_check.raise_if_invalid(InvalidTargetError)
        
        # Altitude policy
        alt_policy = AltitudePolicy(mission_type=choices.mission_type)
        threat_level = 0.0  # Future: query ThreatMap at target
        target_agl = alt_policy.choose_agl(threat_level)

        # Generate tactical waypoints with terrain awareness
        from .tactical_waypoint_generator import TacticalWaypointGenerator
        waypoint_gen = TacticalWaypointGenerator(helper)
        
        # Collect basic route positions
        route_positions = route.ingress + [route.target] + route.egress
        
        # Enhance with tactical waypoint generation if we have enough points
        if len(route_positions) >= 2:
            start_pos = (route_positions[0][0], route_positions[0][1], route_positions[0][2])
            target_pos = (route.target[0], route.target[1], route.target[2])
            
            # Generate terrain-aware tactical route
            tactical_positions = waypoint_gen.generate_tactical_route(
                start_pos=start_pos,
                target_pos=target_pos,
                mission_type=choices.mission_type,
                waypoint_count=len(route_positions),
                threat_positions=None  # TODO: Integrate with threat system
            )
            waypoint_positions = tactical_positions
        else:
            # Fallback to original positions with AGL offset
            waypoint_positions = [(wx, wy + target_agl, wz) for wx, wy, wz in route_positions]
        
        # Validate waypoint spacing
        spacing_check = validator.validate_waypoint_spacing(waypoint_positions, min_spacing=500.0)
        if not spacing_check.valid:
            self.logger.warning(f"{spacing_check.message}")
        
        # Validate waypoint terrain clearance
        clearance_warnings = waypoint_gen.validate_waypoint_clearance(waypoint_positions, min_clearance=50.0)
        for warning, pos in clearance_warnings:
            self.logger.warning(f"Terrain clearance: {warning}")
        
        # Validate altitude envelope for mission type
        altitude_warnings = alt_policy.validate_altitude_envelope(waypoint_positions, helper.tc)
        for warning in altitude_warnings:
            self.logger.warning(f"Altitude envelope: {warning}")
        
        wpt_ids = []
        for i, (wx, wy, wz) in enumerate(waypoint_positions):
            wpt = Waypoint(
                name=f"WP{i+1}",
                global_point=[wx, wy, wz],  # Use calculated tactical altitude
            )
            wpt_id = mission.add_waypoint(wpt)
            wpt_ids.append(wpt_id)

        # Note: Objectives will be created after unit spawning so we can reference units
        target_wpt_id = wpt_ids[len(wpt_ids)//2]
        
        # Get the target waypoint position for terrain-aware objective placement
        target_waypoint_pos = waypoint_positions[len(waypoint_positions)//2]

        # --- Player Spawn (default: Cold at airbase hangar/apron) ---
        try:
            bases = getattr(helper.tc, 'bases', []) or []
            airbases = [b for b in bases if isinstance(b.get('prefab_type', ''), str) and 'airbase' in b['prefab_type'].lower()]

            spawn_mode = "Cold"
            on_carrier = False
            player_pos = None
            player_yaw = None

            if airbases:
                # Choose the airbase closest to the ingress waypoint
                ing = waypoint_positions[0]
                import math as _math
                ab = min(airbases, key=lambda b: _math.hypot(b['position'][0]-ing[0], b['position'][2]-ing[2]))
                # Try to use known spawn points for this base type
                try:
                    from pytol.resources.base_spawn_points import get_spawn_points_for, compute_world_from_base
                    spawns = get_spawn_points_for(ab.get('prefab_type', ''))
                except Exception:
                    spawns = []

                if spawns:
                    # Pick the first defined spawn by default
                    sp = spawns[0]
                    (wx, wy, wz), wyaw = compute_world_from_base(ab, tuple(sp.get('offset', (0.0, 0.0))), sp.get('yaw_offset', 0.0))
                    player_pos = [wx, wy, wz]
                    player_yaw = wyaw
                else:
                    # Fallback: use base flatten zone centroid as anchor
                    fz = ab.get('flatten_zone', [])
                    if fz:
                        cx = sum(p[0] for p in fz) / len(fz)
                        cz = sum(p[1] for p in fz) / len(fz)
                    else:
                        cx, cz = ab['position'][0], ab['position'][2]
                    cy = helper.tc.get_terrain_height(cx, cz)
                    player_pos = [cx, cy, cz]

                    # Orient toward target from base center
                    from pytol.misc.math_utils import calculate_bearing
                    tx, _, tz = route.target
                    player_yaw = calculate_bearing((cx, cy, cz), (tx, cy, tz))

            else:
                # Fallback: flight-ready start at ingress AGL if no airbase found
                ingress_pos = waypoint_positions[0]
                target_pos = route.target
                from pytol.misc.math_utils import calculate_bearing
                player_yaw = calculate_bearing(ingress_pos, target_pos)
                player_pos = [ingress_pos[0], ingress_pos[1], ingress_pos[2]]
                spawn_mode = "FlightReady"

            from pytol.classes.units import create_unit
            player_unit = create_unit(
                id_name="PlayerSpawn",
                unit_name="Player",
                team="Allied",
                global_position=player_pos,
                rotation=[0.0, player_yaw, 0.0],
                start_mode=spawn_mode,
                initial_speed=(180.0 if spawn_mode == "FlightReady" else 0.0),
            )

            if spawn_mode == "FlightReady":
                # Place airborne at a reasonable AGL
                mission.add_unit(
                    player_unit,
                    placement="relative_airborne",
                    altitude_agl=target_agl,
                    align_to_surface=False,
                )
            else:
                # Place cold on base apron/hangar area; prefer smart placement off (flat zone is level)
                mission.add_unit(
                    player_unit,
                    placement="ground",
                    use_smart_placement=False,
                    align_to_surface=False,
                    on_carrier=on_carrier,
                )
        except Exception as e:
            self.logger.warning(f"Could not create PlayerSpawn: {e}")
        
        # Altitude policy
        alt_policy = AltitudePolicy(mission_type=choices.mission_type)
        from .unit_templates import UnitLibrary, SpawnPlan
        from .intelligent_placement import IntelligentPlacer
        from pytol.classes.units import create_unit
        import math
        
        enemy_templates = UnitLibrary.pick_enemy_set(choices.mission_type, choices.difficulty, rng)
        placer = IntelligentPlacer(helper)
        spawned_units = []
        spawned_count = 0
        max_attempts_per_unit = 10
        
        if enemy_templates:
            tx, ty, tz = route.target
            
            # Use intelligent placement for certain mission types
            if choices.mission_type in ("sead", "strike"):
                # For SEAD/strike, use defensive placement zones
                zones = placer.find_placement_zones(
                    center=route.target,
                    radius=600.0,
                    num_zones=max(2, len(enemy_templates) // 3),
                    rng=rng,
                    prefer_urban=(choices.mission_type == "strike"),
                    prefer_defensive=(choices.mission_type == "sead")
                )
                
                if zones:
                    # Cluster units into zones
                    unit_types = [t.unit_type for t in enemy_templates]
                    placements = placer.cluster_units(unit_types, zones, rng)
                    
                    for i, (unit_type, (spawn_x, spawn_y, spawn_z)) in enumerate(placements):
                        template = next(t for t in enemy_templates if t.unit_type == unit_type)
                        
                        unit = create_unit(
                            id_name=template.unit_type,
                            unit_name=f"{template.name} {i+1}",
                            team=template.team,
                            global_position=[spawn_x, spawn_y, spawn_z],
                            rotation=[0, rng.uniform(0, 360), 0],
                            behavior=template.behavior,
                            engage_enemies=template.engage_enemies,
                        )
                        mission.add_unit(unit, placement="ground")
                        spawned_units.append(unit)
                        spawned_count += 1
                else:
                    # Fallback to random placement
                    self.logger.warning("No suitable placement zones found, using random placement")
            
            # For other mission types or if intelligent placement failed, use validated random placement
            if not spawned_units:
                spawn_plan = SpawnPlan(templates=enemy_templates, spawn_center=route.target, spread_radius=400.0)
                
                for i, template in enumerate(spawn_plan.templates):
                    # Try multiple times to find valid spawn location
                    spawn_valid = False
                    for attempt in range(max_attempts_per_unit):
                        # Random offset within spread_radius
                        angle = rng.uniform(0, 2 * math.pi)
                        dist = rng.uniform(50, spawn_plan.spread_radius)
                        spawn_x = tx + dist * math.cos(angle)
                        spawn_z = tz + dist * math.sin(angle)
                        
                        # Validate spawn location
                        spawn_check = validator.validate_spawn_location(spawn_x, spawn_z, template.unit_type, template.team)
                        if spawn_check.valid:
                            spawn_y = helper.tc.get_terrain_height(spawn_x, spawn_z)
                            spawn_valid = True
                            break
                        elif attempt == 0:
                            self.logger.warning(f"{spawn_check.message} (retrying...)")
                    
                    if not spawn_valid:
                        self.logger.warning(f"Could not find valid spawn location for {template.unit_type} after {max_attempts_per_unit} attempts, skipping")
                        continue
                    
                    # Check if this is an air unit (air units don't support behavior parameter)
                    is_air_unit = any(air_type in template.unit_type for air_type in ["ASF", "AEW", "F-45A", "F/A-26"])
                    
                    if is_air_unit:
                        unit = create_unit(
                            id_name=template.unit_type,
                            unit_name=f"{template.name} {i+1}",
                            team=template.team,
                            global_position=[spawn_x, spawn_y, spawn_z],
                            rotation=[0, rng.uniform(0, 360), 0],
                            engage_enemies=template.engage_enemies,
                        )
                    else:
                        unit = create_unit(
                            id_name=template.unit_type,
                            unit_name=f"{template.name} {i+1}",
                            team=template.team,
                            global_position=[spawn_x, spawn_y, spawn_z],
                            rotation=[0, rng.uniform(0, 360), 0],
                            behavior=template.behavior,
                            engage_enemies=template.engage_enemies,
                        )
                    mission.add_unit(unit, placement="ground")
                    spawned_units.append(unit)
                    spawned_count += 1

        # QRF: Prepare a small quick reaction force that spawns when player approaches target
        qrf_templates = enemy_templates[:2] if enemy_templates else []
        qrf_units = []
        if qrf_templates:
            for i, template in enumerate(qrf_templates):
                # Try to find valid QRF spawn location
                qrf_spawn_valid = False
                for attempt in range(max_attempts_per_unit):
                    angle = rng.uniform(0, 2 * math.pi)
                    dist = rng.uniform(300, 900)  # QRF slightly farther out
                    spawn_x = tx + dist * math.cos(angle)
                    spawn_z = tz + dist * math.sin(angle)
                    
                    spawn_check = validator.validate_spawn_location(spawn_x, spawn_z, template.unit_type, template.team)
                    if spawn_check.valid:
                        spawn_y = helper.tc.get_terrain_height(spawn_x, spawn_z)
                        qrf_spawn_valid = True
                        break
                
                if not qrf_spawn_valid:
                    self.logger.warning(f"Could not find valid QRF spawn for {template.unit_type}, skipping")
                    continue
                
                # Check if this is an air unit (air units don't support behavior parameter)
                is_air_unit = any(air_type in template.unit_type for air_type in ["ASF", "AEW", "F-45A", "F/A-26"])
                
                if is_air_unit:
                    unit = create_unit(
                        id_name=template.unit_type,
                        unit_name=f"QRF {template.name} {i+1}",
                        team=template.team,
                        global_position=[spawn_x, spawn_y, spawn_z],
                        rotation=[0, rng.uniform(0, 360), 0],
                        engage_enemies=template.engage_enemies,
                        spawn_on_start=False,
                    )
                else:
                    unit = create_unit(
                        id_name=template.unit_type,
                        unit_name=f"QRF {template.name} {i+1}",
                        team=template.team,
                        global_position=[spawn_x, spawn_y, spawn_z],
                        rotation=[0, rng.uniform(0, 360), 0],
                        behavior=template.behavior,
                        engage_enemies=template.engage_enemies,
                        spawn_on_start=False,
                    )
                mission.add_unit(unit, placement="ground")
                qrf_units.append(unit)

            # Proximity trigger at target waypoint to spawn QRF units
            from pytol.classes.mission_objects import Trigger
            targets = []
            for qu in qrf_units:
                if getattr(qu, "actions", None):
                    targets.append(qu.actions.spawn_unit())
            if targets:
                target_wpt_id = wpt_ids[len(wpt_ids)//2]
                trig = Trigger(
                    id=1,
                    name="QRF Spawn",
                    trigger_type="Proximity",
                    waypoint=target_wpt_id,
                    radius=2500.0,
                    spherical_radius=True,
                    event_targets=targets,
                )
                mission.add_trigger_event(trig)
        
        # Objectives: Create after unit spawning so we can reference spawned units
        plan = ObjectiveManager().plan(choices.mission_type, choices.difficulty, spawned_units)
        if plan.objectives:
            from pytol.classes.objectives import create_objective
            
            for obj_idx, spec_obj in enumerate(plan.objectives):
                if spec_obj.id_name == "Fly_To":
                    # Navigation objective at target waypoint - ensure it's on valid terrain
                    objective_position = self._find_valid_objective_position(
                        target_waypoint_pos, choices.mission_type, helper
                    )
                    
                    # Update the target waypoint position if we found a better one
                    if objective_position != target_waypoint_pos:
                        self.logger.info("Adjusted objective position for terrain validity")
                        # Update the waypoint to the terrain-corrected position
                        target_waypoint = mission.waypoints[target_wpt_id - 1]  # waypoint IDs are 1-based
                        target_waypoint.global_point = [
                            objective_position[0], 
                            objective_position[1] + target_agl, 
                            objective_position[2]
                        ]
                    
                    obj = create_objective(
                        id_name=spec_obj.id_name,
                        objective_id=obj_idx,
                        name=spec_obj.name,
                        info=spec_obj.info,
                        required=spec_obj.required,
                        waypoint=target_wpt_id,
                        auto_set_waypoint=False,
                        trigger_radius=spec_obj.trigger_radius,
                        spherical_radius=spec_obj.spherical_radius,
                    )
                    mission.add_objective(obj)
                
                elif spec_obj.id_name == "Destroy" and spec_obj.target_units:
                    # Destroy objective referencing spawned units
                    obj = create_objective(
                        id_name=spec_obj.id_name,
                        objective_id=obj_idx,
                        name=spec_obj.name,
                        info=spec_obj.info,
                        required=spec_obj.required,
                        target_units=spec_obj.target_units,
                        min_required_units=spec_obj.min_required or len(spec_obj.target_units),
                    )
                    mission.add_objective(obj)
        
        # Radio (placeholder)
        _radio = RadioCommsHelper().opening_calls(choices.mission_type)

        # Environment choices (placeholder—no actual changes applied yet)
        EnvironmentController(time_of_day=choices.time_of_day, weather=choices.weather).apply_to(mission)

        # Multiplayer defaults: off by default; campaigns can override on add
        mission.multiplayer = False

        # Minimal briefing note
        try:
            from pytol.classes.mission_objects import BriefingNote
            intro = f"Procedural {choices.mission_type} mission.\n\n"
            intro += f"Difficulty: {choices.difficulty}\n"
            tod = choices.time_of_day or "default"
            intro += f"Time of day: {tod}\n"
            if choices.weather:
                intro += f"Weather: {choices.weather}\n"
            intro += f"Route: {len(waypoint_positions)} waypoints generated.\n"
            intro += f"Target altitude: {target_agl:.0f}m AGL\n"
            intro += f"Enemy units: {spawned_count}"
            mission.briefing_notes.append(BriefingNote(note_type="Text", content=intro))
        except Exception:
            pass

        self.logger.info(f"Generated mission '{spec.scenario_id}' for map='{mission.map_id}'")
        self.logger.info(f"  Type={choices.mission_type}, Diff={choices.difficulty}, ToD={choices.time_of_day or 'default'}")
        self.logger.info(f"  Route: {len(waypoint_positions)} waypoints at ~{target_agl:.0f}m AGL")
        self.logger.info(f"  Units spawned: {len(mission.units)} ({spawned_count} enemy, {len(qrf_units)} QRF)")
        
        return mission
