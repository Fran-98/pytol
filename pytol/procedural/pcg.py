"""Procedural Content Generation (PCG) skeleton.

This module contains a minimal PCG class that can "realize" a MissionPlan by
placing a few units into the WorldState. The real PCG layer will include
constraint-based placement, pathing generation, and script event creation.
"""
from __future__ import annotations

import logging
import math
import random
from typing import Optional, TYPE_CHECKING, Tuple, Dict, List

import dataclasses

from .world_state import WorldState
from .mission_director import MissionPlan, PlanObjective
from .unit_templates import UnitLibrary, UNIT_TEAM_DATABASE
from pytol.classes.units import create_unit, UNIT_CLASS_TO_ACTION_CLASS
from .validation import validate_generated_mission

if TYPE_CHECKING:
    from pytol.parsers.vts_builder import Mission
    from pytol.terrain.mission_terrain_helper import MissionTerrainHelper

try:
    from pytol.procedural.intelligent_placement import IntelligentPlacer
    from pytol.procedural.tactical_waypoint_generator import TacticalWaypointGenerator
    from pytol.terrain.mission_terrain_helper import MissionTerrainHelper
except Exception:
    IntelligentPlacer = None  # type: ignore
    TacticalWaypointGenerator = None  # type: ignore
    MissionTerrainHelper = None  # type: ignore


class PCG:
    """Simple PCG layer for MVP usage.

    Methods:
        realize_plan(plan, wsm)
    """

    def __init__(
        self,
        seed: int | None = None,
        mission: Optional["Mission"] = None,
        terrain_helper: Optional["MissionTerrainHelper"] = None,
        diagnostics_outpath: str | None = None,
    ) -> None:
        self.seed = seed
        self.rng = random.Random(seed)
        self.mission = mission

        if mission is not None:
            # Prefer the helper from the Mission instance to avoid drift
            terrain_helper = getattr(mission, "helper", None)

        self.terrain_helper = terrain_helper
        if self.terrain_helper is None:
            raise RuntimeError(
                "PCG requires a Mission instance (preferred) or a MissionTerrainHelper. "
                "Instantiate pytol.parsers.vts_builder.Mission for the target map, "
                "then pass mission=... when constructing PCG."
            )

        # Build unit template registry once per PCG instance
        try:
            UnitLibrary.build_from_registry()
        except Exception:
            # If registry introspection fails for some reason, continue with
            # empty lists and let pickers fallback to naive strings.
            pass
        # logger and diagnostics collector for materialization fallbacks
        self.logger = logging.getLogger(__name__)
        # list of dicts: each entry is a diagnostic event for a failed materialization
        self.materialization_diagnostics = []
        # optional file path to persist diagnostics JSON at end of realize_plan
        self.diagnostics_outpath = diagnostics_outpath
        # Track placed unit positions for spacing enforcement
        self._placed_unit_positions: List[Tuple[float, float, float]] = []  # List of (x, y, z) positions

    @staticmethod
    def _scale_units_by_threat(unit_count: int, threat_level: str) -> int:
        """Scale unit count based on threat level.
        
        Args:
            unit_count: Base unit count
            threat_level: Threat level string (low, medium, high, extreme)
        
        Returns:
            Scaled unit count (rounded to int, minimum 1)
        """
        multipliers = {
            'low': 0.5,
            'medium': 1.0,
            'high': 1.5,
            'extreme': 2.0
        }
        multiplier = multipliers.get(threat_level.lower(), 1.0)
        return max(1, int(round(unit_count * multiplier)))
    
    @staticmethod
    def _get_unit_spacing_requirement(unit_type_str: str) -> float:
        """Get minimum spacing requirement for a unit type in meters.
        
        Args:
            unit_type_str: Unit type string (e.g., "sam_site", "truck", "artillery")
        
        Returns:
            Minimum spacing in meters
        """
        unit_lower = unit_type_str.lower()
        
        # Large systems need more space
        if any(kw in unit_lower for kw in ["sam", "radar", "launcher", "battery", "air_defense"]):
            return 2000.0  # 2km spacing for SAM sites
        elif any(kw in unit_lower for kw in ["artillery", "howitzer", "mlrs"]):
            return 1000.0  # 1km spacing for artillery
        elif any(kw in unit_lower for kw in ["tank", "apc", "vehicle"]):
            return 300.0  # 300m spacing for vehicles
        elif any(kw in unit_lower for kw in ["truck", "transport", "logistic", "convoy"]):
            return 100.0  # 100m spacing for trucks (can be closer)
        elif any(kw in unit_lower for kw in ["infantry", "soldier"]):
            return 50.0  # 50m spacing for infantry
        else:
            return 500.0  # Default 500m spacing
    
    @staticmethod
    def _scale_search_radius_by_map_size(base_radius: float, map_size: float) -> float:
        """Scale search radius based on map size.
        
        For a 196km map, use the base radius as-is or slightly scaled.
        For smaller maps, reduce proportionally.
        
        Args:
            base_radius: Base search radius in meters
            map_size: Total map size in meters
        
        Returns:
            Scaled search radius
        """
        # Scale based on map size relative to typical 196km map
        typical_map_size = 196608.0
        if map_size >= typical_map_size:
            # Large map, can use full radius or slightly larger
            return base_radius * 1.0
        else:
            # Smaller map, scale down proportionally (minimum 20% of base)
            scale_factor = max(0.2, map_size / typical_map_size)
            return base_radius * scale_factor
    
    @staticmethod
    def _select_units_for_mission_type(mission_type: str, threat_level: str, rng: random.Random) -> List[str]:
        """Select appropriate unit types for a given mission type and threat level.
        
        Args:
            mission_type: Mission type (sead, strike, cas, cap, recon)
            threat_level: Threat level (low, medium, high, extreme)
            rng: Random number generator
        
        Returns:
            List of unit type strings appropriate for the mission
        """
        mission_lower = mission_type.lower()
        threat_lower = threat_level.lower()
        
        # Base unit sets by mission type
        if mission_lower == "sead":
            # SEAD: Prioritize SAMs and radars
            if not UnitLibrary.ENEMY_SAMS:
                return ["SamBattery1"]  # Fallback
            
            # Select diverse SAM types based on threat
            sam_types = [t.unit_type for t in UnitLibrary.ENEMY_SAMS]
            # For SEAD, prefer more diverse SAM network
            num_sams = {"low": 2, "medium": 3, "high": 4, "extreme": 5}.get(threat_lower, 3)
            selected = rng.choices(sam_types, k=min(num_sams, len(sam_types)))
            
            # Add radar if available
            radar_types = [t.unit_type for t in UnitLibrary.ENEMY_SAMS if 'radar' in t.unit_type.lower()] or ["ewRadarPyramid"]
            if radar_types:
                selected.append(radar_types[0])
            
            return list(set(selected))  # Remove duplicates
        
        elif mission_lower == "strike":
            # Strike: Mix of SAMs and ground targets
            selected = []
            if UnitLibrary.ENEMY_SAMS:
                sam_count = {"low": 1, "medium": 2, "high": 3, "extreme": 4}.get(threat_lower, 2)
                sam_types = [t.unit_type for t in UnitLibrary.ENEMY_SAMS]
                selected.extend(rng.choices(sam_types, k=min(sam_count, len(sam_types))))
            
            if UnitLibrary.ENEMY_VEHICLES:
                vehicle_count = {"low": 2, "medium": 3, "high": 4, "extreme": 5}.get(threat_lower, 3)
                vehicle_types = [t.unit_type for t in UnitLibrary.ENEMY_VEHICLES]
                selected.extend(rng.choices(vehicle_types, k=min(vehicle_count, len(vehicle_types))))
            
            return selected or ["enemyMBT1"]  # Fallback
        
        elif mission_lower == "cas":
            # CAS: Ground vehicles, artillery, infantry
            selected = []
            if UnitLibrary.ENEMY_VEHICLES:
                vehicle_count = {"low": 2, "medium": 4, "high": 6, "extreme": 8}.get(threat_lower, 4)
                vehicle_types = [t.unit_type for t in UnitLibrary.ENEMY_VEHICLES]
                selected.extend(rng.choices(vehicle_types, k=min(vehicle_count, len(vehicle_types))))
            
            if UnitLibrary.ENEMY_INFANTRY:
                infantry_count = {"low": 1, "medium": 2, "high": 3, "extreme": 4}.get(threat_lower, 2)
                infantry_types = [t.unit_type for t in UnitLibrary.ENEMY_INFANTRY]
                selected.extend(rng.choices(infantry_types, k=min(infantry_count, len(infantry_types))))
            
            # Add artillery if available
            arty_types = [t.unit_type for t in UnitLibrary.ENEMY_VEHICLES if 'artillery' in t.unit_type.lower() or 'howitzer' in t.unit_type.lower()]
            if arty_types:
                selected.append(arty_types[0])
            
            return selected or ["enemyMBT1"]  # Fallback
        
        elif mission_lower in ("cap", "intercept"):
            # CAP: Enemy aircraft
            if UnitLibrary.ENEMY_AIR:
                air_count = {"low": 1, "medium": 2, "high": 3, "extreme": 4}.get(threat_lower, 2)
                air_types = [t.unit_type for t in UnitLibrary.ENEMY_AIR]
                return rng.choices(air_types, k=min(air_count, len(air_types)))
            
            return ["F-45A_AI"]  # Fallback
        
        else:
            # Default: generic enemy units
            if UnitLibrary.ENEMY_VEHICLES:
                return [rng.choice([t.unit_type for t in UnitLibrary.ENEMY_VEHICLES])]
            return ["enemyMBT1"]
    
    @staticmethod
    def _get_sam_diversity_by_threat(threat_level: str) -> Dict[str, int]:
        """Get SAM type diversity distribution based on threat level.
        
        Returns dict with sam_type hints and their relative weights.
        Lower threat = simpler SAMs, higher threat = diverse mix.
        
        Args:
            threat_level: Threat level string (low, medium, high, extreme)
        
        Returns:
            Dict mapping sam_type hint to relative weight
        """
        threat_lower = threat_level.lower()
        
        if threat_lower == 'low':
            # Simple: mostly medium range
            return {'medium_range_sam': 8, 'short_range_sam': 2}
        elif threat_lower == 'medium':
            # Balanced: medium + some long range
            return {'medium_range_sam': 6, 'long_range_sam': 3, 'short_range_sam': 1}
        elif threat_lower == 'high':
            # Diverse: mix of all types
            return {'long_range_sam': 4, 'medium_range_sam': 4, 'short_range_sam': 2}
        else:  # extreme
            # Heavy: more long range, advanced systems
            return {'long_range_sam': 5, 'medium_range_sam': 3, 'short_range_sam': 2}

    def _define_mission_key_points(
        self,
        plan: MissionPlan,
        wsm: WorldState,
        map_size: float,
        base_x: int
    ) -> Dict[str, Dict[str, Any]]:
        """
        Define strategic key points for the mission BEFORE placing units.
        
        This creates an overlay of important locations (objectives, defense points,
        staging areas) that units will be placed around. This prevents random
        scattering and ensures units form coherent groups.
        
        Args:
            plan: MissionPlan with objectives
            wsm: WorldState for territory/asset queries
            map_size: Map size in meters
            base_x: Base X coordinate for mission distance
            
        Returns:
            Dict mapping point_id to point info: {
                'position': (x, y, z),
                'type': 'objective|defense|staging|threat',
                'mission_role': 'primary_target|secondary|defense|etc',
                'radius': influence_radius,
                'priority': 1-10
            }
        """
        key_points = {}
        helper = self.terrain_helper
        
        # Get mission context
        mission_archetype = plan.metadata.get("mission_archetype", "offensive").lower()
        player_role = plan.metadata.get("player_role", "strike").lower()
        threat_level = plan.metadata.get("threat_level", "medium").lower()
        
        # Find primary objectives and their targets
        primary_targets = []
        secondary_targets = []
        defense_points = []
        
        for obj in plan.objectives:
            obj_type = obj.type if hasattr(obj, 'type') else obj.get('type', '')
            target_label = obj.target if hasattr(obj, 'target') else obj.get('target')
            
            if obj_type == 'player_task' and target_label:
                primary_targets.append({
                    'target': target_label,
                    'role': player_role,
                    'objective': obj
                })
            elif obj_type == 'secondary_objective' and target_label:
                secondary_targets.append({
                    'target': target_label,
                    'objective': obj
                })
        
        # Resolve target labels to actual map locations
        rng = self.rng
        
        # Get bases for reference
        friendly_bases = []
        enemy_bases = []
        try:
            if hasattr(helper.tc, 'bases'):
                all_bases = helper.tc.bases
                for i, base in enumerate(all_bases):
                    pos = base.get('position', (0, 0, 0))
                    if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                        base_2d = (pos[0], pos[2] if len(pos) >= 3 else pos[1])
                        # First 1-2 bases are typically friendly
                        if i < min(2, len(all_bases) // 2):
                            friendly_bases.append({
                                'position': pos,
                                'id': base.get('id'),
                                'name': base.get('name', f'Base {i}')
                            })
                        else:
                            enemy_bases.append({
                                'position': pos,
                                'id': base.get('id'),
                                'name': base.get('name', f'Base {i}')
                            })
        except Exception:
            pass
        
        # Resolve primary targets to key points
        for target_info in primary_targets:
            target_label = target_info['target']
            role = target_info['role']
            
            point_pos = None
            point_type = 'objective'
            
            if 'airbase' in target_label.lower():
                # Target an enemy airbase
                if enemy_bases:
                    base = rng.choice(enemy_bases)
                    point_pos = base['position']
                else:
                    # No enemy base found - place in enemy territory
                    point_pos = self._find_point_in_territory(
                        wsm, 'enemy', map_size, base_x, rng
                    )
                
                key_points[f"primary_target_{len(key_points)}"] = {
                    'position': point_pos,
                    'type': 'objective',
                    'mission_role': 'primary_target',
                    'radius': 5000,  # 5km influence radius
                    'priority': 10,
                    'target_label': target_label,
                    'role': role
                }
            
            elif 'sam' in target_label.lower() or 'threat' in target_label.lower():
                # For SEAD - place threat area near primary target or in enemy territory
                if key_points:
                    # Place near existing primary target
                    primary_pos = next(iter(key_points.values()))['position']
                    # Offset by 10-20km for threat layer
                    offset_km = 10 + rng.random() * 10
                    angle = rng.random() * 2 * 3.14159
                    point_pos = (
                        primary_pos[0] + math.cos(angle) * offset_km * 1000,
                        primary_pos[1],
                        primary_pos[2] + math.sin(angle) * offset_km * 1000
                    )
                    # Ensure in bounds
                    point_pos = (
                        max(0, min(point_pos[0], map_size)),
                        point_pos[1],
                        max(0, min(point_pos[2], map_size))
                    )
                else:
                    # Place in enemy territory
                    point_pos = self._find_point_in_territory(
                        wsm, 'enemy', map_size, base_x, rng
                    )
                
                key_points[f"threat_area_{len(key_points)}"] = {
                    'position': point_pos,
                    'type': 'threat',
                    'mission_role': 'primary_threat',
                    'radius': 15000,  # 15km radius for threat layer
                    'priority': 9,
                    'target_label': target_label,
                    'role': role
                }
            
            else:
                # Generic target - place in enemy territory or at strategic location
                point_pos = self._find_point_in_territory(
                    wsm, 'enemy', map_size, base_x, rng
                )
                key_points[f"target_{len(key_points)}"] = {
                    'position': point_pos,
                    'type': 'objective',
                    'mission_role': 'primary_target',
                    'radius': 5000,
                    'priority': 8,
                    'target_label': target_label
                }
        
        # Add major cities as tactical objectives (seed-dependent selection)
        # Check complexity settings for city objectives
        complexity = plan.metadata.get("complexity", {})
        include_cities = complexity.get("city_objectives", True)
        
        city_objectives = []
        if include_cities:
            city_objectives = self._find_city_objectives(helper, map_size, rng, enemy_bases)
        for i, city_obj in enumerate(city_objectives[:3]):  # Top 3 cities as objectives
            key_points[f"city_objective_{len(key_points)}"] = {
                'position': city_obj['position'],
                'type': 'objective',
                'mission_role': 'city_target',
                'radius': 5000,
                'priority': 6,
                'target_label': city_obj.get('name', f'City {i+1}'),
                'city_size': city_obj.get('size', 'medium')
            }
        
        # Add secondary objectives as key points
        for target_info in secondary_targets[:3]:  # Limit to 3 secondary points
            target_label = target_info['target']
            point_pos = self._find_point_in_territory(
                wsm, 'enemy', map_size, base_x, rng
            )
            key_points[f"secondary_{len(key_points)}"] = {
                'position': point_pos,
                'type': 'objective',
                'mission_role': 'secondary_target',
                'radius': 3000,
                'priority': 5,
                'target_label': target_label
            }
        
        # Add defense points around friendly bases (for defensive missions)
        if mission_archetype == 'defensive' and friendly_bases:
            for base in friendly_bases[:2]:
                base_pos = base['position']
                # Add defense perimeter points around friendly base
                for angle in [0, 90, 180, 270]:
                    offset_km = 15 + rng.random() * 10  # 15-25km from base
                    angle_rad = math.radians(angle + rng.random() * 30)  # Add some variance
                    defense_pos = (
                        base_pos[0] + math.cos(angle_rad) * offset_km * 1000,
                        base_pos[1],
                        base_pos[2] + math.sin(angle_rad) * offset_km * 1000
                    )
                    defense_pos = (
                        max(0, min(defense_pos[0], map_size)),
                        defense_pos[1],
                        max(0, min(defense_pos[2], map_size))
                    )
                    key_points[f"defense_{len(key_points)}"] = {
                        'position': defense_pos,
                        'type': 'defense',
                        'mission_role': 'defense_perimeter',
                        'radius': 5000,
                        'priority': 6,
                        'base_id': base['id']
                    }
        
        # For SEAD missions, ensure we have a threat area key point for SAM clustering
        if mission_archetype == 'offensive' and player_role == 'sead':
            # Check if we already have a threat area
            has_threat_area = any(
                point.get('type') == 'threat' or point.get('mission_role') == 'primary_threat'
                for point in key_points.values()
            )
            
            if not has_threat_area:
                # Create threat area near primary target (or at enemy base)
                threat_pos = None
                if key_points:
                    # Use primary target as reference
                    primary_point = next((p for p in key_points.values() if p.get('mission_role') == 'primary_target'), None)
                    if primary_point:
                        threat_pos = primary_point['position']
                    else:
                        threat_pos = next(iter(key_points.values()))['position']
                elif enemy_bases:
                    # Use enemy base
                    threat_pos = rng.choice(enemy_bases)['position']
                else:
                    # Fallback
                    threat_pos = self._find_point_in_territory(wsm, 'enemy', map_size, base_x, rng)
                
                # Offset slightly from threat position (5-10km) for SAM clustering
                offset_km = 5 + rng.random() * 5
                angle = rng.random() * 2 * 3.14159
                threat_area_pos = (
                    threat_pos[0] + math.cos(angle) * offset_km * 1000,
                    threat_pos[1],
                    threat_pos[2] + math.sin(angle) * offset_km * 1000
                )
                threat_area_pos = (
                    max(0, min(threat_area_pos[0], map_size)),
                    threat_area_pos[1],
                    max(0, min(threat_area_pos[2], map_size))
                )
                
                key_points["sead_threat_area"] = {
                    'position': threat_area_pos,
                    'type': 'threat',
                    'mission_role': 'primary_threat',
                    'radius': 20000,  # 20km radius for SAM clustering
                    'priority': 9,
                    'target_label': 'sead_targets',
                    'role': 'sead'
                }
                self.logger.info(f"PCG: Created threat area key point for SEAD mission at ({threat_area_pos[0]:.0f}, {threat_area_pos[2]:.0f})")
        
        # Ensure we have at least one key point (fallback)
        if not key_points:
            fallback_pos = self._find_point_in_territory(
                wsm, 'enemy', map_size, base_x, rng
            )
            key_points["fallback_target"] = {
                'position': fallback_pos,
                'type': 'objective',
                'mission_role': 'primary_target',
                'radius': 5000,
                'priority': 7,
                'target_label': 'enemy_unit'
            }
        
        return key_points
    
    def _place_static_convoys(
        self,
        mission_key_points: Dict[str, Dict[str, Any]],
        wsm: WorldState,
        plan: MissionPlan,
        map_size: float
    ) -> Dict[str, Any]:
        """
        Place static convoys on roads between cities or at strategic locations.
        
        Convoys are:
        - Static units (no paths yet, positioned on roads)
        - Logistics/truck units in line formation
        - Potential optional/secondary objectives
        - Located in enemy/neutral territory
        
        Args:
            mission_key_points: Dict of key mission points (may include cities)
            wsm: WorldState instance
            plan: MissionPlan instance
            map_size: Map size in meters
            
        Returns:
            Dict with 'convoys' mapping convoy_id -> convoy_info
        """
        convoys = {}
        rng = self.rng
        helper = self.terrain_helper
        
        # Check if grammar hinted at convoy objective
        convoy_hint = None
        for asset_key, asset_data in wsm.assets.items():
            if isinstance(asset_data, dict) and asset_data.get('type') == 'convoy':
                convoy_hint = asset_data
                break
        
        # Also check optional objective hints
        for asset_key, asset_data in wsm.assets.items():
            if isinstance(asset_data, dict) and 'optional_objective_hint' in asset_key:
                hint_type = asset_data.get('type', '')
                if hint_type == 'convoy':
                    convoy_hint = asset_data
                    break
        
        # Only place convoys if grammar hints at it, or if complexity allows optional objectives
        complexity = plan.metadata.get("complexity", {})
        objective_count = complexity.get("objective_count", "auto")
        if not convoy_hint and objective_count == "few":
            # Skip convoy placement if no hint and objectives are few
            return {"convoys": {}}
        
        # Find cities for convoy routes
        cities = []
        for point_id, point_info in mission_key_points.items():
            if 'city' in point_info.get('type', '').lower() or 'city' in point_info.get('name', '').lower():
                cities.append({
                    'id': point_id,
                    'position': point_info.get('position', (0, 0, 0)),
                    'name': point_info.get('target_label', point_id)
                })
        
        # Also find enemy bases as potential convoy destinations
        enemy_bases = []
        try:
            if hasattr(helper.tc, 'bases') and helper.tc.bases:
                for base in helper.tc.bases:
                    prefab_type = base.get('prefab_type', '').lower()
                    pos = base.get('position', [0, 0, 0])
                    # Enemy bases are typically not the first airbase
                    if 'airbase' in prefab_type and len(enemy_bases) == 0:
                        # Check if it's in enemy territory
                        base_pos_2d = (pos[0], pos[2]) if len(pos) >= 3 else (pos[0], pos[1])
                        if wsm.get_territory_at_position(base_pos_2d) in ['enemy', 'neutral']:
                            enemy_bases.append({
                                'id': base.get('id', f"base_{len(enemy_bases)}"),
                                'position': pos if len(pos) >= 3 else (pos[0], 0, pos[1]),
                                'name': prefab_type
                            })
        except Exception:
            pass
        
        # Determine number of convoys (1-2)
        num_convoys = 1
        if convoy_hint:
            num_convoys = 2 if rng.random() < 0.4 else 1
        elif objective_count == "many":
            num_convoys = 2 if rng.random() < 0.6 else 1
        
        convoy_counter = 0
        
        # Try to place convoys between cities
        for i in range(len(cities)):
            if convoy_counter >= num_convoys:
                break
            
            for j in range(i + 1, len(cities)):
                if convoy_counter >= num_convoys:
                    break
                
                city1 = cities[i]
                city2 = cities[j]
                
                # Check if both cities are in enemy/neutral territory
                pos1_2d = (city1['position'][0], city1['position'][2])
                pos2_2d = (city2['position'][0], city2['position'][2])
                
                if wsm.get_territory_at_position(pos1_2d) not in ['enemy', 'neutral']:
                    continue
                if wsm.get_territory_at_position(pos2_2d) not in ['enemy', 'neutral']:
                    continue
                
                # Find road path between cities
                try:
                    road_path = helper.get_road_path(
                        start_pos=(city1['position'][0], city1['position'][2]),
                        end_pos=(city2['position'][0], city2['position'][2]),
                        max_segments=50
                    )
                    
                    if len(road_path) < 2:
                        # No road connection, skip
                        continue
                    
                    # Select a position along the road (middle third)
                    path_len = len(road_path)
                    start_idx = path_len // 3
                    end_idx = 2 * path_len // 3
                    if end_idx <= start_idx:
                        start_idx = max(0, path_len // 2 - 1)
                        end_idx = min(path_len, path_len // 2 + 1)
                    
                    convoy_center_idx = rng.randint(start_idx, min(end_idx, path_len - 1))
                    convoy_center_pos = road_path[convoy_center_idx]
                    
                    # Determine convoy direction (along road)
                    if convoy_center_idx < len(road_path) - 1:
                        next_pos = road_path[convoy_center_idx + 1]
                        from pytol.misc.math_utils import calculate_bearing
                        heading = calculate_bearing(
                            (convoy_center_pos[0], convoy_center_pos[2]),
                            (next_pos[0], next_pos[2]),
                            degrees=True
                        )
                    else:
                        heading = 0.0
                    
                    # Create convoy (3-5 vehicles)
                    convoy_size = rng.randint(3, 5)
                    convoy_id = f"convoy_{convoy_counter + 1}"
                    convoy_vehicles = []
                    
                    # Available convoy unit types (logistics trucks)
                    convoy_unit_types = ['ELogisticsTruck', 'ALogisticTruck']
                    if not convoy_unit_types:
                        convoy_unit_types = ['ELogisticsTruck']
                    
                    # Place vehicles in line formation along road
                    vehicle_spacing = 75.0  # 75 meters between vehicles
                    convoy_length = (convoy_size - 1) * vehicle_spacing
                    start_offset = -convoy_length / 2
                    
                    for v_idx in range(convoy_size):
                        # Calculate position along road segment
                        offset = start_offset + v_idx * vehicle_spacing
                        offset_x = math.cos(math.radians(heading)) * offset
                        offset_z = math.sin(math.radians(heading)) * offset
                        
                        vehicle_pos = (
                            convoy_center_pos[0] + offset_x,
                            convoy_center_pos[1],
                            convoy_center_pos[2] + offset_z
                        )
                        
                        # Ensure position is on road
                        road_check = helper.get_nearest_road_point(vehicle_pos[0], vehicle_pos[2])
                        if road_check:
                            vehicle_pos = road_check['position']
                        
                        # Select unit type
                        unit_type = rng.choice(convoy_unit_types)
                        vehicle_id = f"{convoy_id}_vehicle_{v_idx + 1}"
                        
                        # Materialize convoy vehicle
                        try:
                            vehicle_obj = _materialize_unit(unit_type, vehicle_pos, name=f"Convoy Vehicle {v_idx + 1}")
                            placement_info = {
                                'position': vehicle_pos,
                                'rotation': (0.0, heading, 0.0),
                                'placement_mode': 'ground',
                                'use_smart_placement': True,
                                'align_to_surface': True,
                                'tactical_role': 'convoy_member',
                                'convoy_id': convoy_id,
                                'vehicle_index': v_idx,
                            }
                            wsm.register_unit(vehicle_id, vehicle_obj, placement_info=placement_info)
                            convoy_vehicles.append(vehicle_id)
                        except Exception as exc:
                            self.logger.warning(f"PCG: Failed to materialize convoy vehicle: {exc}")
                            # Fallback: store as dict
                            wsm.register_unit(vehicle_id, {
                                "type": unit_type,
                                "pos": vehicle_pos,
                                "team": "Enemy",
                                "convoy_id": convoy_id,
                                "vehicle_index": v_idx,
                            })
                            convoy_vehicles.append(vehicle_id)
                    
                    # Store convoy metadata
                    convoys[convoy_id] = {
                        'convoy_id': convoy_id,
                        'position': convoy_center_pos,
                        'heading': heading,
                        'vehicles': convoy_vehicles,
                        'size': convoy_size,
                        'route': {
                            'start_city': city1['name'],
                            'end_city': city2['name'],
                            'road_path': road_path,
                        },
                        'target_label': 'convoy',
                    }
                    
                    convoy_counter += 1
                    self.logger.info(f"PCG: Placed convoy '{convoy_id}' with {convoy_size} vehicles between {city1['name']} and {city2['name']}")
                    
                except Exception as exc:
                    self.logger.debug(f"PCG: Failed to place convoy between cities: {exc}")
                    continue
        
        # If we still need more convoys and have enemy bases, try base-to-city routes
        if convoy_counter < num_convoys and enemy_bases and cities:
            for base in enemy_bases[:1]:  # Use first enemy base
                if convoy_counter >= num_convoys:
                    break
                
                # Find nearest city
                nearest_city = None
                min_dist = float('inf')
                for city in cities:
                    dist = math.sqrt(
                        (base['position'][0] - city['position'][0])**2 +
                        (base['position'][2] - city['position'][2])**2
                    )
                    if dist < min_dist:
                        min_dist = dist
                        nearest_city = city
                
                if nearest_city and min_dist < 50000:  # Within 50km
                    try:
                        road_path = helper.get_road_path(
                            start_pos=(base['position'][0], base['position'][2]),
                            end_pos=(nearest_city['position'][0], nearest_city['position'][2]),
                            max_segments=50
                        )
                        
                        if len(road_path) >= 2:
                            # Place convoy near base (first third of route)
                            convoy_center_idx = rng.randint(1, max(2, len(road_path) // 3))
                            convoy_center_pos = road_path[convoy_center_idx]
                            
                            # Similar convoy creation logic as above
                            convoy_size = rng.randint(3, 4)
                            convoy_id = f"convoy_{convoy_counter + 1}"
                            convoy_vehicles = []
                            
                            # Determine heading
                            if convoy_center_idx < len(road_path) - 1:
                                next_pos = road_path[convoy_center_idx + 1]
                                from pytol.misc.math_utils import calculate_bearing
                                heading = calculate_bearing(
                                    (convoy_center_pos[0], convoy_center_pos[2]),
                                    (next_pos[0], next_pos[2]),
                                    degrees=True
                                )
                            else:
                                heading = 0.0
                            
                            convoy_unit_types = ['ELogisticsTruck', 'ALogisticTruck']
                            vehicle_spacing = 75.0
                            convoy_length = (convoy_size - 1) * vehicle_spacing
                            start_offset = -convoy_length / 2
                            
                            for v_idx in range(convoy_size):
                                offset = start_offset + v_idx * vehicle_spacing
                                offset_x = math.cos(math.radians(heading)) * offset
                                offset_z = math.sin(math.radians(heading)) * offset
                                
                                vehicle_pos = (
                                    convoy_center_pos[0] + offset_x,
                                    convoy_center_pos[1],
                                    convoy_center_pos[2] + offset_z
                                )
                                
                                road_check = helper.get_nearest_road_point(vehicle_pos[0], vehicle_pos[2])
                                if road_check:
                                    vehicle_pos = road_check['position']
                                
                                unit_type = rng.choice(convoy_unit_types)
                                vehicle_id = f"{convoy_id}_vehicle_{v_idx + 1}"
                                
                                try:
                                    vehicle_obj = _materialize_unit(unit_type, vehicle_pos, name=f"Convoy Vehicle {v_idx + 1}")
                                    placement_info = {
                                        'position': vehicle_pos,
                                        'rotation': (0.0, heading, 0.0),
                                        'placement_mode': 'ground',
                                        'use_smart_placement': True,
                                        'align_to_surface': True,
                                        'tactical_role': 'convoy_member',
                                        'convoy_id': convoy_id,
                                        'vehicle_index': v_idx,
                                    }
                                    wsm.register_unit(vehicle_id, vehicle_obj, placement_info=placement_info)
                                    convoy_vehicles.append(vehicle_id)
                                except Exception:
                                    wsm.register_unit(vehicle_id, {
                                        "type": unit_type,
                                        "pos": vehicle_pos,
                                        "team": "Enemy",
                                        "convoy_id": convoy_id,
                                        "vehicle_index": v_idx,
                                    })
                                    convoy_vehicles.append(vehicle_id)
                            
                            convoys[convoy_id] = {
                                'convoy_id': convoy_id,
                                'position': convoy_center_pos,
                                'heading': heading,
                                'vehicles': convoy_vehicles,
                                'size': convoy_size,
                                'route': {
                                    'start': 'enemy_base',
                                    'end_city': nearest_city['name'],
                                },
                                'target_label': 'convoy',
                            }
                            
                            convoy_counter += 1
                            self.logger.info(f"PCG: Placed convoy '{convoy_id}' with {convoy_size} vehicles from base to {nearest_city['name']}")
                    except Exception as exc:
                        self.logger.debug(f"PCG: Failed to place convoy from base: {exc}")
        
        # Store convoy data in WorldState
        if convoys:
            wsm.register_asset("static_convoys", {
                "convoys": convoys,
                "description": "Static convoys placed on roads for optional/secondary objectives"
            })
        
        return {"convoys": convoys}
    
    def _place_static_structures(
        self,
        mission_key_points: Dict[str, Dict[str, Any]],
        wsm: WorldState,
        plan: MissionPlan,
        map_size: float
    ) -> Dict[str, Dict[str, Any]]:
        """
        Place static structures (bunkers, factories, missile silos) at strategic locations.
        
        Static structures provide:
        - Destroyable targets that can be tracked by objectives
        - Strategic locations that units can defend
        - Event triggers (spawn reinforcements when destroyed, unlock objectives, etc.)
        - Variety in mission objectives beyond just destroying units
        
        Args:
            mission_key_points: Dict of key mission points where structures should be placed
            wsm: WorldState instance
            plan: MissionPlan instance
            map_size: Map size in meters
            
        Returns:
            Dict mapping structure_id -> structure_info (position, type, key_point_id)
        """
        static_structures = {}
        rng = self.rng
        threat_level = plan.metadata.get("threat_level", "medium").lower()
        player_role = plan.metadata.get("player_role", "strike").lower()
        
        # Get complexity settings from plan metadata
        complexity = plan.metadata.get("complexity", {})
        
        # Available static structure types for enemy
        enemy_structures = {
            'bunker': ['bunker1', 'bunkerHillside'],
            'factory': ['factory1e'],
            'missile_silo': ['missileSilo_e'],
        }
        
        # Structure placement probability - override from complexity if specified
        if complexity.get("static_structure_probability") is not None:
            structure_probability = float(complexity.get("static_structure_probability"))
        else:
            structure_probability = {
                'low': 0.3,      # 30% chance per eligible key point
                'medium': 0.5,   # 50% chance
                'high': 0.7,     # 70% chance
                'extreme': 0.9   # 90% chance
            }.get(threat_level, 0.5)
        
        # Decide how many structures to place - override from complexity if specified
        if complexity.get("num_static_structures") is not None:
            num_structures = int(complexity.get("num_static_structures"))
            num_structures = max(0, min(5, num_structures))  # Clamp 0-5
        else:
            num_structures = {
                'low': 1,
                'medium': 2,
                'high': 3,
                'extreme': 4
            }.get(threat_level, 2)
        
        # Priority key points for structure placement
        # Prefer primary targets, secondary targets, and cities
        eligible_key_points = []
        for point_id, point_info in mission_key_points.items():
            point_type = point_info.get('type', 'objective')
            mission_role = point_info.get('mission_role', '')
            priority = point_info.get('priority', 5)
            
            # Prioritize primary/secondary targets and cities
            if mission_role in ['primary_target', 'secondary_target']:
                eligible_key_points.append((point_id, point_info, priority + 5))
            elif 'city' in point_type or 'city' in point_info.get('name', '').lower():
                eligible_key_points.append((point_id, point_info, priority + 3))
            elif point_type == 'objective':
                eligible_key_points.append((point_id, point_info, priority))
        
        # Sort by priority (highest first)
        eligible_key_points.sort(key=lambda x: x[2], reverse=True)
        
        # Limit to top candidates
        max_candidates = min(num_structures + 2, len(eligible_key_points))
        eligible_key_points = eligible_key_points[:max_candidates]
        
        structure_counter = 0
        structure_types_used = set()
        
        for point_id, point_info, priority_score in eligible_key_points:
            if structure_counter >= num_structures:
                break
            
            # Skip if we've already placed a structure at this key point
            if point_id in static_structures:
                continue
            
            # Roll probability for placing structure at this point
            if rng.random() > structure_probability:
                continue
            
            center_pos = point_info.get('position', (0, 0, 0))
            if len(center_pos) < 3:
                continue
            
            # Select structure type based on key point type and mission role
            structure_type = None
            structure_unit_type = None
            
            # For primary targets: prefer factories or missile silos (high-value targets)
            if point_info.get('mission_role') == 'primary_target':
                if rng.random() < 0.4:  # 40% chance for factory
                    structure_type = 'factory'
                    structure_unit_type = rng.choice(enemy_structures['factory'])
                elif rng.random() < 0.6:  # 60% of remaining (36% total) for silo
                    structure_type = 'missile_silo'
                    structure_unit_type = rng.choice(enemy_structures['missile_silo'])
                else:  # 24% for bunker
                    structure_type = 'bunker'
                    structure_unit_type = rng.choice(enemy_structures['bunker'])
            
            # For secondary targets or cities: prefer bunkers and factories
            elif point_info.get('mission_role') == 'secondary_target' or 'city' in str(point_info.get('name', '')).lower():
                if rng.random() < 0.5:  # 50% bunker
                    structure_type = 'bunker'
                    structure_unit_type = rng.choice(enemy_structures['bunker'])
                elif rng.random() < 0.7:  # 35% factory
                    structure_type = 'factory'
                    structure_unit_type = rng.choice(enemy_structures['factory'])
                else:  # 15% silo
                    structure_type = 'missile_silo'
                    structure_unit_type = rng.choice(enemy_structures['missile_silo'])
            
            else:
                # Default: mostly bunkers
                structure_type = 'bunker'
                structure_unit_type = rng.choice(enemy_structures['bunker'])
            
            # Try to place structure near key point center (within 50-200m)
            placement_radius = 50 + rng.random() * 150  # 50-200m from center
            angle = rng.random() * 2 * 3.14159
            
            struct_x = center_pos[0] + math.cos(angle) * placement_radius
            struct_z = center_pos[2] + math.sin(angle) * placement_radius
            struct_y = self.terrain_helper.tc.get_terrain_height(struct_x, struct_z)
            
            # Ensure in bounds
            struct_x = max(0, min(struct_x, map_size))
            struct_z = max(0, min(struct_z, map_size))
            
            # Verify structure can be placed here (not in water, reasonable terrain)
            try:
                terrain_height = self.terrain_helper.tc.get_terrain_height(struct_x, struct_z)
                if terrain_height < 0:  # Likely water
                    continue
                
                # Use smart placement to ensure structure sits properly on terrain
                placement = self.terrain_helper.tc.get_smart_placement(
                    struct_x, struct_z, yaw_degrees=rng.random() * 360
                )
                final_pos = placement.get('position', (struct_x, struct_y, struct_z))
                final_rot = placement.get('rotation', (0, rng.random() * 360, 0))
            except Exception:
                # Fallback to simple placement
                final_pos = (struct_x, struct_y, struct_z)
                final_rot = (0, rng.random() * 360, 0)
            
            # Create structure unit
            structure_id = f"static_structure_{structure_counter + 1}"
            
            try:
                from pytol.classes.units import create_unit
                
                # Create static structure unit (treated as ground unit but stationary)
                structure_unit = create_unit(
                    id_name=structure_unit_type,
                    unit_name=f"{structure_type.title()} {structure_counter + 1}",
                    team="Enemy",
                    global_position=list(final_pos),
                    rotation=list(final_rot)
                )
                
                # Store placement info
                placement_info = {
                    'position': final_pos,
                    'rotation': final_rot,
                    'placement_mode': 'ground',  # Static structures are ground units
                    'use_smart_placement': True,
                    'align_to_surface': True,
                    'tactical_role': structure_type
                }
                
                # Register in world state with placement info
                wsm.register_unit(structure_id, structure_unit, placement_info=placement_info)
                
                # Record structure metadata
                static_structures[structure_id] = {
                    'structure_id': structure_id,
                    'structure_type': structure_type,
                    'unit_type': structure_unit_type,
                    'position': final_pos,
                    'key_point_id': point_id,
                    'key_point_role': point_info.get('mission_role', 'objective'),
                    'priority': priority_score
                }
                
                structure_counter += 1
                structure_types_used.add(structure_type)
                
                self.logger.debug(
                    f"PCG: Placed {structure_type} ({structure_unit_type}) at "
                    f"({final_pos[0]:.0f}, {final_pos[2]:.0f}) for key point {point_id}"
                )
                
            except Exception as exc:
                self.logger.warning(
                    f"PCG: Failed to place static structure {structure_unit_type} at "
                    f"({struct_x:.0f}, {struct_z:.0f}): {exc}"
                )
                continue
        
        # Store structures in WorldState assets for reference
        if static_structures:
            wsm.register_asset("static_structures", {
                "structures": static_structures,
                "description": "Static enemy structures (bunkers, factories, missile silos) placed at strategic locations"
            })
        
        return static_structures
    
    def _find_city_objectives(
        self,
        helper: "MissionTerrainHelper",
        map_size: float,
        rng,
        enemy_bases: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Find major cities that could serve as tactical objectives.
        
        Cities are important strategic locations - capturing/defending them
        makes for interesting mission variety.
        
        Returns:
            List of city dicts with position, name, size
        """
        city_objectives = []
        
        try:
            # Use MissionTerrainHelper's suggest_objective_locations which includes cities
            if hasattr(helper, 'suggest_objective_locations'):
                suggestions = helper.suggest_objective_locations(num_locations=10, min_city_size=15)
                
                # Filter for city suggestions
                for suggestion in suggestions:
                    name = suggestion.get('name', '').lower()
                    if 'city' in name or 'town' in name or 'urban' in name:
                        pos = suggestion.get('position')
                        if pos and len(pos) >= 3:
                            city_objectives.append({
                                'position': pos,
                                'name': suggestion.get('name', 'City'),
                                'size': 'large' if 'city' in name else 'medium'
                            })
            
            # Alternative: find cities from city blocks directly
            if not city_objectives and hasattr(helper.tc, 'city_blocks'):
                # Cluster city blocks to find major urban centers
                city_clusters = {}
                cluster_radius = 5000  # 5km cluster radius
                
                for block in helper.tc.city_blocks[:200]:  # Sample first 200 for performance
                    try:
                        block_pos = block.get('world_position', [0, 0, 0])
                        if len(block_pos) < 3:
                            continue
                        
                        block_x, block_z = block_pos[0], block_pos[2]
                        
                        # Find existing cluster or create new
                        clustered = False
                        for cluster_center, cluster_blocks in city_clusters.items():
                            cx, cz = cluster_center[0], cluster_center[1]
                            dist = ((block_x - cx)**2 + (block_z - cz)**2)**0.5
                            if dist < cluster_radius:
                                cluster_blocks.append(block_pos)
                                clustered = True
                                break
                        
                        if not clustered:
                            city_clusters[(block_x, block_z)] = [block_pos]
                    except Exception:
                        continue
                
                # Convert clusters to city objectives (sort by size)
                for cluster_center, blocks in sorted(city_clusters.items(), key=lambda x: len(x[1]), reverse=True):
                    if len(blocks) >= 10:  # At least 10 blocks = significant city
                        # Find average position
                        avg_x = sum(b[0] for b in blocks) / len(blocks)
                        avg_z = sum(b[2] for b in blocks) / len(blocks)
                        avg_y = helper.tc.get_terrain_height(avg_x, avg_z)
                        
                        city_size = 'large' if len(blocks) >= 30 else 'medium'
                        city_objectives.append({
                            'position': (avg_x, avg_y, avg_z),
                            'name': f'{city_size.title()} City ({len(blocks)} blocks)',
                            'size': city_size
                        })
            
            # Prefer cities near enemy bases or in enemy territory (more interesting)
            if city_objectives and enemy_bases:
                from pytol.misc.math_utils import calculate_2d_distance
                
                # Score cities by distance to enemy bases (closer = more interesting)
                for city in city_objectives:
                    city_pos = city['position']
                    city_2d = (city_pos[0], city_pos[2] if len(city_pos) >= 3 else city_pos[1])
                    
                    min_dist_to_enemy = min(
                        calculate_2d_distance(city_2d, (eb['position'][0], eb['position'][2] if len(eb['position']) >= 3 else eb['position'][1]))
                        for eb in enemy_bases
                    )
                    city['distance_to_enemy'] = min_dist_to_enemy
                
                # Sort by proximity to enemy bases (closer = higher priority)
                city_objectives.sort(key=lambda c: c.get('distance_to_enemy', float('inf')))
            
            # Limit and randomize selection (seed-dependent)
            num_cities = min(rng.randint(2, 5), len(city_objectives))  # 2-5 cities vary by seed
            if num_cities > 0 and city_objectives:
                city_objectives = city_objectives[:num_cities]
            
            # Add some randomization to selection
            if len(city_objectives) > num_cities:
                city_objectives = rng.sample(city_objectives, num_cities)
            
        except Exception as e:
            self.logger.debug(f"PCG: Error finding city objectives: {e}")
        
        return city_objectives
    
    def _find_point_in_territory(
        self,
        wsm: WorldState,
        territory_type: str,
        map_size: float,
        base_x: int,
        rng
    ) -> Tuple[float, float, float]:
        """Find a point within a specific territory type."""
        helper = self.terrain_helper
        
        # Try to find a point in the territory
        for attempt in range(10):
            x = rng.uniform(map_size * 0.2, map_size * 0.8)
            z = rng.uniform(map_size * 0.2, map_size * 0.8)
            
            # Adjust based on territory type
            if territory_type == 'enemy':
                # Enemy territory typically on right side of map
                x = rng.uniform(map_size * 0.5, map_size * 0.9)
            elif territory_type == 'friendly':
                # Friendly territory typically on left side
                x = rng.uniform(map_size * 0.1, map_size * 0.5)
            
            y = helper.tc.get_terrain_height(x, z)
            
            # Verify territory
            actual_territory = wsm.get_territory_at_position(x, z)
            if actual_territory == territory_type or (territory_type == 'enemy' and actual_territory == 'neutral'):
                return (x, y, z)
        
        # Fallback: return center of appropriate area
        if territory_type == 'enemy':
            x = map_size * 0.7
        else:
            x = map_size * 0.3
        z = map_size * 0.5
        y = helper.tc.get_terrain_height(x, z)
        return (x, y, z)
    
    def _select_key_point_for_unit(
        self,
        unit_type: str,
        unit_role: str,
        mission_key_points: Dict[str, Dict[str, Any]],
        map_size: float,
        wsm: WorldState,
        rng
    ) -> Tuple[float, float, float]:
        """
        Select the most appropriate mission key point for placing a unit.
        
        Units are grouped around strategic points instead of being randomly scattered.
        Different unit types are attracted to different key point types.
        
        Args:
            unit_type: Unit type string (e.g., 'enemySAM', 'tank')
            unit_role: Mission role ('sead', 'strike', etc.)
            mission_key_points: Dict of key points from _define_mission_key_points
            map_size: Map size in meters
            wsm: WorldState instance
            rng: Random number generator
            
        Returns:
            (x, y, z) target area for unit placement
        """
        if not mission_key_points:
            # Fallback: random position in enemy territory
            helper = self.terrain_helper
            fallback_pos = self._find_point_in_territory(
                wsm, 'enemy', map_size, int(map_size * 0.5), rng
            )
            return fallback_pos
        
        unit_lower = unit_type.lower()
        
        # Score each key point based on unit type and mission role
        scored_points = []
        
        for point_id, point_info in mission_key_points.items():
            score = 0.0
            point_type = point_info.get('type', 'objective')
            mission_role = point_info.get('mission_role', 'primary_target')
            priority = point_info.get('priority', 5)
            radius = point_info.get('radius', 5000)
            
            # Base score from priority
            score += priority
            
            # SAMs prefer threat areas or near primary targets
            if 'sam' in unit_lower or 'aa' in unit_lower:
                if point_type == 'threat' or mission_role == 'primary_threat':
                    score += 10
                elif mission_role == 'primary_target':
                    score += 5
                elif 'defense' in mission_role:
                    score += 3
            
            # Artillery prefers near targets but with standoff
            elif 'artillery' in unit_lower:
                if mission_role in ['primary_target', 'secondary_target']:
                    score += 7
                elif point_type == 'defense':
                    score += 4
            
            # Ground vehicles prefer near objectives or defensive positions
            elif any(t in unit_lower for t in ['tank', 'apc', 'vehicle']):
                if mission_role in ['primary_target', 'secondary_target']:
                    score += 6
                elif point_type == 'defense':
                    score += 8
                elif point_type == 'threat':
                    score += 2
            
            # For SEAD missions, SAMs should be near threat areas
            if unit_role == 'sead' and ('sam' in unit_lower or 'aa' in unit_lower):
                if point_type == 'threat':
                    score += 15  # Strong preference for threat areas
            
            scored_points.append({
                'point_id': point_id,
                'point_info': point_info,
                'score': score
            })
        
        # Sort by score (highest first)
        scored_points.sort(key=lambda x: x['score'], reverse=True)
        
        # Select from top candidates (top 3 or all if less than 3)
        top_candidates = scored_points[:min(3, len(scored_points))]
        
        # Weighted random selection from top candidates
        if len(top_candidates) > 1:
            total_score = sum(c['score'] for c in top_candidates)
            rand_val = rng.random() * total_score
            cumulative = 0
            selected = top_candidates[0]  # Default to first
            for candidate in top_candidates:
                cumulative += candidate['score']
                if rand_val <= cumulative:
                    selected = candidate
                    break
        else:
            selected = top_candidates[0] if top_candidates else scored_points[0]
        
        # Get position from selected key point
        key_point = selected['point_info']
        center_pos = key_point['position']
        radius = key_point.get('radius', 5000)
        
        # Place unit within radius of key point (not at exact center for variety)
        # Use 30-80% of radius for spacing
        offset_factor = 0.3 + rng.random() * 0.5
        offset_radius = radius * offset_factor
        angle = rng.random() * 2 * 3.14159
        
        target_x = center_pos[0] + math.cos(angle) * offset_radius
        target_z = center_pos[2] + math.sin(angle) * offset_radius
        target_y = self.terrain_helper.tc.get_terrain_height(target_x, target_z)
        
        # Ensure in bounds
        target_x = max(0, min(target_x, map_size))
        target_z = max(0, min(target_z, map_size))
        
        return (target_x, target_y, target_z)
    
    def _get_unit_category(self, unit_type_lower: str, mission_role: str) -> str:
        """
        Group units into categories for clustering.
        
        Units in the same category will cluster at the same key point,
        even if they're slightly different types (e.g., different SAM variants).
        """
        if 'sam' in unit_type_lower or 'aa' in unit_type_lower or 'patriot' in unit_type_lower or 'backstop' in unit_type_lower:
            if mission_role == 'sead':
                return 'threat_sam'  # All SAMs cluster together for SEAD
            else:
                return 'air_defense'
        elif 'radar' in unit_type_lower:
            if mission_role == 'sead':
                return 'threat_sam'  # Radars cluster with SAMs in SEAD
            else:
                return 'radar'
        elif 'artillery' in unit_type_lower or 'mlrs' in unit_type_lower:
            return 'artillery'
        elif any(t in unit_type_lower for t in ['tank', 'apc', 'vehicle', 'mbt']):
            return 'ground_vehicles'
        elif 'aircraft' in unit_type_lower or 'fighter' in unit_type_lower or 'ef-' in unit_type_lower or 'asf' in unit_type_lower:
            return 'aircraft'
        elif 'ship' in unit_type_lower or 'carrier' in unit_type_lower:
            return 'naval'
        else:
            # Generic category - group all generic enemy units
            return 'generic_enemy'
    
    def _assign_key_point_for_unit_type(
        self,
        unit_type: str,
        unit_role: str,
        mission_key_points: Dict[str, Dict[str, Any]],
        units_by_key_point: Dict[str, List[str]],
        rng
    ) -> Optional[str]:
        """
        Assign a key point to a unit type, ensuring related units cluster together.
        
        This prevents scattering by assigning the same key point to all units of
        the same type, especially for threat units (SAMs, etc.) in SEAD missions.
        
        Returns:
            key_point_id or None
        """
        if not mission_key_points:
            return None
        
        unit_lower = unit_type.lower()
        
        # For SEAD missions, all SAMs should cluster at the threat area
        if unit_role == 'sead' and ('sam' in unit_lower or 'aa' in unit_lower or 'radar' in unit_lower):
            # Find threat area key point
            for point_id, point_info in mission_key_points.items():
                if point_info.get('type') == 'threat' or point_info.get('mission_role') == 'primary_threat':
                    return point_id
        
        # For strike missions, enemy units should cluster at primary target
        if unit_role == 'strike' and not any(t in unit_lower for t in ['sam', 'aa', 'defense', 'allied']):
            # Find primary target key point
            for point_id, point_info in mission_key_points.items():
                if point_info.get('mission_role') == 'primary_target':
                    return point_id
        
        # Score all key points (same logic as _select_key_point_for_unit but return ID)
        scored_points = []
        for point_id, point_info in mission_key_points.items():
            score = 0.0
            point_type = point_info.get('type', 'objective')
            mission_role = point_info.get('mission_role', 'primary_target')
            priority = point_info.get('priority', 5)
            
            score += priority
            
            if 'sam' in unit_lower or 'aa' in unit_lower:
                if point_type == 'threat' or mission_role == 'primary_threat':
                    score += 10
                elif mission_role == 'primary_target':
                    score += 5
            elif 'artillery' in unit_lower:
                if mission_role in ['primary_target', 'secondary_target']:
                    score += 7
            elif any(t in unit_lower for t in ['tank', 'apc', 'vehicle']):
                if mission_role in ['primary_target', 'secondary_target']:
                    score += 6
                elif point_type == 'defense':
                    score += 8
            
            scored_points.append({
                'point_id': point_id,
                'score': score
            })
        
        if not scored_points:
            return None
        
        # Select highest scoring point
        scored_points.sort(key=lambda x: x['score'], reverse=True)
        return scored_points[0]['point_id']
    
    def _get_placement_near_key_point(
        self,
        key_point: Dict[str, Any],
        unit_type: str,
        existing_units_at_point: int,
        map_size: float,
        rng
    ) -> Tuple[float, float, float]:
        """
        Get placement position near a key point using formation logic.
        
        Supports different formation types based on unit category:
        - SAMs/Air Defense: Defensive ring around key point
        - Ground Vehicles: Line formation facing threat or objective
        - Artillery: Spread formation with standoff distance
        - Generic: Circular distribution
        
        Args:
            key_point: Key point dict with position, radius, etc.
            unit_type: Unit type being placed
            existing_units_at_point: Number of units already placed at this point
            map_size: Map size in meters
            rng: Random number generator
            
        Returns:
            (x, y, z) position near key point
        """
        center_pos = key_point['position']
        radius = key_point.get('radius', 5000)
        mission_role = key_point.get('mission_role', 'primary_target')
        unit_lower = unit_type.lower()
        
        # Determine formation type based on unit category
        formation_type = self._determine_formation_type(unit_lower, mission_role, existing_units_at_point)
        
        # Get position based on formation
        if formation_type == 'defensive_ring':
            # SAMs and air defense: layered defensive ring
            pos = self._formation_defensive_ring(
                center_pos, radius, existing_units_at_point, map_size, rng
            )
        elif formation_type == 'line':
            # Ground vehicles: line formation
            pos = self._formation_line(
                center_pos, radius, existing_units_at_point, map_size, rng, key_point
            )
        elif formation_type == 'wedge':
            # Assault units: wedge formation toward objective
            pos = self._formation_wedge(
                center_pos, radius, existing_units_at_point, map_size, rng, key_point
            )
        elif formation_type == 'spread':
            # Artillery: spread formation with spacing
            pos = self._formation_spread(
                center_pos, radius, existing_units_at_point, map_size, rng
            )
        else:
            # Default: circular distribution
            pos = self._formation_circular(
                center_pos, radius, existing_units_at_point, map_size, rng
            )
        
        return pos
    
    def _determine_formation_type(self, unit_type_lower: str, mission_role: str, unit_count: int) -> str:
        """Determine which formation type to use for this unit."""
        if 'sam' in unit_type_lower or 'aa' in unit_type_lower or 'patriot' in unit_type_lower or 'radar' in unit_type_lower:
            return 'defensive_ring'  # Air defense in defensive ring
        elif any(t in unit_type_lower for t in ['tank', 'apc', 'mbt']):
            if mission_role == 'primary_target' or mission_role == 'secondary_target':
                return 'line'  # Ground units attacking in line
            else:
                return 'wedge'  # Ground units in wedge formation
        elif 'artillery' in unit_type_lower:
            return 'spread'  # Artillery spread out
        elif any(t in unit_type_lower for t in ['vehicle', 'truck']):
            return 'line'  # Vehicles in line/column
        else:
            return 'circular'  # Default circular distribution
    
    def _formation_defensive_ring(
        self,
        center_pos: Tuple[float, float, float],
        radius: float,
        unit_index: int,
        map_size: float,
        rng
    ) -> Tuple[float, float, float]:
        """Place units in defensive ring around key point (for SAMs)."""
        # Use 60-80% of radius for defensive positions
        ring_radius = radius * (0.6 + rng.random() * 0.2)
        
        # For SAM sites, space evenly around the threat area
        # First 4 units: cardinal directions (N, E, S, W)
        if unit_index < 4:
            angles = [0, 90, 180, 270]  # North, East, South, West
            base_angle = math.radians(angles[unit_index])
            angle_variance = 15.0  # ±15 degrees variance
        else:
            # Additional units: fill gaps between cardinal directions
            angle_spacing = 360.0 / max(unit_index + 1, 8)
            base_angle = math.radians(unit_index * angle_spacing)
            angle_variance = angle_spacing * 0.2
        
        angle = base_angle + math.radians(rng.uniform(-angle_variance, angle_variance))
        
        target_x = center_pos[0] + math.cos(angle) * ring_radius
        target_z = center_pos[2] + math.sin(angle) * ring_radius
        target_y = self.terrain_helper.tc.get_terrain_height(target_x, target_z)
        
        # Ensure in bounds
        target_x = max(0, min(target_x, map_size))
        target_z = max(0, min(target_z, map_size))
        
        return (target_x, target_y, target_z)
    
    def _formation_line(
        self,
        center_pos: Tuple[float, float, float],
        radius: float,
        unit_index: int,
        map_size: float,
        rng,
        key_point: Dict[str, Any]
    ) -> Tuple[float, float, float]:
        """Place units in a line formation (for ground vehicles)."""
        # Line extends perpendicular to threat direction
        # For now, use random line direction, but units spread along line
        
        if unit_index == 0:
            # First unit at center-forward position
            offset_factor = 0.4 + rng.random() * 0.2  # 40-60% of radius
            line_angle = rng.random() * 2 * 3.14159
        else:
            # Subsequent units spread along line
            line_angle = rng.random() * 2 * 3.14159  # Line direction
            offset_factor = 0.4 + rng.random() * 0.3  # 40-70% of radius
        
        # Calculate position along line
        along_line = (unit_index - 1) * 500  # 500m spacing between units
        perpendicular_offset = rng.uniform(-200, 200)  # ±200m perpendicular variance
        
        # Calculate position
        target_x = center_pos[0] + math.cos(line_angle) * along_line + math.cos(line_angle + math.pi/2) * perpendicular_offset + math.cos(line_angle) * offset_factor * radius * 0.5
        target_z = center_pos[2] + math.sin(line_angle) * along_line + math.sin(line_angle + math.pi/2) * perpendicular_offset + math.sin(line_angle) * offset_factor * radius * 0.5
        target_y = self.terrain_helper.tc.get_terrain_height(target_x, target_z)
        
        # Ensure in bounds
        target_x = max(0, min(target_x, map_size))
        target_z = max(0, min(target_z, map_size))
        
        return (target_x, target_y, target_z)
    
    def _formation_wedge(
        self,
        center_pos: Tuple[float, float, float],
        radius: float,
        unit_index: int,
        map_size: float,
        rng,
        key_point: Dict[str, Any]
    ) -> Tuple[float, float, float]:
        """Place units in wedge/V-formation (for assault units)."""
        # Wedge formation: units spread in V shape toward objective
        wedge_angle = 45.0  # 45 degree wedge
        
        if unit_index == 0:
            # Point unit at center-forward
            offset_factor = 0.5
            angle = 0
        else:
            # Spread units in wedge
            offset_factor = 0.5 + (unit_index * 0.1)  # Stagger forward
            side = 1 if (unit_index % 2 == 0) else -1  # Alternate sides
            wedge_position = (unit_index // 2) + 1
            angle_offset = math.radians(side * wedge_position * (wedge_angle / 3))
            angle = angle_offset
        
        offset_radius = radius * offset_factor
        
        target_x = center_pos[0] + math.cos(angle) * offset_radius
        target_z = center_pos[2] + math.sin(angle) * offset_radius
        target_y = self.terrain_helper.tc.get_terrain_height(target_x, target_z)
        
        # Ensure in bounds
        target_x = max(0, min(target_x, map_size))
        target_z = max(0, min(target_z, map_size))
        
        return (target_x, target_y, target_z)
    
    def _formation_spread(
        self,
        center_pos: Tuple[float, float, float],
        radius: float,
        unit_index: int,
        map_size: float,
        rng
    ) -> Tuple[float, float, float]:
        """Place units in spread formation (for artillery with spacing)."""
        # Artillery needs more spacing to avoid counter-battery fire
        min_spacing = 800  # 800m minimum between artillery pieces
        
        if unit_index == 0:
            offset_factor = 0.5
        else:
            # Spread out more
            offset_factor = 0.5 + (unit_index * 0.15)  # 50-95% of radius
        
        angle_spacing = 360.0 / max(6, unit_index + 2)  # Max 6 directions
        angle = math.radians(unit_index * angle_spacing + rng.uniform(-10, 10))
        
        offset_radius = radius * offset_factor
        
        target_x = center_pos[0] + math.cos(angle) * offset_radius
        target_z = center_pos[2] + math.sin(angle) * offset_radius
        target_y = self.terrain_helper.tc.get_terrain_height(target_x, target_z)
        
        # Ensure in bounds
        target_x = max(0, min(target_x, map_size))
        target_z = max(0, min(target_z, map_size))
        
        return (target_x, target_y, target_z)
    
    def _formation_circular(
        self,
        center_pos: Tuple[float, float, float],
        radius: float,
        unit_index: int,
        map_size: float,
        rng
    ) -> Tuple[float, float, float]:
        """Place units in circular distribution (default)."""
        if unit_index == 0:
            offset_factor = 0.3 + rng.random() * 0.2  # 30-50% of radius
        elif unit_index < 3:
            offset_factor = 0.4 + rng.random() * 0.3  # 40-70% of radius
            angle_spacing = 360.0 / (unit_index + 2)
        else:
            offset_factor = 0.5 + rng.random() * 0.4  # 50-90% of radius
            angle_spacing = 360.0 / min(8, unit_index + 2)
        
        offset_radius = radius * offset_factor
        
        if unit_index > 0:
            base_angle = unit_index * angle_spacing
            angle_variance = angle_spacing * 0.3
            angle = math.radians(base_angle + rng.uniform(-angle_variance, angle_variance))
        else:
            angle = rng.random() * 2 * 3.14159
        
        target_x = center_pos[0] + math.cos(angle) * offset_radius
        target_z = center_pos[2] + math.sin(angle) * offset_radius
        target_y = self.terrain_helper.tc.get_terrain_height(target_x, target_z)
        
        # Ensure in bounds
        target_x = max(0, min(target_x, map_size))
        target_z = max(0, min(target_z, map_size))
        
        return (target_x, target_y, target_z)
    
    def _place_unit_with_retries(
        self,
        unit_type_str: str,
        unit_role: str,
        target_area: Tuple[float, float, float],
        mission_key_points: Dict[str, Dict[str, Any]],
        units_by_key_point: Dict[str, List[str]],
        key_point_id: Optional[str],
        wsm: WorldState,
        plan: MissionPlan,
        map_size: float,
        _place_unit_intelligently_fn: Any,
        _coherent_unit_placement_fn: Any,
        rng
    ) -> Optional[Tuple[Tuple[float, float, float], Dict[str, Any]]]:
        """
        Place unit with progressive retry strategy.
        
        Retry logic:
        1. Try coherent placement at primary key point (strict validation)
        2. Try coherent placement at primary key point (relaxed validation)
        3. Try coherent placement at alternative key points
        4. Try intelligent placement without strict validation
        5. Try basic placement with relaxed constraints
        
        Args:
            unit_type_str: Unit type to place
            unit_role: Mission role
            target_area: Initial target area
            mission_key_points: Available key points
            units_by_key_point: Units already at each key point
            key_point_id: Primary key point ID
            wsm: WorldState instance
            plan: MissionPlan instance
            map_size: Map size in meters
            _place_unit_intelligently_fn: Function for intelligent placement
            _coherent_unit_placement_fn: Function for coherent placement
            rng: Random number generator
            
        Returns:
            Tuple of (position, placement_info) or None if all attempts fail
        """
        max_attempts = 5
        retry_count = 0
        
        # Strategy 1: Coherent placement at primary key point (strict)
        if key_point_id and key_point_id in mission_key_points:
            coherent_result = _coherent_unit_placement_fn(
                unit_type_str=unit_type_str,
                unit_role=unit_role,
                target_area=target_area,
                wsm=wsm,
                plan=plan,
                _place_unit_intelligently_fn=_place_unit_intelligently_fn
            )
            
            if coherent_result:
                pos, placement_info = coherent_result
                placement_info["retry_attempts"] = retry_count + 1
                placement_info["placement_strategy"] = "coherent_primary_strict"
                return (pos, placement_info)
            
            retry_count += 1
            
            # Strategy 2: Coherent placement at primary key point (with relaxed search radius)
            # Widen the search area slightly
            if key_point_id in mission_key_points:
                key_point = mission_key_points[key_point_id]
                widened_radius = key_point.get('radius', 5000) * 1.5  # 50% wider
                
                # Generate new target area with wider radius
                center_pos = key_point['position']
                angle = rng.random() * 2 * 3.14159
                offset_factor = 0.6 + rng.random() * 0.3  # 60-90% of widened radius
                new_target_x = center_pos[0] + math.cos(angle) * widened_radius * offset_factor
                new_target_z = center_pos[2] + math.sin(angle) * widened_radius * offset_factor
                new_target_y = self.terrain_helper.tc.get_terrain_height(new_target_x, new_target_z)
                new_target_area = (new_target_x, new_target_y, new_target_z)
                
                coherent_result = _coherent_unit_placement_fn(
                    unit_type_str=unit_type_str,
                    unit_role=unit_role,
                    target_area=new_target_area,
                    wsm=wsm,
                    plan=plan,
                    _place_unit_intelligently_fn=_place_unit_intelligently_fn
                )
                
                if coherent_result:
                    pos, placement_info = coherent_result
                    placement_info["retry_attempts"] = retry_count + 1
                    placement_info["placement_strategy"] = "coherent_primary_relaxed"
                    return (pos, placement_info)
                
                retry_count += 1
        
        # Strategy 3: Try alternative key points (if primary failed)
        if len(mission_key_points) > 1:
            # Try other key points in priority order
            scored_points = []
            for point_id, point_info in mission_key_points.items():
                if point_id == key_point_id:
                    continue  # Skip primary (already tried)
                
                priority = point_info.get('priority', 5)
                point_type = point_info.get('type', 'objective')
                mission_role_kp = point_info.get('mission_role', '')
                
                score = priority
                unit_lower = unit_type_str.lower()
                
                # Match unit type to key point type
                if 'sam' in unit_lower and point_type == 'threat':
                    score += 5
                elif any(t in unit_lower for t in ['tank', 'apc']) and mission_role_kp in ['primary_target', 'secondary_target']:
                    score += 3
                
                scored_points.append((point_id, score, point_info))
            
            scored_points.sort(key=lambda x: x[1], reverse=True)
            
            # Try top 2 alternative key points
            for point_id, score, point_info in scored_points[:2]:
                alt_target_area = self._get_placement_near_key_point(
                    key_point=point_info,
                    unit_type=unit_type_str,
                    existing_units_at_point=len(units_by_key_point.get(point_id, [])),
                    map_size=map_size,
                    rng=rng
                )
                
                coherent_result = _coherent_unit_placement_fn(
                    unit_type_str=unit_type_str,
                    unit_role=unit_role,
                    target_area=alt_target_area,
                    wsm=wsm,
                    plan=plan,
                    _place_unit_intelligently_fn=_place_unit_intelligently_fn
                )
                
                if coherent_result:
                    pos, placement_info = coherent_result
                    placement_info["retry_attempts"] = retry_count + 1
                    placement_info["placement_strategy"] = f"coherent_alternative_{point_id}"
                    return (pos, placement_info)
                
                retry_count += 1
                if retry_count >= max_attempts - 1:
                    break
        
        # Strategy 4: Intelligent placement without strict coherent validation
        # This bypasses some validation layers but still uses terrain helpers
        intelligent_result = _place_unit_intelligently_fn(
            unit_type_str=unit_type_str,
            unit_role=unit_role,
            target_area=target_area,
            wsm=wsm,
            plan=plan
        )
        
        if intelligent_result:
            pos, placement_info = intelligent_result
            # Basic validation: just check map bounds
            map_size_actual = map_size
            if 0 <= pos[0] <= map_size_actual and 0 <= pos[2] <= map_size_actual:
                placement_info["retry_attempts"] = retry_count + 1
                placement_info["placement_strategy"] = "intelligent_no_validation"
                placement_info["coherent_placement"] = False
                return (pos, placement_info)
        
        retry_count += 1
        
        # Strategy 5: Basic placement with minimal constraints (last resort)
        # Use key point position directly, just adjust height
        if key_point_id and key_point_id in mission_key_points:
            key_point = mission_key_points[key_point_id]
            center_pos = key_point['position']
            radius = key_point.get('radius', 5000)
            
            # Random position within radius
            angle = rng.random() * 2 * 3.14159
            offset = rng.random() * radius * 0.8  # 0-80% of radius
            fallback_x = center_pos[0] + math.cos(angle) * offset
            fallback_z = center_pos[2] + math.sin(angle) * offset
            fallback_y = self.terrain_helper.tc.get_terrain_height(fallback_x, fallback_z)
            
            # Ensure in bounds
            fallback_x = max(0, min(fallback_x, map_size))
            fallback_z = max(0, min(fallback_z, map_size))
            fallback_pos = (fallback_x, fallback_y, fallback_z)
            
            if 0 <= fallback_x <= map_size and 0 <= fallback_z <= map_size:
                placement_info = {
                    "position": fallback_pos,
                    "placement_mode": "ground",
                    "use_smart_placement": True,
                    "source_query": "fallback_basic",
                    "tactical_role": "fallback_placement",
                    "retry_attempts": retry_count + 1,
                    "placement_strategy": "fallback_basic",
                    "coherent_placement": False
                }
                self.logger.warning(f"PCG: Used fallback placement for '{unit_type_str}' after {retry_count + 1} attempts")
                return (fallback_pos, placement_info)
        
        # All strategies failed
        self.logger.warning(f"PCG: Failed to place '{unit_type_str}' after {retry_count + 1} attempts")
        return None

    def _place_iads_layer(
        self,
        target_center: Tuple[float, float, float],
        layer_type: str,
        radius_range: Tuple[float, float],
        wsm: WorldState,
        plan: MissionPlan,
        unit_type: str = "enemySAM",
        existing_positions: Optional[List[Tuple[float, float, float]]] = None
    ) -> Optional[Tuple[Tuple[float, float, float], Dict[str, Any]]]:
        """
        Place IADS (Integrated Air Defense System) layer using tactical queries.
        
        Creates layered SAM defenses:
        - Outer ring: Long-range SAMs on elevated positions at 15-30km from target
        - Middle ring: Medium-range SAMs at 5-15km from target
        - Inner ring: SHORAD/AAA on flat areas within 5km
        
        Args:
            target_center: Center point to defend (x, y, z)
            layer_type: "outer_ring", "middle_ring", or "inner_ring"
            radius_range: (min_distance, max_distance) in meters
            wsm: WorldState instance
            plan: MissionPlan instance
            unit_type: Unit type to place
            existing_positions: List of already-placed unit positions for spacing
            
        Returns:
            Tuple of (position, placement_info) or None if placement failed
        """
        if self.terrain_helper is None:
            return None
        
        helper = self.terrain_helper
        min_dist, max_dist = radius_range
        
        # Get territory constraints for enemy units
        territory_constraints = {}
        try:
            territory_constraints = wsm.get_territory_constraints("Enemy", include_excluded=True)
        except Exception:
            pass
        
        # Scale distances based on map size
        map_size = getattr(helper.tc, 'total_map_size_meters', 196608.0)
        min_dist_scaled = helper.scale_search_radius_by_map_size(min_dist)
        max_dist_scaled = helper.scale_search_radius_by_map_size(max_dist)
        
        placement_info = {
            "placement_mode": "ground",
            "use_smart_placement": True,
            "align_to_surface": True,
            "rotation": (0.0, 0.0, 0.0),
            "tactical_role": f"iads_{layer_type}",
        }
        
        candidates = []
        
        try:
            if layer_type == "outer_ring":
                # Long-range SAM on elevated positions (high ground advantage)
                # First try: find highest point in area (mountain peaks) for maximum coverage
                try:
                    highest = helper.find_highest_point_in_area(
                        center_x=target_center[0],
                        center_z=target_center[2],
                        search_radius=max_dist_scaled,
                        existing_unit_positions=existing_positions,
                        min_spacing_from_units=500.0
                    )
                    if highest:
                        # Validate against territory constraints
                        if territory_constraints.get('position_validator'):
                            if territory_constraints['position_validator']((highest[0], highest[2])):
                                candidates = [{'position': highest, 'heading': 0}]
                                placement_info["source_query"] = "find_highest_point_in_area"
                        elif not territory_constraints.get('constraint_area'):
                            candidates = [{'position': highest, 'heading': 0}]
                            placement_info["source_query"] = "find_highest_point_in_area"
                except Exception:
                    pass
                
                # Fallback: use elevated positions if highest point not found
                if not candidates:
                    candidates_result = helper.find_elevated_positions(
                        center_x=target_center[0],
                        center_z=target_center[2],
                        search_radius=max_dist_scaled,
                        min_height_advantage=100,  # 100m elevation advantage
                        num_samples=15,
                        constraint_area=territory_constraints.get('constraint_area'),
                        excluded_areas=territory_constraints.get('excluded_areas'),
                        position_validator=territory_constraints.get('position_validator'),
                        existing_unit_positions=existing_positions,
                        min_spacing_from_units=500.0  # SAMs need spacing
                    )
                    if isinstance(candidates_result, dict):
                        candidates_result = [candidates_result]
                    elif candidates_result and not isinstance(candidates_result[0], dict):
                        # Convert list of positions to list of dicts
                        candidates_result = [{'position': pos, 'heading': 0} for pos in candidates_result if isinstance(pos, (list, tuple)) and len(pos) >= 3]
                    candidates = candidates_result or []
                    if not placement_info.get("source_query"):
                        placement_info["source_query"] = "find_elevated_positions"
                
            elif layer_type == "middle_ring":
                # Medium-range SAM with observation post logic (good LOS coverage)
                op_result = helper.find_observation_post(
                    target_area=target_center,
                    min_dist=min_dist_scaled,
                    max_dist=max_dist_scaled,
                    num_candidates=15,
                    constraint_area=territory_constraints.get('constraint_area'),
                    excluded_areas=territory_constraints.get('excluded_areas'),
                    position_validator=territory_constraints.get('position_validator'),
                    existing_unit_positions=existing_positions,
                    min_spacing_from_units=500.0
                )
                if op_result:
                    if isinstance(op_result, (list, tuple)) and len(op_result) >= 3:
                        # Single position returned
                        candidates = [{'position': op_result, 'heading': 0}]
                    elif isinstance(op_result, dict) and 'position' in op_result:
                        candidates = [op_result]
                    elif isinstance(op_result, list):
                        candidates = op_result if all(isinstance(c, dict) for c in op_result) else []
                placement_info["source_query"] = "find_observation_post"
                
            else:  # inner_ring / SHORAD
                # Short-range on flat areas near target
                flat_zones_result = helper.find_flat_landing_zones(
                    center_x=target_center[0],
                    center_z=target_center[2],
                    search_radius=max_dist_scaled,
                    min_area_radius=50,
                    max_slope_degrees=10
                )
                if flat_zones_result:
                    if isinstance(flat_zones_result, list):
                        if flat_zones_result and isinstance(flat_zones_result[0], (list, tuple)) and len(flat_zones_result[0]) >= 3:
                            # List of positions
                            candidates = [{'position': pos, 'heading': 0} for pos in flat_zones_result]
                        elif flat_zones_result and isinstance(flat_zones_result[0], dict):
                            candidates = flat_zones_result
                    else:
                        candidates = []
                placement_info["source_query"] = "find_flat_landing_zones"
            
            # Filter candidates by distance from target
            from pytol.misc.math_utils import calculate_2d_distance
            valid_candidates = []
            target_2d = (target_center[0], target_center[2])
            
            for candidate in candidates:
                if not isinstance(candidate, dict) or 'position' not in candidate:
                    continue
                
                pos = candidate['position']
                if not isinstance(pos, (list, tuple)) or len(pos) < 3:
                    continue
                
                pos_2d = (pos[0], pos[2])
                dist = calculate_2d_distance(pos_2d, target_2d)
                
                # Check if within radius range
                if min_dist_scaled <= dist <= max_dist_scaled:
                    # Verify line-of-sight to target (important for SAM coverage)
                    try:
                        target_3d = (target_center[0], target_center[1] + 100, target_center[2])  # 100m AGL
                        has_los = helper.has_line_of_sight(
                            pos1=(pos[0], pos[1] + 8, pos[2]),  # Radar mast height
                            pos2=target_3d,
                            steps=20
                        )
                        if has_los:
                            valid_candidates.append({
                                'position': pos,
                                'heading': candidate.get('heading', 0),
                                'distance': dist
                            })
                    except Exception:
                        # If LOS check fails, still include candidate (might be valid)
                        valid_candidates.append({
                            'position': pos,
                            'heading': candidate.get('heading', 0),
                            'distance': dist
                        })
            
            # Select best candidate (prefer closer to ideal distance)
            if valid_candidates:
                ideal_dist = (min_dist_scaled + max_dist_scaled) / 2
                valid_candidates.sort(key=lambda c: abs(c['distance'] - ideal_dist))
                selected = valid_candidates[0]
                
                placement_info["position"] = selected['position']
                placement_info["rotation"] = (0.0, selected['heading'], 0.0)
                
                return (selected['position'], placement_info)
                
        except Exception as e:
            self.logger.debug(f"PCG: IADS layer placement error for {layer_type}: {e}")
        
        return None
    
    def _coherent_unit_placement(
        self,
        unit_type_str: str,
        unit_role: str,
        target_area: Optional[Tuple[float, float, float]],
        wsm: WorldState,
        plan: MissionPlan,
        _place_unit_intelligently_fn: Any
    ) -> Optional[Tuple[Tuple[float, float, float], Dict[str, Any]]]:
        """
        Place unit with 4-layer coherence validation:
        1. Mission context (objectives, role, archetype)
        2. Territory (unit allowed in territory, correct team territory)
        3. Terrain (slope, LOS, accessibility)
        4. Unit-to-unit (spacing, formations, relationships)
        
        Returns:
            Tuple of (position, placement_info) or None if all validation fails.
        """
        if self.terrain_helper is None:
            return None
        
        # Get map size for bounds checking
        map_size = 196608.0
        try:
            if self.terrain_helper and hasattr(self.terrain_helper, 'tc'):
                map_size = getattr(self.terrain_helper.tc, 'total_map_size_meters', 196608.0)
        except Exception:
            pass
        
        def _validate_map_bounds(pos):
            """Check if position is within map bounds."""
            if pos is None or len(pos) < 3:
                return False
            x, y, z = pos[0], pos[1], pos[2]
            return (0 <= x <= map_size and 0 <= z <= map_size)
        
        # Layer 0: Check for related units already placed and group nearby
        # Also check for objective-related positioning
        unit_lower = unit_type_str.lower()
        related_unit_positions = []
        objective_positions = []
        objective_key_point_positions = []  # Positions from mission key points
        
        # Identify related unit types that should be grouped together
        if "sam" in unit_lower or "aa" in unit_lower:
            # SAMs should be near radars
            for unit_key, unit_obj in wsm.units.items():
                if isinstance(unit_obj, dict):
                    other_type = unit_obj.get("type", "").lower()
                    other_pos = unit_obj.get("pos")
                else:
                    other_type = getattr(unit_obj, "unit_type", "").lower()
                    other_pos = getattr(unit_obj, "global_position", None)
                
                if other_pos and ("radar" in other_type or "sam" in other_type or "aa" in other_type):
                    # Get position from placement info if available
                    placement = wsm.unit_placements.get(unit_key, {})
                    if placement.get("position"):
                        other_pos = placement["position"]
                    if other_pos and len(other_pos) >= 3:
                        related_unit_positions.append((other_pos[0], other_pos[2]))
            
            # SAMs should also be near their objective targets (defensive positions)
            # Find objectives that target SAMs or air defense
            for obj_key, obj_info in wsm.objectives.items():
                if isinstance(obj_info, dict):
                    obj_target_label = obj_info.get("target_label", "").lower()
                    # If this objective targets SAMs/AA, find units that are targets
                    if "sam" in obj_target_label or "aa" in obj_target_label or "air_defense" in obj_target_label:
                        # Find target units for this objective
                        try:
                            target_units = wsm.query_units_by_pattern(obj_target_label)
                            for target_unit in target_units:
                                if isinstance(target_unit, dict):
                                    tpos = target_unit.get("pos")
                                else:
                                    tpos = getattr(target_unit, "global_position", None)
                                if tpos and len(tpos) >= 3:
                                    objective_positions.append((tpos[0], tpos[2]))
                        except Exception:
                            pass
        
        elif "radar" in unit_lower:
            # Radars should be near SAMs
            for unit_key, unit_obj in wsm.units.items():
                if isinstance(unit_obj, dict):
                    other_type = unit_obj.get("type", "").lower()
                    other_pos = unit_obj.get("pos")
                else:
                    other_type = getattr(unit_obj, "unit_type", "").lower()
                    other_pos = getattr(unit_obj, "global_position", None)
                
                if other_pos and ("sam" in other_type or "aa" in other_type):
                    placement = wsm.unit_placements.get(unit_key, {})
                    if placement.get("position"):
                        other_pos = placement["position"]
                    if other_pos and len(other_pos) >= 3:
                        related_unit_positions.append((other_pos[0], other_pos[2]))
        
        elif any(t in unit_lower for t in ["convoy", "logistic", "truck", "transport"]):
            # Convoys should be grouped together
            for unit_key, unit_obj in wsm.units.items():
                if isinstance(unit_obj, dict):
                    other_type = unit_obj.get("type", "").lower()
                    other_pos = unit_obj.get("pos")
                else:
                    other_type = getattr(unit_obj, "unit_type", "").lower()
                    other_pos = getattr(unit_obj, "global_position", None)
                
                if other_pos and any(t in other_type for t in ["convoy", "logistic", "truck", "transport"]):
                    placement = wsm.unit_placements.get(unit_key, {})
                    if placement.get("position"):
                        other_pos = placement["position"]
                    if other_pos and len(other_pos) >= 3:
                        related_unit_positions.append((other_pos[0], other_pos[2]))
        
        # FIRST: Check mission key points for objective positions
        # This is critical - units related to objectives should be near the objective location
        key_points_asset = wsm.assets.get("mission_key_points", {})
        key_points = key_points_asset.get("points", {}) if isinstance(key_points_asset, dict) else {}
        
        # Find key points that match objectives this unit is related to
        for obj_key, obj_info in wsm.objectives.items():
            if isinstance(obj_info, dict):
                obj_target_label = obj_info.get("target_label", "").lower()
                obj_type = obj_info.get("type", "")
                
                # Check if this objective might target units like this one
                unit_matches_objective = False
                if "sam" in unit_lower and ("sam" in obj_target_label or "air_defense" in obj_target_label):
                    unit_matches_objective = True
                elif "artillery" in unit_lower and ("artillery" in obj_target_label or "battery" in obj_target_label):
                    unit_matches_objective = True
                elif any(t in unit_lower for t in ["convoy", "logistic"]) and ("convoy" in obj_target_label or "logistic" in obj_target_label):
                    unit_matches_objective = True
                elif "bunker" in unit_lower and ("bunker" in obj_target_label or "defensive" in obj_target_label):
                    unit_matches_objective = True
                elif "factory" in unit_lower and "factory" in obj_target_label:
                    unit_matches_objective = True
                elif "airbase" in obj_target_label or "base" in obj_target_label:
                    # Units defending or attacking airbases should be near the airbase
                    # Check if this unit type is related to airbase objectives
                    if any(t in unit_lower for t in ["sam", "aa", "radar", "defense"]) or "airbase" in unit_lower:
                        unit_matches_objective = True
                
                # If unit matches objective, find the key point for this objective
                if unit_matches_objective:
                    # Search key points for one matching this objective
                    for kp_id, kp_info in key_points.items():
                        if isinstance(kp_info, dict):
                            kp_target_label = kp_info.get("target_label", "").lower()
                            kp_role = kp_info.get("mission_role", "").lower()
                            kp_pos = kp_info.get("position")
                            
                            # Match key point to objective
                            if (kp_target_label and obj_target_label and 
                                (kp_target_label in obj_target_label or obj_target_label in kp_target_label)):
                                if kp_pos and len(kp_pos) >= 3:
                                    objective_key_point_positions.append((kp_pos[0], kp_pos[2]))
                                    self.logger.debug(f"PCG: Found key point '{kp_id}' for objective '{obj_key}' at ({kp_pos[0]:.0f}, {kp_pos[2]:.0f})")
                            # Also match by mission role (primary_target, etc.)
                            elif kp_role in ["primary_target", "primary_threat"] and obj_type == "Destroy":
                                if kp_pos and len(kp_pos) >= 3:
                                    objective_key_point_positions.append((kp_pos[0], kp_pos[2]))
                                    self.logger.debug(f"PCG: Found key point '{kp_id}' by role '{kp_role}' for objective '{obj_key}'")
        
        # SECOND: Check for objectives that target this unit type
        # This helps place units near their objective targets and group units from same objective
        for obj_key, obj_info in wsm.objectives.items():
            if isinstance(obj_info, dict):
                obj_target_label = obj_info.get("target_label", "").lower()
                obj_type = obj_info.get("type", "")
                
                # Check if this objective might target units like this one
                unit_matches_objective = False
                if "sam" in unit_lower and ("sam" in obj_target_label or "air_defense" in obj_target_label):
                    unit_matches_objective = True
                elif "artillery" in unit_lower and ("artillery" in obj_target_label or "battery" in obj_target_label):
                    unit_matches_objective = True
                elif any(t in unit_lower for t in ["convoy", "logistic"]) and ("convoy" in obj_target_label or "logistic" in obj_target_label):
                    unit_matches_objective = True
                elif "bunker" in unit_lower and ("bunker" in obj_target_label or "defensive" in obj_target_label):
                    unit_matches_objective = True
                elif "factory" in unit_lower and "factory" in obj_target_label:
                    unit_matches_objective = True
                
                # If this unit type matches the objective, find existing target units
                if unit_matches_objective and obj_type == "Destroy":
                    try:
                        # Find units that are already targets of this objective
                        target_units = wsm.query_units_by_pattern(obj_target_label)
                        for target_unit in target_units:
                            if isinstance(target_unit, dict):
                                tpos = target_unit.get("pos")
                            else:
                                tpos = getattr(target_unit, "global_position", None)
                            if tpos and len(tpos) >= 3:
                                # Get position from placement info if available
                                for wsm_key, u in wsm.units.items():
                                    if u is target_unit:
                                        placement = wsm.unit_placements.get(wsm_key, {})
                                        if placement.get("position"):
                                            tpos = placement["position"]
                                        break
                                objective_positions.append((tpos[0], tpos[2]))
                    except Exception:
                        pass
                    
                    # Also find other units of the same type that are already placed
                    # This groups units from the same objective together
                    for wsm_key, other_unit in wsm.units.items():
                        # Skip if this is the same unit (we're placing it now)
                        # We can't skip by key since we don't know the key yet, so we'll check by type
                        if isinstance(other_unit, dict):
                            other_type = other_unit.get("type", "").lower()
                            other_pos = other_unit.get("pos")
                        else:
                            other_type = getattr(other_unit, "unit_type", "").lower()
                            other_pos = getattr(other_unit, "global_position", None)
                        
                        # Check if this other unit also matches the same objective
                        other_matches = False
                        if "sam" in other_type and ("sam" in obj_target_label or "air_defense" in obj_target_label):
                            other_matches = True
                        elif "artillery" in other_type and ("artillery" in obj_target_label or "battery" in obj_target_label):
                            other_matches = True
                        elif any(t in other_type for t in ["convoy", "logistic"]) and ("convoy" in obj_target_label or "logistic" in obj_target_label):
                            other_matches = True
                        elif "bunker" in other_type and ("bunker" in obj_target_label or "defensive" in obj_target_label):
                            other_matches = True
                        elif "factory" in other_type and "factory" in obj_target_label:
                            other_matches = True
                        
                        # If other unit matches same objective, add to grouping positions
                        if other_matches and other_pos and len(other_pos) >= 3:
                            placement = wsm.unit_placements.get(wsm_key, {})
                            if placement.get("position"):
                                other_pos = placement["position"]
                            if other_pos and len(other_pos) >= 3:
                                related_unit_positions.append((other_pos[0], other_pos[2]))
        
        # Combine related unit positions, objective positions, and key point positions
        # PRIORITIZE key point positions (objective locations) - these are the most important
        all_reference_positions = objective_key_point_positions + related_unit_positions + objective_positions
        
        # If we have related units or objective targets, adjust target_area to be near them
        if all_reference_positions and target_area:
            # Find centroid of related units/objectives
            avg_x = sum(p[0] for p in all_reference_positions) / len(all_reference_positions)
            avg_z = sum(p[1] for p in all_reference_positions) / len(all_reference_positions)
            
            # Determine grouping distance based on unit type and whether we have objective key points
            # If we have objective key points, place MUCH closer (5-20km, not 200km)
            if objective_key_point_positions:
                # Units related to specific objectives should be close to the objective
                if "sam" in unit_lower or "aa" in unit_lower or "radar" in unit_lower:
                    # Air defense near objective: 5-15km (defensive perimeter)
                    grouping_dist = 5000 + self.rng.random() * 10000
                elif "artillery" in unit_lower:
                    # Artillery near objective: 10-20km (standoff distance)
                    grouping_dist = 10000 + self.rng.random() * 10000
                elif any(t in unit_lower for t in ["convoy", "logistic", "truck"]):
                    # Convoys near objective: 2-10km (approach routes)
                    grouping_dist = 2000 + self.rng.random() * 8000
                else:
                    # Default for objective-related units: 5-15km
                    grouping_dist = 5000 + self.rng.random() * 10000
            else:
                # No specific objective key point - use tighter grouping for related units
                if "sam" in unit_lower or "aa" in unit_lower or "radar" in unit_lower:
                    # Air defense units: 2-5km grouping (defensive network)
                    grouping_dist = 2000 + self.rng.random() * 3000
                elif any(t in unit_lower for t in ["convoy", "logistic", "truck"]):
                    # Convoys: 500m-2km grouping (tight formation)
                    grouping_dist = 500 + self.rng.random() * 1500
                elif "artillery" in unit_lower:
                    # Artillery: 1-3km grouping (battery formation)
                    grouping_dist = 1000 + self.rng.random() * 2000
                else:
                    # Default: 2-5km grouping
                    grouping_dist = 2000 + self.rng.random() * 3000
            
            angle = self.rng.random() * 2 * math.pi
            offset_x = math.cos(angle) * grouping_dist
            offset_z = math.sin(angle) * grouping_dist
            
            # Update target_area to be near related units/objectives
            target_area = (
                max(0, min(avg_x + offset_x, map_size)),
                target_area[1],
                max(0, min(avg_z + offset_z, map_size))
            )
        
        # Layer 0: Get initial placement from intelligent placement
        intelligent_result = _place_unit_intelligently_fn(
            unit_type_str=unit_type_str,
            unit_role=unit_role,
            target_area=target_area,
            wsm=wsm,
            plan=plan
        )
        
        if not intelligent_result:
            return None
        
        pos, placement_info = intelligent_result
        
        # Mark if this was grouped with related units or objectives
        if all_reference_positions:
            placement_info["grouped_with_related"] = True
            placement_info["related_units_count"] = len(related_unit_positions)
            placement_info["objective_targets_count"] = len(objective_positions)
            if objective_positions:
                placement_info["placed_near_objectives"] = True
        
        # Basic validation
        if not _validate_map_bounds(pos):
            return None
        
        helper = self.terrain_helper
        unit_lower = unit_type_str.lower()
        
        # Determine unit team
        unit_team = "Enemy"
        try:
            from pytol.procedural.unit_templates import UNIT_TEAM_DATABASE
            allowed_teams = UNIT_TEAM_DATABASE.get(unit_type_str, set())
            if "allied" in unit_lower or (unit_lower.startswith('a') and not any(unit_lower.startswith(p) for p in ['asf', 'aew', 'abomber', 'aiucav'])):
                unit_team = "Allied" if "Allied" in allowed_teams else ("Enemy" if "Enemy" in allowed_teams else "Enemy")
            elif "enemy" in unit_lower:
                unit_team = "Enemy"
            elif allowed_teams:
                if any(t in unit_lower for t in ["sam", "aa", "radar", "defense", "patriot", "backstop"]):
                    unit_team = "Allied" if "Allied" in allowed_teams else next(iter(allowed_teams))
                else:
                    unit_team = "Enemy" if "Enemy" in allowed_teams else next(iter(allowed_teams))
        except Exception:
            if "allied" in unit_lower:
                unit_team = "Allied"
            elif "enemy" in unit_lower:
                unit_team = "Enemy"
        
        # Layer 1: Mission Context Validation
        mission_archetype = plan.metadata.get("mission_archetype", "").lower()
        player_role = plan.metadata.get("player_role", "strike").lower()
        
        # For SEAD missions, SAMs should be near objectives
        objective_positions = []
        if player_role == "sead" and ("sam" in unit_lower or "aa" in unit_lower):
            # Check if SAM is reasonably positioned for SEAD (within 30km of any objective)
            try:
                for obj_key, obj_info in wsm.objectives.items():
                    if isinstance(obj_info, dict):
                        # Try to find target unit positions
                        target_label = obj_info.get("target_label", "")
                        target_units = wsm.query_units_by_pattern(target_label)
                        for unit in target_units:
                            if isinstance(unit, dict):
                                pos_data = unit.get("pos", unit.get("position"))
                            else:
                                pos_data = getattr(unit, "global_position", getattr(unit, "pos", None))
                            if pos_data and len(pos_data) >= 2:
                                objective_positions.append((pos_data[0], pos_data[2] if len(pos_data) >= 3 else pos_data[1]))
                
                if objective_positions:
                    from pytol.misc.math_utils import calculate_2d_distance
                    min_dist_to_objective = min(calculate_2d_distance((pos[0], pos[2]), obj_pos) for obj_pos in objective_positions)
                    if min_dist_to_objective > 30000:  # Too far from objectives for SEAD
                        self.logger.debug(f"PCG: SAM too far from objectives for SEAD mission ({min_dist_to_objective:.0f}m)")
                        return None  # Reject - not coherent with SEAD mission
            except Exception:
                pass  # Skip mission validation on error
        
        # Layer 2: Territory Validation
        territory_at_pos = wsm.get_territory_at_position(pos[0], pos[2])
        if territory_at_pos:
            # Check if unit is allowed in this territory type
            unit_allowed = wsm.get_unit_allowed_in_territory(unit_type_str, territory_at_pos)
            if not unit_allowed:
                self.logger.debug(f"PCG: Unit '{unit_type_str}' not allowed in '{territory_at_pos}' territory")
                return None  # Reject - violates territory rules
            
            # Check if unit is in correct team territory
            if territory_at_pos == "friendly" and unit_team == "Enemy":
                # Enemy unit in friendly territory - only acceptable if very close to boundary (neutral zone)
                from pytol.misc.math_utils import calculate_2d_distance
                # Check distance to nearest friendly strategic point
                try:
                    if hasattr(self.terrain_helper.tc, 'bases'):
                        friendly_bases = [b for b in self.terrain_helper.tc.bases[:1]]  # First base is typically friendly
                        if friendly_bases:
                            base_pos = friendly_bases[0].get('position', [0, 0, 0])
                            dist_to_friendly = calculate_2d_distance((pos[0], pos[2]), (base_pos[0], base_pos[2] if len(base_pos) >= 3 else base_pos[1]))
                            if dist_to_friendly < map_size * 0.15:  # Too close to friendly base
                                self.logger.debug(f"PCG: Enemy unit too close to friendly territory ({dist_to_friendly:.0f}m)")
                                return None
                except Exception:
                    pass
            elif territory_at_pos == "enemy" and unit_team == "Allied":
                # Allied unit in enemy territory - might be acceptable for offensive missions
                if mission_archetype not in ["offensive", "strike"]:
                    self.logger.debug(f"PCG: Allied unit in enemy territory for {mission_archetype} mission")
                    return None
        
        # Layer 3: Terrain Validation (using MissionTerrainHelper)
        try:
            # Use MissionTerrainHelper's tactical terrain analysis
            system_type = 'sam' if "sam" in unit_lower or "aa" in unit_lower else 'generic'
            terrain_analysis = helper._analyze_tactical_terrain(pos, system_type)
            
            # Get slope from analysis
            slope_deg = terrain_analysis.get('slope', 0.0)
            
            # Max slope depends on unit type
            max_slope = 30.0  # Default
            if "sam" in unit_lower or "aa" in unit_lower:
                max_slope = 15.0  # SAMs need relatively flat terrain
            elif "artillery" in unit_lower:
                max_slope = 10.0  # Artillery needs very flat terrain
            elif "tank" in unit_lower or "apc" in unit_lower:
                max_slope = 25.0  # Vehicles can handle moderate slopes
            
            if slope_deg > max_slope:
                self.logger.debug(f"PCG: Position too steep for {unit_type_str} (slope: {slope_deg:.1f}°, max: {max_slope}°)")
                return None  # Reject - terrain too steep
            
            # Check terrain type suitability
            terrain_type = terrain_analysis.get('terrain_type', 'unknown')
            if terrain_type == 'water':
                self.logger.debug(f"PCG: Position is in water - unsuitable for {unit_type_str}")
                return None
            
            # Check accessibility for ground units
            if any(t in unit_lower for t in ["tank", "apc", "artillery", "truck"]):
                accessibility = terrain_analysis.get('accessibility', 'unknown')
                if accessibility == 'poor' and "sam" not in unit_lower:
                    # Non-SAM ground units need good accessibility (near roads)
                    # But allow SAMs to be away from roads for defensive positions
                    road_point = helper.get_nearest_road_point(pos[0], pos[2])
                    if road_point and road_point.get('distance', float('inf')) > 2000:
                        self.logger.debug(f"PCG: Ground unit too far from roads ({road_point.get('distance', 0):.0f}m)")
                        return None
            
            # For SAMs, verify LOS to expected targets (if in SEAD mission)
            if "sam" in unit_lower and player_role == "sead":
                try:
                    # Check LOS to nearest objective target
                    if objective_positions:
                        target_pos = objective_positions[0]
                        # Create 3D target position
                        target_y = helper.tc.get_terrain_height(target_pos[0], target_pos[1])
                        target_3d = (target_pos[0], target_y + 100, target_pos[1])  # 100m AGL
                        
                        # Check LOS with radar height offset using MissionTerrainHelper
                        has_los = helper.has_line_of_sight(
                            pos1=(pos[0], pos[1] + 8, pos[2]),  # Radar mast height
                            pos2=target_3d,
                            steps=20
                        )
                        if not has_los:
                            self.logger.debug(f"PCG: SAM at ({pos[0]:.0f}, {pos[2]:.0f}) has no LOS to target")
                            return None  # Reject - no LOS to target
                except Exception:
                    pass  # Skip LOS check on error
        
        except Exception as e:
            self.logger.debug(f"PCG: Terrain validation error: {e}")
            pass  # Skip terrain validation on error
        
        # Layer 4: Unit-to-Unit Validation
        try:
            # Check spacing from existing units (track in class variable)
            if not hasattr(self, '_placed_unit_positions'):
                self._placed_unit_positions = []
            
            existing_positions = self._placed_unit_positions
            min_spacing = helper.get_unit_spacing_requirement(unit_type_str)
            
            spacing_ok = True
            if existing_positions and min_spacing > 0:
                from pytol.misc.math_utils import calculate_3d_distance
                for existing_pos in existing_positions:
                    if existing_pos and len(existing_pos) >= 3:
                        dist = calculate_3d_distance(pos, existing_pos)
                        if dist < min_spacing:
                            spacing_ok = False
                            self.logger.debug(f"PCG: Unit too close to existing unit ({dist:.0f}m < {min_spacing:.0f}m)")
                            break
            
            if not spacing_ok:
                return None  # Reject - insufficient spacing
            
            # Check unit relationships (e.g., SAM sites should not cluster unless in battery)
            if "sam" in unit_lower and existing_positions:
                # Count nearby SAMs (within 5km)
                nearby_sams = 0
                from pytol.misc.math_utils import calculate_2d_distance
                for existing_pos in existing_positions:
                    if existing_pos and len(existing_pos) >= 3:
                        dist_2d = calculate_2d_distance((pos[0], pos[2]), (existing_pos[0], existing_pos[2]))
                        if dist_2d < 5000:  # 5km radius
                            # Check if existing unit is also a SAM
                            # This is simplified - would need to check unit types in wsm
                            nearby_sams += 1
                
                # Too many SAMs clustered (unless specifically forming a battery - not handled here)
                if nearby_sams > 2:
                    self.logger.debug(f"PCG: Too many SAMs clustered at ({pos[0]:.0f}, {pos[2]:.0f})")
                    return None
        
        except Exception:
            pass  # Skip unit-to-unit validation on error
        
        # All layers passed - return coherent placement
        placement_info["coherent_placement"] = True
        placement_info["validation_layers"] = ["mission", "territory", "terrain", "unit_to_unit"]
        return (pos, placement_info)
    
    def _validate_mission_coherence(self, wsm: WorldState, plan: MissionPlan) -> Tuple[List[str], List[str]]:
        """Validate mission coherence: objectives have targets, triggers have valid actions, etc.
        
        This runs after all units and objectives are generated to catch coherence issues.
        
        Returns:
            Tuple of (validation_errors, validation_warnings)
        """
        validation_errors = []
        validation_warnings = []
        
        # 1. Check that objectives have valid targets
        for obj_key, obj_info in wsm.objectives.items():
            if not isinstance(obj_info, dict):
                continue
                
            target_label = obj_info.get("target_label")
            obj_type = obj_info.get("type", "Destroy")
            obj_name = obj_info.get("name", obj_key)
            
            if obj_type == "Destroy" and target_label:
                # Check if we can resolve this target
                # Simple check: count matching units
                matching_units = []
                for unit_key, unit_obj in wsm.units.items():
                    label_lower = target_label.lower()
                    if isinstance(unit_obj, dict):
                        unit_type = unit_obj.get("type", "").lower()
                        team = unit_obj.get("team", "").lower()
                    else:
                        unit_type = getattr(unit_obj, "unit_type", "").lower()
                        team = getattr(unit_obj, "team", "").lower()
                    
                    # Match patterns
                    matched = False
                    if "sam_network" in label_lower:
                        if "sam" in unit_type or "aa" in unit_type:
                            matched = True
                    elif "artillery_battery" in label_lower:
                        if "artillery" in unit_type or "howitzer" in unit_type:
                            matched = True
                    elif "convoy" in label_lower:
                        if "convoy" in unit_type or "logistic" in unit_type:
                            matched = True
                    elif "enemy" in label_lower and "enemy" in team:
                        matched = True
                    
                    if matched:
                        matching_units.append(unit_key)
                
                if not matching_units:
                    validation_warnings.append(f"Objective '{obj_name}' (target_label='{target_label}') has no matching units - may be unresolvable")
                elif len(matching_units) == 1:
                    validation_warnings.append(f"Objective '{obj_name}' only matches 1 unit - consider increasing target count")
        
        # 2. Check that triggers have valid target units
        for trigger_id, trigger_info in wsm.triggers.items():
            if not isinstance(trigger_info, dict):
                continue
                
            target_unit_key = trigger_info.get("target_unit_key")
            trigger_type = trigger_info.get("type", "proximity")
            
            if trigger_type in ("proximity", "unit_destroyed") and target_unit_key:
                if target_unit_key not in wsm.units:
                    validation_errors.append(f"Trigger '{trigger_id}' references non-existent unit '{target_unit_key}'")
            
            reinforcement_key = trigger_info.get("reinforcement_unit_key")
            if reinforcement_key and reinforcement_key not in wsm.units:
                validation_warnings.append(f"Trigger '{trigger_id}' references non-existent reinforcement unit '{reinforcement_key}'")
        
        # 3. Check unit counts match threat level expectations
        threat_level = plan.metadata.get("threat_level", "medium").lower()
        enemy_units = wsm.query_units_by_team("Enemy")
        enemy_unit_count = len(enemy_units)
        
        expected_min = {"low": 2, "medium": 4, "high": 6, "extreme": 8}.get(threat_level, 4)
        if enemy_unit_count < expected_min:
            validation_warnings.append(f"Threat level '{threat_level}' but only {enemy_unit_count} enemy units (expected >= {expected_min})")
        
        # 4. Check that primary objective exists
        if "primary_player_objective" not in wsm.objectives:
            validation_errors.append("Missing primary player objective - mission may be incomplete")
        
        # 5. Check spatial coherence: SAMs near objectives for SEAD missions
        player_role = plan.metadata.get("player_role", "strike").lower()
        if player_role == "sead":
            # Count SAM units using WorldState pattern query helper
            # Get unit keys instead of units (for hashable set operations)
            sam_keys = wsm.get_unit_keys_by_pattern("sam")
            aa_keys = wsm.get_unit_keys_by_pattern("aa")
            # Remove duplicates (units matching both patterns)
            all_sam_aa_keys = list(set(sam_keys + aa_keys))
            sam_count = len(all_sam_aa_keys)
            if sam_count < 2:
                validation_warnings.append(f"SEAD mission but only {sam_count} SAM units found - may be too easy")
        
        # Log validation results
        if validation_errors:
            for error in validation_errors:
                self.logger.error("PCG: Coherence validation ERROR: %s", error)
        
        if validation_warnings:
            for warning in validation_warnings:
                self.logger.warning("PCG: Coherence validation WARNING: %s", warning)
        
        if not validation_errors and not validation_warnings:
            self.logger.info("PCG: Mission coherence validation passed")
        elif not validation_errors:
            self.logger.info("PCG: Mission coherence validation passed with %d warnings", len(validation_warnings))
        
        return validation_errors, validation_warnings

    def realize_plan(self, plan: MissionPlan, wsm: WorldState) -> None:
        """Populate the provided WorldState according to the MissionPlan.

        The function will use existing terrain-aware helpers when available; it
        falls back to simple deterministic placements when they are not.
        
        MVP MODE: Simplified version that focuses on:
        1. Player placement on allied airbase
        2. Single objective from grammar
        3. Player waypoints to objective
        4. Skip enemy units for now
        """
        # Check if we're in MVP mode (simple player-focused mission)
        mvp_mode = plan.metadata.get("mvp_mode", False)
        if mvp_mode:
            return self._realize_plan_mvp(plan, wsm)
        
        # Initialize placed unit positions tracking for coherent placement
        self._placed_unit_positions = []
        
        # Initialize territories if not already defined
        # This allows manual definition before calling realize_plan, or automatic initialization
        if not wsm.territory_zones.get('enemy') and not wsm.territory_zones.get('friendly'):
            try:
                from pytol.procedural.territory_helpers import define_territories_from_mission_plan
                if self.mission is not None and hasattr(self.mission, 'tc'):
                    # Intelligently define territories from mission plan
                    # This uses mission archetype, objectives, and bases
                    define_territories_from_mission_plan(
                        wsm=wsm,
                        mission_plan=plan,
                        terrain_calculator=self.mission.tc,
                        default_radius=30000
                    )
                    self.logger.info("PCG: Auto-defined territories from mission plan")
                else:
                    # Fallback: simple base-based definition
                    from pytol.procedural.territory_helpers import auto_define_territories_from_map
                    if self.mission is not None and hasattr(self.mission, 'tc'):
                        auto_define_territories_from_map(wsm, self.mission.tc, default_radius=30000)
                        self.logger.info("PCG: Auto-defined territories from map bases")
            except Exception as exc:
                self.logger.debug("PCG: Could not auto-define territories: %s", exc)
        
        # Try to place player spawn at a base if available
        player_spawn_placed = False
        try:
            from pytol.resources.base_spawn_points import get_available_bases
            if self.mission is not None:
                bases = get_available_bases(self.mission.tc, prefab_type=None)
                if bases:
                    # Use first available airbase for player spawn
                    base = bases[0]
                    base_pos = base.get('position', (0, 0, 0))
                    wsm.register_asset("player_spawn", {
                        "type": "airbase",
                        "pos": base_pos,
                        "base_index": 0,
                        "category": "hangar",
                        "spawn_index": 0,
                        "notes": f"Player spawn at {base.get('prefab_type', 'unknown')} airbase"
                    })
                    player_spawn_placed = True
                    self.logger.info("PCG: Player spawn set to base 0 hangar")
        except Exception as exc:
            self.logger.debug("PCG: Could not find base for player spawn: %s", exc)
        
        if not player_spawn_placed:
            # Fallback: register default spawn
            wsm.register_asset("player_spawn", {"type": "airfield", "pos": (0, 0), "notes": "player home (no base found)"})

        # Get map size for bounds checking
        map_size = 196608.0  # Default map size
        try:
            if self.terrain_helper and hasattr(self.terrain_helper, 'tc'):
                map_size = getattr(self.terrain_helper.tc, 'total_map_size_meters', 196608.0)
        except Exception:
            pass
        
        # Use mission duration to pick a rough target distance for naive placements
        # Use wider range to avoid wasting map space: 15-75% of map width
        # Note: Leave more margin at top end since we add offsets
        duration = plan.metadata.get("duration_min", 60)
        x_km = min(10 * duration, map_size / 1000.0 * 0.75)  # Max 75% of map width
        x_m = max(int(x_km * 1000), int(map_size * 0.15))  # Min 15% of map width
        x_m = min(x_m, int(map_size * 0.75))  # Max 75% of map width (safety margin - leave room for offsets)

        # Require a terrain helper for realistic generation
        if self.terrain_helper is None:
            raise RuntimeError("PCG requires a MissionTerrainHelper instance. Construct a TerrainCalculator and pass MissionTerrainHelper into PCG.")

        # STEP 1: Define key mission points first (strategic planning layer)
        # This resolves objectives to actual map locations before placing units
        mission_key_points = self._define_mission_key_points(plan, wsm, map_size, x_m)
        self.logger.info(f"PCG: Defined {len(mission_key_points)} key mission points")
        
        # Store key points in WorldState for reference
        wsm.register_asset("mission_key_points", {
            "points": mission_key_points,
            "description": "Strategic mission locations for unit placement"
        })
        
        # STEP 1.5: Place static structures (bunkers, factories, missile silos) at strategic locations
        # These provide destroyable targets and create interesting gameplay loops
        static_structures = self._place_static_structures(mission_key_points, wsm, plan, map_size)
        self.logger.info(f"PCG: Placed {len(static_structures)} static structures")
        
        # STEP 1.6: Place static convoys on roads (if grammar hints at convoy objectives)
        # Convoys are placed between cities or near strategic points, creating optional/secondary objectives
        convoy_data = self._place_static_convoys(mission_key_points, wsm, plan, map_size)
        self.logger.info(f"PCG: Placed {len(convoy_data.get('convoys', {}))} static convoys")
        
        # Track unit groups - map unit types to key points so related units cluster together
        unit_group_assignments = {}  # unit_type -> key_point_id
        units_by_key_point = {}  # key_point_id -> list of unit types that should cluster here

        # Instantiate helpers (will raise if modules missing)
        placer = IntelligentPlacer(self.terrain_helper) if IntelligentPlacer is not None else None
        waypoint_gen = TacticalWaypointGenerator(self.terrain_helper) if TacticalWaypointGenerator is not None else None

        # Walk objectives produced by the grammar and create WSM entries
        for idx, raw_obj in enumerate(plan.objectives):
            if isinstance(raw_obj, PlanObjective):
                obj = raw_obj.to_dict()
            elif hasattr(raw_obj, "to_dict"):
                obj = raw_obj.to_dict()
            elif isinstance(raw_obj, dict):
                obj = raw_obj
            else:
                # Last resort: attempt dataclass conversion
                try:
                    obj = dataclasses.asdict(raw_obj)  # type: ignore[name-defined]
                except Exception:
                    obj = {"type": "note", "description": str(raw_obj), "raw": str(raw_obj)}

            otype = obj.get("type")

            def _attach_action_helper(uobj):
                """Attach a temporary action helper instance with no final uid yet.

                vts_builder will overwrite this with the final target_id when
                the mission is compiled, but having an actions helper in the
                WSM makes it convenient to build EventTarget objects early.
                """
                try:
                    for cls_key, a_cls in UNIT_CLASS_TO_ACTION_CLASS.items():
                        if isinstance(uobj, cls_key):
                            try:
                                uobj.actions = a_cls(target_id=None)
                            except Exception:
                                # ignore action attach failures
                                pass
                            break
                except Exception:
                    pass

            def _place_unit_intelligently(
                unit_type_str: str,
                unit_role: str,
                target_area: Optional[Tuple[float, float, float]],
                wsm: WorldState,
                plan: MissionPlan
            ) -> Optional[Tuple[Tuple[float, float, float], Dict[str, Any]]]:
                """Place unit using MissionTerrainHelper tactical queries.
                
                Returns:
                    Tuple of (position, placement_info) or None if placement failed.
                    placement_info contains: position, rotation, placement_mode, use_smart_placement,
                    align_to_surface, source_query, tactical_role
                """
                if self.terrain_helper is None:
                    return None
                
                helper = self.terrain_helper
                unit_lower = unit_type_str.lower()
                role_lower = unit_role.lower() if unit_role else ""
                
                # Get map size for bounds checking
                map_size = 196608.0  # Default map size
                try:
                    if self.terrain_helper and hasattr(self.terrain_helper, 'tc'):
                        map_size = getattr(self.terrain_helper.tc, 'total_map_size_meters', 196608.0)
                except Exception:
                    pass
                
                # Helper function to validate position is within map bounds
                def _validate_map_bounds(pos):
                    """Check if position is within map bounds (0 to map_size)."""
                    if pos is None or len(pos) < 3:
                        return False
                    x, y, z = pos[0], pos[1], pos[2]
                    return (0 <= x <= map_size and 0 <= z <= map_size)
                
                # Determine unit team early for team-aware placement
                unit_team = "Enemy"  # Default to Enemy
                try:
                    from pytol.procedural.unit_templates import UNIT_TEAM_DATABASE
                    allowed_teams = UNIT_TEAM_DATABASE.get(unit_type_str, set())
                    # Prefer Allied if available and name suggests Allied
                    if "allied" in unit_lower or (unit_lower.startswith('a') and not any(unit_lower.startswith(p) for p in ['asf', 'aew', 'abomber', 'aiucav'])):
                        unit_team = "Allied" if "Allied" in allowed_teams else ("Enemy" if "Enemy" in allowed_teams else "Enemy")
                    elif "enemy" in unit_lower or (unit_lower.startswith('e') and not any(unit_lower.startswith(p) for p in ['esc', 'e-', 'ef-', 'ew'])):
                        unit_team = "Enemy"
                    elif allowed_teams:
                        # For multi-team units, prefer Allied for defensive units, Enemy for offensive
                        if any(t in unit_lower for t in ["sam", "aa", "radar", "defense", "patriot", "backstop"]):
                            unit_team = "Allied" if "Allied" in allowed_teams else next(iter(allowed_teams))
                        else:
                            unit_team = "Enemy" if "Enemy" in allowed_teams else next(iter(allowed_teams))
                except Exception:
                    # Fallback: infer from name
                    if "allied" in unit_lower:
                        unit_team = "Allied"
                    elif "enemy" in unit_lower:
                        unit_team = "Enemy"
                
                # Get spacing requirement for this unit type
                min_spacing = helper.get_unit_spacing_requirement(unit_type_str)
                # Get existing unit positions for spacing checks
                existing_positions = self._placed_unit_positions
                
                # Team-aware target area selection
                # Allied units should be placed near their bases, Enemy units can be more distributed
                if target_area is None:
                    # Find Allied airbases for friendly zone placement
                    allied_base_positions = []
                    try:
                        if hasattr(helper.tc, 'bases') and helper.tc.bases:
                            # Filter for Allied bases (typically first base or bases with Allied naming)
                            for base in helper.tc.bases:
                                prefab_type = base.get('prefab_type', '').lower()
                                # Assume first airbase is Allied (VTOL VR convention)
                                if 'airbase' in prefab_type:
                                    pos = base.get('position', [0, 0, 0])
                                    allied_base_positions.append((pos[0], pos[2]))
                                    # Use first Allied base found
                                    if len(allied_base_positions) == 1:
                                        break
                    except Exception:
                        pass
                    
                    # If Allied unit and we have base positions, place near base
                    if unit_team == "Allied" and allied_base_positions:
                        base_x, base_z = allied_base_positions[0]
                        # Place within 10-30km of base (defensive perimeter)
                        offset_km = 10 + self.rng.random() * 20  # 10-30km
                        angle = self.rng.random() * 2 * math.pi
                        offset_x = math.cos(angle) * offset_km * 1000
                        offset_z = math.sin(angle) * offset_km * 1000
                        x_m = max(int(map_size * 0.15), min(int(base_x + offset_x), int(map_size * 0.85)))
                        z_m = max(int(map_size * 0.15), min(int(base_z + offset_z), int(map_size * 0.85)))
                        target_area = (x_m, 0, z_m)
                    else:
                        # Enemy units or no base found: use strategic distribution
                        # Enemy units avoid Allied territory (left side of map typically)
                        duration = plan.metadata.get("duration_min", 60)
                        x_km = min(10 * duration, map_size / 1000.0 * 0.8)
                        # Enemy units prefer right side (40-90% of map width)
                        if unit_team == "Enemy":
                            x_m = int(map_size * (0.4 + self.rng.random() * 0.5))
                        else:
                            x_m = max(int(x_km * 1000), int(map_size * 0.2))
                            x_m = min(x_m, int(map_size * 0.8))
                        # Use random Z position in middle 60% of map (20-80%) for better distribution
                        z_m = int(map_size * (0.2 + self.rng.random() * 0.6))
                        target_area = (x_m, 0, z_m)
                
                # Validate target_area is within bounds
                if not _validate_map_bounds(target_area):
                    # Clamp target_area to bounds
                    target_area = (
                        max(0, min(target_area[0], map_size)),
                        target_area[1],
                        max(0, min(target_area[2], map_size))
                    )
                
                placement_info = {
                    "placement_mode": "ground",
                    "use_smart_placement": True,
                    "align_to_surface": True,
                    "rotation": (0.0, 0.0, 0.0),
                }
                
                # Get territory constraints if this is an enemy unit
                territory_constraints = {}
                try:
                    # Try to infer team from unit type or role
                    is_enemy = any(kw in unit_lower for kw in ["enemy", "sam", "aa", "artillery", "threat"])
                    if is_enemy:
                        # Get enemy territory constraints
                        territory_constraints = wsm.get_territory_constraints("Enemy", include_excluded=True)
                except Exception:
                    pass
                
                # SAM / Air Defense -> Observation post or elevated position
                if "sam" in unit_lower or "aa" in unit_lower or "air_defense" in unit_lower:
                    # Team-aware placement: Enemy SAMs use peaks for offensive coverage,
                    # Allied SAMs use defensive observation posts (not peaks)
                    try:
                        # First, check terrain type to make smart decisions
                        terrain_type = helper.get_terrain_type(
                            position=(target_area[0], target_area[2]),
                            sample_radius=2000
                        )
                        
                        # For mountainous terrain and ENEMY units ONLY, use highest point
                        # Allied units should NOT be on peaks - they use observation posts for defensive coverage
                        if terrain_type == "Mountainous" and unit_team == "Enemy":
                            try:
                                # Scale search radius appropriately for map size
                                base_search_radius = 5000
                                search_radius = helper.scale_search_radius_by_map_size(base_search_radius)
                                highest = helper.find_highest_point_in_area(
                                    center_x=target_area[0],
                                    center_z=target_area[2],
                                    search_radius=search_radius,
                                    existing_unit_positions=existing_positions,
                                    min_spacing_from_units=min_spacing
                                )
                                if highest and _validate_map_bounds(highest):
                                    # Validate against territory constraints
                                    if territory_constraints.get('position_validator'):
                                        if territory_constraints['position_validator']((highest[0], highest[2])):
                                            placement_info.update({
                                                "position": highest,
                                                "source_query": "find_highest_point_in_area",
                                                "tactical_role": "air_defense_peak",
                                            })
                                            return (highest, placement_info)
                                    elif not territory_constraints.get('constraint_area'):
                                        # Only use if no constraints, or validate separately
                                        placement_info.update({
                                            "position": highest,
                                            "source_query": "find_highest_point_in_area",
                                            "tactical_role": "air_defense_peak",
                                        })
                                        return (highest, placement_info)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    
                    try:
                        # Try observation post first (good for radar coverage)
                        # Scale max_dist appropriately for map size
                        base_max_dist = 15000
                        max_dist = helper.scale_search_radius_by_map_size(base_max_dist)
                        # Also scale min_dist proportionally
                        base_min_dist = 2000
                        min_dist = helper.scale_search_radius_by_map_size(base_min_dist)
                        op = helper.find_observation_post(
                            target_area=target_area,
                            min_dist=min_dist,
                            max_dist=max_dist,
                            num_candidates=15,
                            constraint_area=territory_constraints.get('constraint_area'),
                            excluded_areas=territory_constraints.get('excluded_areas'),
                            position_validator=territory_constraints.get('position_validator'),
                            existing_unit_positions=existing_positions,
                            min_spacing_from_units=min_spacing
                        )
                        if op and _validate_map_bounds(op):
                            placement_info.update({
                                "position": op,
                                "source_query": "find_observation_post",
                                "tactical_role": "air_defense",
                            })
                            return (op, placement_info)
                    except Exception:
                        pass
                    
                    # Fallback: try defensive position (note: find_defensive_position doesn't support constraints yet)
                    try:
                        # Scale search radius appropriately for map size
                        base_search_radius = 10000
                        search_radius = helper.scale_search_radius_by_map_size(base_search_radius)
                        defensive = helper.find_defensive_position(
                            center_pos=target_area,
                            search_radius=search_radius,
                            system_type='sam',
                            constraint_area=territory_constraints.get('constraint_area'),
                            excluded_areas=territory_constraints.get('excluded_areas'),
                            position_validator=territory_constraints.get('position_validator')
                        )
                        # Check if defensive position is in allowed territory and within map bounds
                        if defensive and defensive.get('position'):
                            pos = defensive['position']
                            # First check map bounds
                            if not _validate_map_bounds(pos):
                                defensive = None
                            # Check spacing from existing units
                            elif existing_positions and not helper.check_spacing_from_existing_units(pos, existing_positions, min_spacing):
                                defensive = None
                            # Then validate against territory constraints
                            elif territory_constraints.get('position_validator'):
                                if not territory_constraints['position_validator']((pos[0], pos[2])):
                                    defensive = None  # Reject position outside allowed territory
                            elif territory_constraints.get('constraint_area'):
                                # Simple validation for single constraint area
                                from pytol.misc.math_utils import is_position_in_circle
                                ca = territory_constraints['constraint_area']
                                if ca.get('type') == 'circle':
                                    if not is_position_in_circle((pos[0], pos[2]), ca['center'], ca['radius']):
                                        defensive = None
                        if defensive and defensive.get('position'):
                            pos = defensive['position']
                            placement_info.update({
                                "position": pos,
                                "source_query": "find_defensive_position",
                                "tactical_role": "air_defense",
                            })
                            return (pos, placement_info)
                    except Exception:
                        pass
                
                # Artillery -> Hidden artillery position (use terrain type classification)
                elif "artillery" in unit_lower or "mlrs" in unit_lower or "howitzer" in unit_lower:
                    # Use terrain awareness: prefer valleys/low points for concealment
                    try:
                        terrain_type = helper.get_terrain_type(
                            position=(target_area[0], target_area[2]),
                            sample_radius=2000
                        )
                        
                        # For varied terrain, use lowest point (valleys) for better concealment
                        if terrain_type in ["Mountainous", "Rolling Hills"]:
                            try:
                                # Scale search radius appropriately for map size
                                base_search_radius = 5000
                                search_radius = helper.scale_search_radius_by_map_size(base_search_radius)
                                lowest = helper.find_lowest_point_in_area(
                                    center_x=target_area[0],
                                    center_z=target_area[2],
                                    search_radius=search_radius,
                                    existing_unit_positions=existing_positions,
                                    min_spacing_from_units=min_spacing
                                )
                                if lowest and _validate_map_bounds(lowest):
                                    # Validate against territory constraints
                                    if territory_constraints.get('position_validator'):
                                        if territory_constraints['position_validator']((lowest[0], lowest[2])):
                                            placement_info.update({
                                                "position": lowest,
                                                "source_query": "find_lowest_point_in_area",
                                                "tactical_role": "indirect_fire_valley",
                                            })
                                            return (lowest, placement_info)
                                    elif not territory_constraints.get('constraint_area'):
                                        placement_info.update({
                                            "position": lowest,
                                            "source_query": "find_lowest_point_in_area",
                                            "tactical_role": "indirect_fire_valley",
                                        })
                                        return (lowest, placement_info)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    
                    try:
                        # Scale search radius appropriately for map size
                        base_search_radius = 8000
                        search_radius = helper.scale_search_radius_by_map_size(base_search_radius)
                        # Scale standoff distance too
                        base_standoff = 2000
                        standoff_dist = helper.scale_search_radius_by_map_size(base_standoff)
                        arty_pos = helper.find_artillery_position(
                            target_area=target_area,
                            search_radius=search_radius,
                            standoff_dist=standoff_dist,
                            constraint_area=territory_constraints.get('constraint_area'),
                            excluded_areas=territory_constraints.get('excluded_areas'),
                            position_validator=territory_constraints.get('position_validator'),
                            existing_unit_positions=existing_positions,
                            min_spacing_from_units=min_spacing
                        )
                        if arty_pos and _validate_map_bounds(arty_pos):
                            placement_info.update({
                                "position": arty_pos,
                                "source_query": "find_artillery_position",
                                "tactical_role": "indirect_fire",
                            })
                            return (arty_pos, placement_info)
                    except Exception:
                        pass
                
                # Ground vehicles / Tanks -> Roads (prioritized) or flat areas
                elif any(t in unit_lower for t in ["tank", "apc", "vehicle", "truck", "infantry"]):
                    # For ALL ground vehicles, try to find nearest road first (within 2km)
                    # This makes placement more logical - vehicles on roads
                    try:
                        pos_2d = (target_area[0], target_area[2])
                        road_info = helper.get_nearest_road_point(pos_2d[0], pos_2d[1], max_distance=2000.0)
                        if road_info and road_info.get('position'):
                            road_pos = road_info['position']
                            road_distance = road_info.get('distance', 0.0)
                            
                            # For convoy/logistics units, always prefer roads
                            # For other ground units, prefer roads if within 1km
                            is_convoy = any(t in unit_lower for t in ["convoy", "logistic", "truck", "transport"])
                            if is_convoy or road_distance <= 1000.0:
                                # Verify position is actually on road
                                if helper.tc.is_on_road(road_pos[0], road_pos[2], tolerance=10.0):
                                    # Calculate heading along road if possible
                                    from pytol.misc.math_utils import calculate_bearing
                                    # Try to get road direction from road_info if available
                                    heading = 0.0
                                    if 'heading' in road_info:
                                        heading = road_info['heading']
                                    elif target_area and len(target_area) >= 3:
                                        heading = calculate_bearing((road_pos[0], road_pos[2]), (target_area[0], target_area[2]), degrees=True)
                                    
                                    # Use smart placement to ensure proper terrain alignment
                                    try:
                                        smart = helper.tc.get_smart_placement(road_pos[0], road_pos[2], yaw_degrees=heading)
                                        if smart and smart.get('position'):
                                            final_pos = smart['position']
                                            final_rot = smart.get('rotation', (0.0, heading, 0.0))
                                        else:
                                            final_pos = road_pos
                                            final_rot = (0.0, heading, 0.0)
                                    except Exception:
                                        final_pos = road_pos
                                        final_rot = (0.0, heading, 0.0)
                                    
                                    placement_info.update({
                                        "position": final_pos,
                                        "rotation": final_rot,
                                        "source_query": "get_nearest_road_point",
                                        "tactical_role": "road_vehicle" if not is_convoy else "convoy_route",
                                        "placement_type": "road"  # Store placement type for debugging
                                    })
                                    return (final_pos, placement_info)
                    except Exception:
                        pass
                    
                    # For defensive units (SAMs, artillery), allow off-road but still prefer road proximity
                    # This is already handled above - if road is found within 1km, use it
                    
                    # For urban objectives: check if in city area and use building roofs
                    try:
                        city_density = helper.tc.get_city_density(target_area[0], target_area[2])
                        if city_density > 0.1:  # Urban area
                            # Use smart placement which will place on building roofs if appropriate
                            try:
                                smart = helper.tc.get_smart_placement(target_area[0], target_area[2], yaw_degrees=0)
                                if smart and smart.get('position') and smart.get('type') in ['city_roof', 'static_roof']:
                                    placement_info.update({
                                        "position": smart['position'],
                                        "rotation": smart.get('rotation', (0.0, 0.0, 0.0)),
                                        "source_query": "get_smart_placement_urban",
                                        "tactical_role": "urban_unit",
                                        "placement_type": smart.get('type'),
                                        "snapped_to_building": smart.get('snapped_to_building')
                                    })
                                    return (smart['position'], placement_info)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    
                    # For stealth/special forces units, use hidden positions
                    if any(t in unit_lower for t in ["stealth", "special", "recon", "csar"]):
                        try:
                            # Use hidden position helper - assumes no observers for now
                            # In future, could use known threat positions as observers
                            # Scale search radius appropriately
                            base_search_radius = 3000
                            search_radius = helper.scale_search_radius_by_map_size(base_search_radius)
                            hidden_pos = helper.find_hidden_position(
                                observer_pos=(0, 1000, 0),  # Generic high observer point
                                target_area_center=(target_area[0], target_area[2]),
                                search_radius=search_radius,
                                constraint_area=territory_constraints.get('constraint_area'),
                                excluded_areas=territory_constraints.get('excluded_areas'),
                                position_validator=territory_constraints.get('position_validator'),
                                existing_unit_positions=existing_positions,
                                min_spacing_from_units=min_spacing
                            )
                            if hidden_pos:
                                placement_info.update({
                                    "position": hidden_pos,
                                    "source_query": "find_hidden_position",
                                    "tactical_role": "stealth_unit",
                                })
                                return (hidden_pos, placement_info)
                        except Exception:
                            pass
                    
                    # NOTE: get_smart_placement is for SNAPPING positions to terrain/surfaces,
                    # not for finding positions. We need to find diverse positions first using
                    # helper methods, then optionally snap them. Don't use target_area directly
                    # as it will place all units at the same location!
                    
                    # Fallback: find open area, then use smart placement for proper terrain alignment
                    try:
                        # Scale search radius appropriately
                        base_search_radius = 5000
                        search_radius = helper.scale_search_radius_by_map_size(base_search_radius)
                        open_area = helper.find_open_area(
                            center_pos=(target_area[0], target_area[2]),
                            search_radius=search_radius,
                            min_clear_radius=50,
                            constraint_area=territory_constraints.get('constraint_area'),
                            excluded_areas=territory_constraints.get('excluded_areas'),
                            position_validator=territory_constraints.get('position_validator'),
                            existing_unit_positions=existing_positions,
                            min_spacing_from_units=min_spacing
                        )
                        if open_area:
                            # Use smart placement to ensure proper terrain/road/building alignment
                            try:
                                smart = helper.tc.get_smart_placement(open_area[0], open_area[2], yaw_degrees=0)
                                if smart and smart.get('position'):
                                    final_pos = smart['position']
                                    placement_type = smart.get('type', 'terrain')
                                else:
                                    final_pos = open_area
                                    placement_type = 'terrain'
                            except Exception:
                                final_pos = open_area
                                placement_type = 'terrain'
                            
                            placement_info.update({
                                "position": final_pos,
                                "source_query": "find_open_area+get_smart_placement",
                                "tactical_role": "ground_unit",
                                "placement_type": placement_type
                            })
                            return (final_pos, placement_info)
                    except Exception:
                        pass
                
                # Ships -> Sea level placement
                elif any(t in unit_lower for t in ["ship", "carrier", "destroyer", "cruiser", "frigate"]):
                    try:
                        # Ships at sea level
                        pos = (target_area[0], 0.0, target_area[2])
                        placement_info.update({
                            "position": pos,
                            "placement_mode": "sea",
                            "use_smart_placement": False,
                            "align_to_surface": False,
                            "source_query": "sea_level",
                            "tactical_role": "naval",
                        })
                        return (pos, placement_info)
                    except Exception:
                        pass
                
                # Aircraft (parked or cold start) -> Base spawn points or flat landing zones
                elif any(t in unit_lower for t in ["ef-", "asf", "aircraft", "fighter", "bomber", "helicopter"]):
                    # Check if aircraft should start cold (on ground, taking off)
                    # Conditions: mission context indicates cold start, unit role suggests ground start, or grammar hints
                    should_start_cold = False
                    
                    # Check mission context for cold start indicators
                    mission_archetype = plan.metadata.get("archetype", "").lower()
                    world_liveliness = plan.metadata.get("world_liveliness", "").lower()
                    
                    # Cold start indicators:
                    # - Parallel sorties / background activity (world_liveliness)
                    # - Unit role suggests ground start (patrol_from_base, escort_from_base)
                    # - Grammar/plan metadata hints at ground start
                    if any(hint in role_lower for hint in ["patrol_from_base", "escort_from_base", "cold_start", "ground_start"]):
                        should_start_cold = True
                    elif world_liveliness in ["high", "very_high"] and "parallel" in str(plan.metadata.get("background_tasking", "")).lower():
                        # High liveliness with parallel sorties suggests cold starts
                        should_start_cold = True
                    elif any(hint in str(plan.metadata.get("background_tasking", "")).lower() for hint in ["cold", "ground", "takeoff"]):
                        should_start_cold = True
                    
                    # If should start cold, try base spawn placement
                    if should_start_cold:
                        base_spawn_result = self._place_aircraft_at_base(
                            unit_type_str=unit_type_str,
                            unit_team=unit_team,
                            target_area=target_area,
                            wsm=wsm
                        )
                        if base_spawn_result:
                            pos, base_spawn_info = base_spawn_result
                            placement_info.update({
                                "position": pos,
                                "placement_mode": "ground",
                                "source_query": "base_spawn",
                                "tactical_role": "cold_start_aircraft",
                                "base_spawn": base_spawn_info
                            })
                            return (pos, placement_info)
                    
                    # For parked aircraft (not cold start), find flat landing zone
                    try:
                        flat_zones = helper.find_flat_landing_zones(
                            center_x=target_area[0],
                            center_z=target_area[2],
                            search_radius=3000,
                            min_area_radius=100,
                            max_slope_degrees=5.0
                        )
                        if flat_zones:
                            # Pick first flat zone
                            flat_area = flat_zones[0]
                            placement_info.update({
                                "position": flat_area,
                                "placement_mode": "ground",
                                "source_query": "find_flat_landing_zones",
                                "tactical_role": "parked_aircraft",
                            })
                            return (flat_area, placement_info)
                    except Exception:
                        pass
                    
                    # Fallback: find open area
                    try:
                        open_area = helper.find_open_area(
                            center_pos=(target_area[0], target_area[2]),
                            search_radius=3000,
                            min_clear_radius=100
                        )
                        if open_area:
                            placement_info.update({
                                "position": open_area,
                                "placement_mode": "ground",
                                "source_query": "find_open_area",
                                "tactical_role": "parked_aircraft",
                            })
                            return (open_area, placement_info)
                    except Exception:
                        pass
                
                # Default: use smart placement (for ground units, this ensures proper terrain/road/building placement)
                try:
                    pos_2d = (target_area[0], target_area[2])
                    smart = helper.tc.get_smart_placement(pos_2d[0], pos_2d[1], yaw_degrees=0)
                    if smart and smart.get('position'):
                        # Store placement type from smart placement result
                        placement_type = smart.get('type', 'terrain')  # 'terrain', 'road', 'city_roof', 'static_roof'
                        placement_info.update({
                            "position": smart['position'],
                            "rotation": smart.get('rotation', (0.0, 0.0, 0.0)),
                            "source_query": "get_smart_placement",
                            "tactical_role": "generic",
                            "placement_type": placement_type  # Store placement type for debugging
                        })
                        return (smart['position'], placement_info)
                except Exception:
                    pass
                
                return None

            def _place_aircraft_at_base(
                unit_type_str: str,
                unit_team: str,
                target_area: Optional[Tuple[float, float, float]],
                wsm: WorldState
            ) -> Optional[Tuple[Tuple[float, float, float], Dict[str, Any]]]:
                """Place aircraft at base spawn point for cold start.
                
                Args:
                    unit_type_str: Unit type string
                    unit_team: Unit team ("Allied" or "Enemy")
                    target_area: Target area for placement (optional)
                    wsm: WorldState instance
                
                Returns:
                    Tuple of (position, base_spawn_info) or None if placement failed.
                    base_spawn_info contains: base_index, category, spawn_index
                """
                try:
                    from pytol.resources.base_spawn_points import get_available_bases, select_spawn_point
                    
                    if self.mission is None or not hasattr(self.mission, 'tc'):
                        return None
                    
                    # Get available bases
                    bases = get_available_bases(self.mission.tc, prefab_type=None)
                    if not bases:
                        return None
                    
                    # Select appropriate base based on team
                    # Allied units use first base, Enemy units use later bases
                    selected_base = None
                    if unit_team == "Allied":
                        # Use first airbase (typically Allied)
                        for base in bases:
                            prefab_type = base.get('prefab_type', '').lower()
                            if 'airbase' in prefab_type:
                                selected_base = base
                                break
                    else:
                        # Enemy units: use second or later airbase
                        enemy_bases = [b for b in bases if 'airbase' in b.get('prefab_type', '').lower()]
                        if len(enemy_bases) > 1:
                            selected_base = enemy_bases[1]  # Second airbase
                        elif enemy_bases:
                            selected_base = enemy_bases[0]  # Fallback to first
                    
                    if not selected_base:
                        return None
                    
                    # Determine spawn category based on aircraft type
                    unit_lower = unit_type_str.lower()
                    category = 'hangar'  # Default
                    
                    if 'helicopter' in unit_lower or 'helo' in unit_lower:
                        category = 'helipad'
                    elif any(t in unit_lower for t in ['bomber', 'bomb', 'heavy']):
                        category = 'bigplane'  # Large aircraft
                    elif any(t in unit_lower for t in ['ef-', 'asf', 'fighter']):
                        category = 'hangar'  # Fighters
                    
                    # Select spawn point
                    try:
                        pos, yaw = select_spawn_point(
                            selected_base,
                            category=category,
                            index=-1,  # Random spawn in category
                            fallback_to_center=True
                        )
                        
                        # Find base index
                        base_index = bases.index(selected_base)
                        
                        # Store base spawn info
                        base_spawn_info = {
                            "base_index": base_index,
                            "category": category,
                            "spawn_index": -1  # Random was used
                        }
                        
                        return (pos, base_spawn_info)
                    except Exception as exc:
                        self.logger.debug("PCG: Failed to select spawn point: %s", exc)
                        return None
                        
                except Exception as exc:
                    self.logger.debug("PCG: Failed to place aircraft at base: %s", exc)
                    return None

            def _materialize_unit(unit_type_str, position, name=None):
                """Try to create a Unit dataclass for the given type+pos.

                Returns the Unit instance or raises if creation failed.
                """
                # Resolve abstract planner terminals to concrete unit IDs first
                try:
                    resolved = UnitLibrary.resolve_abstract(unit_type_str)
                    if resolved:
                        self.logger.debug("PCG: resolved abstract token '%s' -> '%s'", unit_type_str, resolved)
                        unit_type_str = resolved
                except Exception:
                    pass

                # Try to find a UnitTemplate matching this unit_type
                tpl = None
                try:
                    for lst_name in ('ENEMY_VEHICLES', 'ENEMY_AIR', 'ENEMY_SAMS', 'ENEMY_INFANTRY', 'ALLIED_VEHICLES'):
                        for t in getattr(UnitLibrary, lst_name):
                            if t.unit_type == unit_type_str:
                                tpl = t
                                break
                        if tpl:
                            break
                except Exception:
                    tpl = None

                if tpl is not None:
                    try:
                        unit_obj = UnitLibrary.template_to_unit_object(tpl, self.rng, position, name or tpl.name)
                        _attach_action_helper(unit_obj)
                        return unit_obj
                    except Exception as e:
                        # Log and record diagnostic; let callers fallback to alternate behaviors
                        msg = f"template materialization failed for '{tpl.unit_type}' (token='{unit_type_str}') : {e}"
                        self.logger.warning("PCG: %s", msg)
                        try:
                            self.materialization_diagnostics.append({
                                'token': unit_type_str,
                                'template': tpl.unit_type,
                                'pos': position,
                                'reason': 'template_materialization_failed',
                                'exception': str(e),
                            })
                        except Exception:
                            pass
                        # propagate error so caller can decide fallback
                        raise

                # Fallback: determine team from authoritative UNIT_TEAM_DATABASE
                try:
                    allowed = UNIT_TEAM_DATABASE.get(unit_type_str)
                    if allowed:
                        # Prefer Enemy if allowed, else pick arbitrary allowed team
                        guessed_team = 'Enemy' if 'Enemy' in allowed else next(iter(allowed))
                    else:
                        # Unknown unit id (mods/new content): fall back to 'Allied'
                        guessed_team = 'Allied'
                except Exception:
                    guessed_team = 'Allied'

                # Record that we are falling back to create_unit for this token
                try:
                    self.logger.info("PCG: falling back to create_unit for '%s' (guessed_team=%s)", unit_type_str, guessed_team)
                    self.materialization_diagnostics.append({
                        'token': unit_type_str,
                        'pos': position,
                        'reason': 'fallback_to_create_unit',
                        'guessed_team': guessed_team,
                    })
                except Exception:
                    pass

                try:
                    gp = [float(position[0]), float(position[1]), float(position[2])]
                except Exception:
                    # ensure 3D position
                    try:
                        gp = [float(position[0]), 0.0, float(position[1])]
                    except Exception:
                        gp = [0.0, 0.0, 0.0]

                rot = [0.0, 0.0, 0.0]
                try:
                    unit_obj = create_unit(unit_type_str, name or unit_type_str, guessed_team, gp, rot)
                    if unit_obj is None:
                        raise RuntimeError(f"create_unit returned None for '{unit_type_str}'")
                    _attach_action_helper(unit_obj)
                    return unit_obj
                except Exception as e:
                    # Log and record diagnostic
                    self.logger.error("PCG: create_unit failed for '%s' (team=%s): %s", unit_type_str, guessed_team, e)
                    try:
                        self.materialization_diagnostics.append({
                            'token': unit_type_str,
                            'pos': position,
                            'reason': 'create_unit_failed',
                            'guessed_team': guessed_team,
                            'exception': str(e),
                        })
                    except Exception:
                        pass
                    # propagate so callers can fallback to dict-based registration
                    raise

            if otype == "ai_task":
                # Process AI support tasks (escort, AWACS, etc.)
                action = obj.get("action", "").upper()
                target = obj.get("target", "")
                
                # Register AI task for later processing
                wsm.register_asset(f"ai_task_{idx}", {
                    "action": action,
                    "target": target,
                    "description": obj.get("description", f"AI Task: {action} -> {target}"),
                    "type": "ai_task"
                })
                
                self.logger.info(f"PCG: Registered AI task: {action} -> {target}")
                continue
            
            if otype == "player_task":
                # Ensure player spawn exists and register a task note
                wsm.register_asset("player_task", {"role": obj.get("role"), "target": obj.get("target"), "desc": obj.get("description")})
                
                # Register primary objective metadata based on player role
                role = obj.get("role", "strike")
                target_label = obj.get("target", "enemy_unit")
                
                # Map role to objective type
                objective_type = "Destroy"  # Default
                objective_name = f"Complete {role.title()} Mission"
                
                if role == "strike" or role == "sead":
                    objective_type = "Destroy"
                    objective_name = f"Destroy {target_label.replace('_', ' ').title()}"
                elif role == "cap":
                    objective_type = "Destroy"  # Destroy enemy aircraft
                    objective_name = "Establish Air Superiority"
                elif role == "cas":
                    objective_type = "Destroy"
                    objective_name = "Provide Close Air Support"
                elif role == "recon":
                    objective_type = "Fly_To"  # Fly to recon zone (VTOL VR uses Fly_To, not FlyTo)
                    objective_name = "Reconnaissance Mission"
                
                # Store objective metadata - will be converted to Objective object by compiler
                # after units are placed and we know actual unit IDs
                wsm.register_objective("primary_player_objective", {
                    "type": objective_type,
                    "name": objective_name,
                    "role": role,
                    "target_label": target_label,  # Abstract label, will resolve to unit IDs later
                    "required": True,
                    "completion_reward": 100,
                    "description": obj.get("description", objective_name),
                })

            elif otype == "spawn":
                target = obj.get("target") or "enemy_unit"
                
                # Use mission-type unit matching for better unit selection
                threat_level = plan.metadata.get("threat_level", "medium")
                player_role = plan.metadata.get("player_role", "strike")
                
                # If target is generic, use mission-type matching to select specific units
                if target in ("enemy_unit", "enemy", None) or (isinstance(target, str) and target.endswith("_unit")):
                    # Use mission type to select appropriate units
                    selected_unit_types = self._select_units_for_mission_type(
                        mission_type=player_role,
                        threat_level=threat_level,
                        rng=self.rng
                    )
                    if selected_unit_types:
                        # For spawn objectives, we might spawn multiple units
                        # For now, pick one representative unit
                        target = self.rng.choice(selected_unit_types)
                        self.logger.info("PCG: Selected unit type '%s' for %s mission (threat: %s)", target, player_role, threat_level)
                
                # STEP 2: Select appropriate mission key point for this unit
                # Use grouping logic: group units by category (SAMs together, ground units together, etc.)
                target_lower = target.lower()
                key_point_id = None
                
                # Determine unit category for clustering
                unit_category = self._get_unit_category(target_lower, player_role)
                
                # Check if we've already assigned a key point for this unit category (for clustering)
                if unit_category in unit_group_assignments:
                    key_point_id = unit_group_assignments[unit_category]
                    self.logger.debug(f"PCG: Reusing key point '{key_point_id}' for unit category '{unit_category}' (clustering {target})")
                else:
                    # Find best key point for this unit category
                    key_point_id = self._assign_key_point_for_unit_type(
                        unit_type=target,
                        unit_role=player_role,
                        mission_key_points=mission_key_points,
                        units_by_key_point=units_by_key_point,
                        rng=self.rng
                    )
                    if key_point_id:
                        unit_group_assignments[unit_category] = key_point_id
                        if key_point_id not in units_by_key_point:
                            units_by_key_point[key_point_id] = []
                        units_by_key_point[key_point_id].append(target)
                
                # Get target area from assigned key point
                if key_point_id and key_point_id in mission_key_points:
                    key_point = mission_key_points[key_point_id]
                    # Place unit near key point, accounting for already-placed units at this point
                    target_area = self._get_placement_near_key_point(
                        key_point=key_point,
                        unit_type=target,
                        existing_units_at_point=len(units_by_key_point.get(key_point_id, [])) - 1,
                        map_size=map_size,
                        rng=self.rng
                    )
                else:
                    # Fallback: use original selection logic
                    target_area = self._select_key_point_for_unit(
                        unit_type=target,
                        unit_role=player_role,
                        mission_key_points=mission_key_points,
                        map_size=map_size,
                        wsm=wsm,
                        rng=self.rng
                    )
                
                # Try coherent placement with retry logic (progressive fallback)
                placement_result = self._place_unit_with_retries(
                    unit_type_str=target,
                    unit_role=player_role,
                    target_area=target_area,
                    mission_key_points=mission_key_points,
                    units_by_key_point=units_by_key_point,
                    key_point_id=key_point_id,
                    wsm=wsm,
                    plan=plan,
                    map_size=map_size,
                    _place_unit_intelligently_fn=_place_unit_intelligently,
                    _coherent_unit_placement_fn=self._coherent_unit_placement,
                    rng=self.rng
                )
                
                if placement_result:
                    pos, placement_info = placement_result
                    # Update position in placement_info if needed
                    placement_info["position"] = pos
                    # Try to materialize unit at coherent position
                    try:
                        unit_obj = _materialize_unit(target, pos, name=target)
                        # Update unit position to match coherent placement
                        if hasattr(unit_obj, 'global_position'):
                            unit_obj.global_position = list(pos) if isinstance(pos, (list, tuple)) else [pos[0], pos[1], pos[2]]
                        wsm.register_unit(f"spawn_{idx+1}", unit_obj, placement_info=placement_info)
                        # Track placed position for spacing validation
                        if not hasattr(self, '_placed_unit_positions'):
                            self._placed_unit_positions = []
                        self._placed_unit_positions.append(pos)
                        
                        retry_info = placement_info.get("retry_attempts", "")
                        strategy = placement_info.get("placement_strategy", "unknown")
                        coherent = placement_info.get("coherent_placement", False)
                        status = "coherently" if coherent else "with fallback"
                        retry_msg = f" (attempt {retry_info}, strategy: {strategy})" if retry_info else ""
                        self.logger.info("PCG: Placed '%s' %s using %s at (%.0f, %.0f, %.0f)%s", 
                                       target, status, placement_info.get("source_query"), pos[0], pos[1], pos[2], retry_msg)
                        continue
                    except Exception as exc:
                        self.logger.debug("PCG: Placement materialization failed for '%s', falling back: %s", target, exc)
                        # Fall through to other placement methods
                        pass

                # If we have a placer, try to find a tactical zone and place there
                if placer is not None:
                    try:
                        # Use mission key point as center instead of random position
                        if target_area and len(target_area) >= 3:
                            center = target_area
                        else:
                            # Fallback to random if no key point
                            center_z = int(map_size * (0.2 + self.rng.random() * 0.6))
                            center = (x_m, 0, center_z)
                        zones = placer.find_placement_zones(center=center, radius=800.0, num_zones=1, rng=self.rng, prefer_defensive=("airbase" in target))
                        placements = placer.cluster_units([target], zones, self.rng) if zones else []
                        if placements:
                            utype, pos = placements[0]
                            # Try to find a UnitTemplate matching this unit type
                            tpl = None
                            try:
                                for lst_name in ('ENEMY_VEHICLES', 'ENEMY_AIR', 'ENEMY_SAMS', 'ENEMY_INFANTRY', 'ALLIED_VEHICLES'):
                                    for t in getattr(UnitLibrary, lst_name):
                                        if t.unit_type == utype:
                                            tpl = t
                                            break
                                    if tpl:
                                        break
                            except Exception:
                                tpl = None

                            if tpl is not None:
                                try:
                                    unit_obj = UnitLibrary.template_to_unit_object(tpl, self.rng, pos, tpl.name)
                                    _attach_action_helper(unit_obj)
                                    # Store placement info if available
                                    placement_info = {
                                        "position": pos,
                                        "placement_mode": "ground",
                                        "use_smart_placement": True,
                                        "source_query": "intelligent_placer",
                                    }
                                    wsm.register_unit(f"spawn_{idx+1}", unit_obj, placement_info=placement_info)
                                    continue
                                except Exception:
                                    # fall through to register raw type
                                    pass

                            # Try to materialize canonical Unit dataclass
                            try:
                                unit_obj = _materialize_unit(utype, pos, name=utype)
                                placement_info = {
                                    "position": pos,
                                    "placement_mode": "ground",
                                    "use_smart_placement": True,
                                    "source_query": "placer_cluster",
                                }
                                wsm.register_unit(f"spawn_{idx+1}", unit_obj, placement_info=placement_info)
                                continue
                            except Exception:
                                wsm.register_unit(f"spawn_{idx+1}", {"type": utype, "pos": pos, "description": obj.get("description")})
                                continue
                            continue
                    except Exception:
                        pass

                # Fallback naive placement
                # If the target is a generic token like 'enemy' or 'enemy_unit',
                # choose a set from UnitLibrary based on mission hints when possible.
                chosen_type = target
                try:
                    role_hint = plan.metadata.get('player_role') if isinstance(plan.metadata, dict) else None
                    threat = plan.metadata.get('threat_level') if isinstance(plan.metadata, dict) else None
                    difficulty = {'low':'easy','medium':'normal','high':'hard','extreme':'hard'}.get(threat,'normal')
                    mission_type = role_hint or 'strike'
                    if 'enemy' in str(target).lower() or str(target).lower().endswith('_unit'):
                        # pick an enemy unit set appropriate for mission_type
                        # Pass threat_level to get better unit selection
                        templates = UnitLibrary.pick_enemy_set(mission_type, difficulty, self.rng, threat_level=threat)
                        if templates:
                            tpl = self.rng.choice(templates)
                            chosen_type = tpl.unit_type
                            # Use the UnitLibrary helper to materialize common fields
                            try:
                                # Generate proper 3D position with random Z distribution
                                spawn_x = min(x_m + 1000 * (idx + 1), int(map_size * 0.75))
                                spawn_z_variant = int(map_size * (0.2 + self.rng.random() * 0.6))
                                pos = (spawn_x, 0, spawn_z_variant)
                                unit_obj = UnitLibrary.template_to_unit_object(tpl, self.rng, pos, tpl.name)
                                _attach_action_helper(unit_obj)
                                wsm.register_unit(f"spawn_{idx+1}", unit_obj)
                                continue
                            except Exception:
                                # If materialization fails, fall back to string type below
                                chosen_type = tpl.unit_type
                except Exception:
                    chosen_type = target

                # Use map-bounded position for dict-based units with better distribution
                # Map origin is bottom-left (0,0), use wider range: 15-75% of map
                # Calculate spawn X with offset but ensure it doesn't exceed bounds
                spawn_x_offset = 1000 * (idx + 1)
                spawn_x = min(x_m + spawn_x_offset, int(map_size * 0.75))  # Max 75% of map
                spawn_x = max(int(map_size * 0.15), spawn_x)  # Ensure minimum 15% from edge
                # Distribute Z positions across middle 60% of map (20-80%) - avoid edges
                spawn_z = int(map_size * (0.2 + self.rng.random() * 0.6))
                unit = {"type": chosen_type, "pos": (spawn_x, 0, spawn_z), "description": obj.get("description")}
                # Populate unit fields if template had defaults (lightweight)
                if isinstance(chosen_type, str):
                    # nothing else to do
                    pass
                # Attempt to materialize the unit if possible, otherwise keep dict
                try:
                    # Use map-bounded position for spawn units with better distribution
                    # Map origin is bottom-left (0,0), use wider range: 15-75% of map
                    # Calculate spawn X with offset but ensure it doesn't exceed bounds
                    spawn_x_offset = 1000 * (idx + 1)
                    spawn_x = min(x_m + spawn_x_offset, int(map_size * 0.75))  # Max 75% of map
                    spawn_x = max(int(map_size * 0.15), spawn_x)  # Ensure minimum 15% from edge
                    # Distribute Z positions across middle 60% of map (20-80%) - avoid edges
                    spawn_z = int(map_size * (0.2 + self.rng.random() * 0.6))
                    pos = (spawn_x, 0, spawn_z)
                    unit_obj = _materialize_unit(chosen_type, pos, name=chosen_type)
                    wsm.register_unit(f"spawn_{idx+1}", unit_obj)
                except Exception:
                    wsm.register_unit(f"spawn_{idx+1}", unit)

            elif otype == "threat_layer":
                layer = obj.get("layer") or "iads"
                
                # IADS Layering with intelligent placement
                if layer in ("IADS_RING", "IADS_CORE"):
                    # Use reasonable target center within map bounds
                    map_size = 196608.0  # Default map size
                    try:
                        if self.terrain_helper and hasattr(self.terrain_helper, 'tc'):
                            map_size = getattr(self.terrain_helper.tc, 'total_map_size_meters', 196608.0)
                    except Exception:
                        pass
                    
                    # Use strategic position as target center for IADS layers
                    # Map origin is bottom-left (0,0), distribute better across map
                    # Try to use player spawn position if available, otherwise use distributed position
                    target_x = int(map_size * 0.5)  # Default: center in X
                    target_z = int(map_size * 0.5)  # Default: center in Z
                    
                    # Try to use player spawn position if available
                    try:
                        player_spawn_asset = wsm.get_asset("player_spawn")
                        if player_spawn_asset and isinstance(player_spawn_asset, dict):
                            spawn_pos = player_spawn_asset.get("pos")
                            if spawn_pos and len(spawn_pos) >= 2:
                                target_x = int(spawn_pos[0]) if isinstance(spawn_pos[0], (int, float)) else target_x
                                target_z = int(spawn_pos[2] if len(spawn_pos) >= 3 else spawn_pos[1]) if isinstance(spawn_pos[-1], (int, float)) else target_z
                        
                        # If no spawn asset, check for allied units
                        if target_x == int(map_size * 0.5):  # Still at default center
                            player_spawns = [k for k, v in wsm.units.items() 
                                           if isinstance(v, dict) and v.get('team') == 'Allied']
                            if not player_spawns:
                                # Use distributed position: 25-75% of map to avoid clustering
                                target_x = int(map_size * (0.25 + self.rng.random() * 0.5))
                                target_z = int(map_size * (0.25 + self.rng.random() * 0.5))
                    except Exception:
                        # Fallback: use distributed position
                        target_x = int(map_size * (0.25 + self.rng.random() * 0.5))
                        target_z = int(map_size * (0.25 + self.rng.random() * 0.5))
                    
                    # Clamp to safe bounds (10-90% of map) to account for search radius
                    target_x = max(int(map_size * 0.1), min(target_x, int(map_size * 0.9)))
                    target_z = max(int(map_size * 0.1), min(target_z, int(map_size * 0.9)))
                    
                    target_center = (target_x, 0, target_z)
                    threat_level = plan.metadata.get("threat_level", "medium").lower()
                    
                    # Determine number of SAM sites based on threat level and complexity
                    complexity = plan.metadata.get("complexity", {})
                    sam_density = complexity.get("sam_density", "auto")
                    
                    # Base count by threat level
                    if sam_density == "sparse":
                        base_sam_count = {"low": 1, "medium": 2, "high": 2, "extreme": 3}.get(threat_level, 2)
                    elif sam_density == "dense":
                        base_sam_count = {"low": 3, "medium": 4, "high": 6, "extreme": 8}.get(threat_level, 4)
                    else:  # "auto" or "medium"
                        base_sam_count = {"low": 2, "medium": 3, "high": 4, "extreme": 5}.get(threat_level, 3)
                    
                    num_sams = self._scale_units_by_threat(base_sam_count, threat_level)
                    
                    # Determine layer distances (clamped to ensure units stay within map bounds)
                    # Account for target_center position - don't let max_dist push units outside map
                    safe_max_dist_x = min(target_center[0], map_size - target_center[0])
                    safe_max_dist_z = min(target_center[2], map_size - target_center[2])
                    safe_max_dist = min(safe_max_dist_x, safe_max_dist_z) * 0.8  # 80% of safe distance
                    
                    if layer == "IADS_RING":
                        # Outer ring: 15-30km, but clamp to map bounds
                        min_dist, max_dist = 15000, min(30000, int(safe_max_dist))
                        sam_type_hint = "long_range_sam"
                    else:  # IADS_CORE
                        # Inner ring: 5-15km, but clamp to map bounds
                        min_dist, max_dist = 5000, min(15000, int(safe_max_dist))
                        sam_type_hint = "medium_range_sam"
                    
                    sam_units_placed = 0
                    sam_positions = []  # Track placed SAM positions for formation spacing
                    
                    for j in range(num_sams):
                        try:
                            # For first SAM, try intelligent placement
                            # For subsequent SAMs in same layer, use formation spacing if we have a good first position
                            if j == 0 or len(sam_positions) == 0:
                                sam_result = _place_unit_intelligently(
                                    unit_type_str="sam_site",
                                    unit_role="air_defense",
                                    target_area=target_center,
                                    wsm=wsm,
                                    plan=plan
                                )
                                
                                if sam_result:
                                    pos, placement_info = sam_result
                                    # Verify it's in the right distance range
                                    from pytol.misc.math_utils import calculate_2d_distance
                                    dist = calculate_2d_distance((pos[0], pos[2]), (target_center[0], target_center[2]))
                                    if min_dist <= dist <= max_dist:
                                        # Verify line of sight to target
                                        if self.terrain_helper.has_line_of_sight(pos, target_center, steps=20):
                                            sam_positions.append((pos, placement_info, dist))
                            else:
                                # Use formation helper for subsequent SAMs - space them around the first one
                                try:
                                    first_pos, first_placement, first_dist = sam_positions[0]
                                    # Use circular formation to place SAMs around first position
                                    # Calculate appropriate formation radius (2-5km spacing)
                                    formation_radius = min(max_dist - first_dist, 5000) if first_dist < max_dist else 3000
                                    formation_radius = max(formation_radius, 2000)  # Minimum 2km spacing
                                    
                                    # Get formation positions using MissionTerrainHelper
                                    formation_positions = self.terrain_helper.get_circular_formation_points(
                                        center_pos=first_pos,
                                        radius=formation_radius,
                                        num_points=num_sams,
                                        start_angle_deg=self.rng.randint(0, 360)
                                    )
                                    
                                    if len(formation_positions) > len(sam_positions):
                                        # Pick next position from formation
                                        candidate_pos = formation_positions[len(sam_positions)]
                                        
                                        # Verify it's in the right distance range and has LoS
                                        candidate_dist = calculate_2d_distance((candidate_pos[0], candidate_pos[2]), (target_center[0], target_center[2]))
                                        if min_dist <= candidate_dist <= max_dist:
                                            if self.terrain_helper.has_line_of_sight(candidate_pos, target_center, steps=20):
                                                # Check minimum spacing from other SAMs
                                                min_spacing = 1500  # Minimum 1.5km between SAMs
                                                too_close = False
                                                for existing_pos, _, _ in sam_positions:
                                                    spacing = calculate_2d_distance((candidate_pos[0], candidate_pos[2]), (existing_pos[0], existing_pos[2]))
                                                    if spacing < min_spacing:
                                                        too_close = True
                                                        break
                                                
                                                if not too_close:
                                                    placement_info = {
                                                        "position": candidate_pos,
                                                        "placement_mode": "ground",
                                                        "use_smart_placement": True,
                                                        "align_to_surface": True,
                                                        "source_query": "get_circular_formation_points",
                                                        "tactical_role": f"{layer.lower()}_sam",
                                                        "layer_distance": candidate_dist,
                                                        "formation_member": len(sam_positions),
                                                    }
                                                    sam_positions.append((candidate_pos, placement_info, candidate_dist))
                                                    pos, placement_info, dist = candidate_pos, placement_info, candidate_dist
                                                else:
                                                    # Fall back to intelligent placement
                                                    sam_result = _place_unit_intelligently(
                                                        unit_type_str="sam_site",
                                                        unit_role="air_defense",
                                                        target_area=target_center,
                                                        wsm=wsm,
                                                        plan=plan
                                                    )
                                                    if sam_result:
                                                        pos, placement_info = sam_result
                                                        dist = calculate_2d_distance((pos[0], pos[2]), (target_center[0], target_center[2]))
                                                        if min_dist <= dist <= max_dist and self.terrain_helper.has_line_of_sight(pos, target_center, steps=20):
                                                            sam_positions.append((pos, placement_info, dist))
                                                        else:
                                                            continue
                                                    else:
                                                        continue
                                            else:
                                                continue
                                        else:
                                            continue
                                    else:
                                        # Fall back to intelligent placement
                                        sam_result = _place_unit_intelligently(
                                            unit_type_str="sam_site",
                                            unit_role="air_defense",
                                            target_area=target_center,
                                            wsm=wsm,
                                            plan=plan
                                        )
                                        if sam_result:
                                            pos, placement_info = sam_result
                                            dist = calculate_2d_distance((pos[0], pos[2]), (target_center[0], target_center[2]))
                                            if min_dist <= dist <= max_dist and self.terrain_helper.has_line_of_sight(pos, target_center, steps=20):
                                                sam_positions.append((pos, placement_info, dist))
                                            else:
                                                continue
                                        else:
                                            continue
                                except Exception:
                                    # Fall back to intelligent placement
                                    sam_result = _place_unit_intelligently(
                                        unit_type_str="sam_site",
                                        unit_role="air_defense",
                                        target_area=target_center,
                                        wsm=wsm,
                                        plan=plan
                                    )
                                    if sam_result:
                                        pos, placement_info = sam_result
                                        dist = calculate_2d_distance((pos[0], pos[2]), (target_center[0], target_center[2]))
                                        if min_dist <= dist <= max_dist and self.terrain_helper.has_line_of_sight(pos, target_center, steps=20):
                                            sam_positions.append((pos, placement_info, dist))
                                        else:
                                            continue
                                    else:
                                        continue
                            
                            # Materialize unit from sam_positions list
                            if len(sam_positions) > sam_units_placed:
                                pos, placement_info, dist = sam_positions[sam_units_placed]
                                
                                # Pick a SAM unit type based on threat diversity
                                sam_types = [t.unit_type for t in UnitLibrary.ENEMY_SAMS] or ["AASite"]
                                if len(sam_types) > 1:
                                    # Use diversity weights to select SAM type
                                    diversity = self._get_sam_diversity_by_threat(threat_level)
                                    sam_type = self.rng.choice(sam_types)
                                else:
                                    sam_type = sam_types[0] if sam_types else "AASite"
                                
                                try:
                                    unit_obj = _materialize_unit(sam_type, pos, name=f"{layer}_SAM_{sam_units_placed+1}")
                                    # Update unit position to match intelligent placement
                                    if hasattr(unit_obj, 'global_position'):
                                        unit_obj.global_position = list(pos) if isinstance(pos, (list, tuple)) else [pos[0], pos[1], pos[2]]
                                    placement_info.update({
                                        "position": pos,
                                        "tactical_role": f"{layer.lower()}_sam",
                                        "layer_distance": dist,
                                    })
                                    wsm.register_unit(f"threat_{idx+1}_{sam_units_placed+1}", unit_obj, placement_info=placement_info)
                                    # Track position for spacing enforcement
                                    if pos not in self._placed_unit_positions:
                                        self._placed_unit_positions.append(pos)
                                    sam_units_placed += 1
                                    self.logger.info("PCG: Placed %s SAM using %s at distance %.0fm", layer, placement_info.get("source_query"), dist)
                                    continue
                                except Exception as exc:
                                    self.logger.debug("PCG: Failed to materialize SAM at intelligent position: %s", exc)
                                    # Remove from sam_positions if materialization failed
                                    if len(sam_positions) > sam_units_placed:
                                        sam_positions.pop(sam_units_placed)
                                    pass
                        except Exception:
                            pass
                    
                    # If we placed SAMs successfully, skip to next objective
                    if sam_units_placed > 0:
                        continue
                
                # Fallback to original placement logic
                if placer is not None:
                    try:
                        center = (x_m, 0, 0)
                        # Scale SAM count based on threat level and complexity
                        complexity = plan.metadata.get("complexity", {})
                        sam_density = complexity.get("sam_density", "auto")
                        
                        # Adjust base count based on SAM density
                        if sam_density == "sparse":
                            base_fallback_count = 1
                        elif sam_density == "dense":
                            base_fallback_count = 5
                        else:  # "auto" or "medium"
                            base_fallback_count = 3
                        
                        scaled_sam_count = self._scale_units_by_threat(base_fallback_count, threat_level)
                        sam_placements = placer.place_sam_network(center=center, radius=15000.0, num_sam_sites=scaled_sam_count, rng=self.rng)
                        for j, (typ, pos) in enumerate(sam_placements):
                            # Try to create real Unit objects for threat placements
                            try:
                                unit_obj = _materialize_unit(typ, pos, name=typ)
                                wsm.register_unit(f"threat_{idx+1}_{j+1}", unit_obj)
                            except Exception:
                                wsm.register_unit(f"threat_{idx+1}_{j+1}", {"type": typ, "pos": pos, "layer": layer})
                        continue
                    except Exception:
                        pass

                # Fallback simple threats
                # Try to pick SAM templates from UnitLibrary first
                sam_types = [t.unit_type for t in UnitLibrary.ENEMY_SAMS] or [f"{layer}_site"]
                
                # Scale fallback unit count based on threat and complexity
                complexity = plan.metadata.get("complexity", {})
                sam_density = complexity.get("sam_density", "auto")
                
                # Adjust base count based on SAM density
                if sam_density == "sparse":
                    base_fallback_count = 1
                elif sam_density == "dense":
                    base_fallback_count = 4
                else:  # "auto" or "medium"
                    base_fallback_count = 2
                
                scaled_fallback_count = self._scale_units_by_threat(base_fallback_count, threat_level)
                for j in range(scaled_fallback_count):
                    tid = f"threat_{idx+1}_{j+1}"
                    typ = sam_types[j % len(sam_types)]
                    # Generate proper 3D position with random Z distribution
                    fallback_x = min(x_m + 2000 * (j+1), int(map_size * 0.85))
                    fallback_x = max(int(map_size * 0.15), fallback_x)
                    fallback_z = int(map_size * (0.2 + self.rng.random() * 0.6))
                    pos = (fallback_x, 0, fallback_z)
                    try:
                        unit_obj = _materialize_unit(typ, pos, name=typ)
                        wsm.register_unit(tid, unit_obj)
                    except Exception:
                        unit = {"type": typ, "pos": pos, "layer": layer}
                        wsm.register_unit(tid, unit)

            elif otype == "ai_task":
                action = obj.get("action") or "generic_ai"
                aid = f"ai_{idx+1}"
                
                # Resolve action to concrete unit type using ABSTRACT_TO_CONCRETE mapping
                action_lower = action.lower()
                unit_type_str = UnitLibrary.resolve_abstract(action_lower)
                
                if not unit_type_str:
                    # Try common action -> unit mappings
                    action_to_unit = {
                        'awacs': 'AEW-50',  # Enemy AWACS
                        'tanker': 'KC-49',  # Allied tanker
                        'cap': 'ASF-30',   # Enemy CAP
                        'escort': 'F-45A AI',  # Allied escort
                        'generic_ai': 'ASF-30',
                    }
                    unit_type_str = action_to_unit.get(action_lower)
                
                # Generate position for AI unit
                ai_x = min(x_m + 5000 * (idx+1), int(map_size * 0.85))
                ai_x = max(int(map_size * 0.15), ai_x)
                ai_z = int(map_size * (0.2 + self.rng.random() * 0.6))
                
                # Determine altitude based on action type
                if action_lower in ['awacs', 'tanker', 'cap']:
                    ai_altitude = 8000  # High altitude for AWACS/tanker/CAP
                else:
                    ai_altitude = 1000
                
                # Get terrain height
                try:
                    terrain_height = self.terrain_helper.tc.get_terrain_height(ai_x, ai_z)
                    ai_y = terrain_height + ai_altitude
                except Exception:
                    ai_y = ai_altitude
                
                ai_pos = (ai_x, ai_y, ai_z)
                
                # Try to materialize as actual unit
                if unit_type_str:
                    try:
                        # Determine team based on action type
                        team = 'Allied' if action_lower in ['tanker', 'escort'] else 'Enemy'
                        if action_lower == 'awacs':
                            # AWACS can be either team, use Enemy for enemy missions
                            team = 'Enemy'
                        
                        unit_obj = _materialize_unit(unit_type_str, ai_pos, name=f"{action.title()} {idx+1}")
                        
                        # Set team if needed
                        if hasattr(unit_obj, 'team'):
                            unit_obj.team = team
                        elif isinstance(unit_obj, dict):
                            unit_obj['team'] = team
                        
                        # Create placement info
                        placement_info = {
                            'position': ai_pos,
                            'rotation': (0.0, 0.0, 0.0),
                            'placement_mode': 'airborne',
                            'tactical_role': action_lower,
                        }
                        
                        # If waypoint generator is present, create patrol route for CAP/AWACS
                        if waypoint_gen is not None and action_lower in ['cap', 'awacs']:
                            try:
                                cap = waypoint_gen.generate_combat_air_patrol(
                                    ai_pos,
                                    patrol_radius=10000 if action_lower == 'awacs' else 5000,
                                    altitude_agl=ai_altitude,
                                    num_waypoints=6 if action_lower == 'awacs' else 4
                                )
                                if hasattr(unit_obj, 'unit_fields'):
                                    unit_obj.unit_fields['cap_waypoints'] = cap
                                elif isinstance(unit_obj, dict):
                                    unit_obj['cap_waypoints'] = cap
                            except Exception:
                                pass
                        
                        wsm.register_unit(aid, unit_obj, placement_info=placement_info)
                        self.logger.info("PCG: Materialized AI task '%s' as unit '%s' (team=%s)", action, unit_type_str, team)
                        continue
                    except Exception as exc:
                        self.logger.warning("PCG: Failed to materialize AI task '%s' as unit '%s': %s", action, unit_type_str, exc)
                
                # Fallback: store as dict if materialization failed
                unit = {
                    "type": unit_type_str or action_lower,
                    "pos": ai_pos,
                    "team": 'Allied' if action_lower in ['tanker', 'escort'] else 'Enemy',
                    "description": obj.get("description", f"AI {action}")
                }
                self.logger.warning("PCG: falling back to dict for AI task '%s' (action=%s)", aid, action)
                self.materialization_diagnostics.append(
                    {"kind": "ai_task_fallback", "id": aid, "action": action, "target": obj.get("target"), "description": obj.get("description")}
                )
                wsm.register_unit(aid, unit)

            elif otype == "secondary_objective":
                # Grammar hints at secondary objective type
                # Actual objectives are generated later based on spawned units
                # Store hint for later processing
                obj_type_hint = obj.get("target")
                wsm.register_asset(f"secondary_objective_hint_{idx+1}", {
                    "type": obj_type_hint,
                    "description": obj.get("description", f"Secondary objective: {obj_type_hint}")
                })
                self.logger.debug("PCG: Registered secondary objective hint: %s", obj_type_hint)
                continue
                
            elif otype == "optional_objective":
                # Grammar hints at optional objective type
                obj_type_hint = obj.get("target")
                wsm.register_asset(f"optional_objective_hint_{idx+1}", {
                    "type": obj_type_hint,
                    "description": obj.get("description", f"Optional objective: {obj_type_hint}")
                })
                self.logger.debug("PCG: Registered optional objective hint: %s", obj_type_hint)
                continue
                
            elif otype == "reinforcement":
                # Grammar hints at reinforcement trigger
                reinf_type = obj.get("target")
                wsm.register_asset(f"reinforcement_hint_{idx+1}", {
                    "type": reinf_type,
                    "description": obj.get("description", f"Reinforcement: {reinf_type}")
                })
                # Reinforcements are handled when generating triggers later
                self.logger.debug("PCG: Registered reinforcement hint: %s", reinf_type)
                continue
                
            else:
                # Generic note or unknown terminal: store as asset note
                wsm.register_asset(f"note_{idx+1}", {"text": obj.get("description", obj.get("raw"))})

        # Basic background unit if planner hinted at scheduling
        if any(((o.type) if isinstance(o, PlanObjective) else o.get("type")) == "schedule_background" for o in plan.objectives):
            # Try to materialize a background transport unit
            try:
                # Generate proper 3D position with random Z distribution and ensure X is within map bounds
                bg_x = min(x_m + 50000, int(map_size * 0.9))  # Ensure within map bounds
                bg_x = max(int(map_size * 0.15), bg_x)  # Ensure minimum 15% from edge
                bg_z = int(map_size * (0.2 + self.rng.random() * 0.6))
                pos = (bg_x, 5000, bg_z)
                unit_obj = _materialize_unit('transport', pos, name='background_transport')
                wsm.register_unit("background_1", unit_obj)
            except Exception:
                # Ensure X is within map bounds
                bg_x = min(x_m + 50000, int(map_size * 0.9))
                bg_x = max(int(map_size * 0.15), bg_x)
                bg_z = int(map_size * (0.2 + self.rng.random() * 0.6))
                wsm.register_unit("background_1", {"type": "transport", "pos": (bg_x, 5000, bg_z)})

        # Generate secondary and optional objectives based on spawned units
        # Secondary objectives: Destroy SAM network, clear route (for SEAD/Strike)
        # Optional objectives: Destroy convoy, destroy artillery battery
        threat_level = plan.metadata.get("threat_level", "medium").lower()
        player_role = plan.metadata.get("player_role", "strike")
        
        # Count units by type for objective generation
        # Use WorldState query helper methods for efficient pattern-based queries
        sam_unit_keys = wsm.get_unit_keys_by_pattern("sam", team="Enemy")
        aa_unit_keys = wsm.get_unit_keys_by_pattern("aa", team="Enemy")
        sam_units = list(set(sam_unit_keys + aa_unit_keys))  # Combine and remove duplicates
        
        artillery_units = wsm.get_unit_keys_by_pattern("artillery", team="Enemy")
        artillery_units.extend(wsm.get_unit_keys_by_pattern("howitzer", team="Enemy"))
        artillery_units = list(set(artillery_units))  # Remove duplicates
        
        # Get convoy units (from static convoy placement)
        convoy_units = []
        static_convoys_asset = wsm.assets.get("static_convoys", {})
        if isinstance(static_convoys_asset, dict):
            convoys_data = static_convoys_asset.get("convoys", {})
            for convoy_id, convoy_info in convoys_data.items():
                convoy_vehicles = convoy_info.get('vehicles', [])
                convoy_units.extend(convoy_vehicles)
        
        # Also check for existing convoy units from grammar
        convoy_units.extend(wsm.get_unit_keys_by_pattern("convoy", team="Enemy"))
        convoy_units.extend(wsm.get_unit_keys_by_pattern("logistic", team="Enemy"))
        convoy_units = list(set(convoy_units))  # Remove duplicates
        
        enemy_aircraft = wsm.get_unit_keys_by_pattern("fighter", team="Enemy")
        enemy_aircraft.extend(wsm.get_unit_keys_by_pattern("ef-", team="Enemy"))
        enemy_aircraft.extend(wsm.get_unit_keys_by_pattern("asf", team="Enemy"))
        enemy_aircraft = list(set(enemy_aircraft))  # Remove duplicates
        
        # Generate objectives for static structures (bunkers, factories, missile silos)
        # These are high-value targets that create interesting gameplay loops
        static_structures_asset = wsm.assets.get("static_structures", {})
        static_structures_data = static_structures_asset.get("structures", {}) if isinstance(static_structures_asset, dict) else {}
        
        objective_counter = 1
        
        # Generate destroy objectives for static structures
        # Structures are grouped by type for objective variety
        structures_by_type = {}
        for struct_id, struct_info in static_structures_data.items():
            struct_type = struct_info.get('structure_type', 'bunker')
            if struct_type not in structures_by_type:
                structures_by_type[struct_type] = []
            structures_by_type[struct_type].append(struct_id)
        
        # Primary objective: Destroy factories (high-value industrial targets)
        if 'factory' in structures_by_type and len(structures_by_type['factory']) > 0:
            factory_ids = structures_by_type['factory']
            wsm.register_objective("destroy_factories", {
                "type": "Destroy",
                "name": "Destroy Enemy Factories",
                "target_label": f"static_factories",  # Will resolve to factory unit IDs
                "required": True,  # Factories are often primary targets
                "completion_reward": 150,
                "description": f"Destroy {len(factory_ids)} enemy factory{'ies' if len(factory_ids) > 1 else ''} to disrupt production",
            })
            # Store factory IDs for target resolution
            wsm.register_asset("objective_factories", {
                "structure_ids": factory_ids,
                "target_label": "static_factories"
            })
            objective_counter += 1
        
        # Primary/Secondary objective: Destroy missile silos (strategic weapons)
        if 'missile_silo' in structures_by_type and len(structures_by_type['missile_silo']) > 0:
            silo_ids = structures_by_type['missile_silo']
            is_primary = len(silo_ids) >= 2 or rng.random() < 0.6  # 60% chance to be primary if 1 silo
            wsm.register_objective("destroy_missile_silos", {
                "type": "Destroy",
                "name": "Destroy Missile Silos",
                "target_label": f"static_missile_silos",
                "required": is_primary,
                "completion_reward": 200 if is_primary else 100,
                "description": f"Destroy {len(silo_ids)} enemy missile silo{'s' if len(silo_ids) > 1 else ''} to prevent launch",
            })
            wsm.register_asset("objective_missile_silos", {
                "structure_ids": silo_ids,
                "target_label": "static_missile_silos"
            })
            objective_counter += 1
        
        # Secondary objective: Destroy bunkers (defensive positions)
        # Only create objective if we actually have bunker structures
        if 'bunker' in structures_by_type and len(structures_by_type['bunker']) > 0:
            bunker_ids = structures_by_type['bunker']
            # Verify bunker structures actually exist in WorldState
            existing_bunker_ids = []
            for struct_id in bunker_ids:
                if struct_id in wsm.units:
                    existing_bunker_ids.append(struct_id)
            
            # Only create objective if we have valid bunker units
            if existing_bunker_ids:
                # Group bunkers into objective if 2+ exist, otherwise optional
                if len(existing_bunker_ids) >= 2:
                    wsm.register_objective("destroy_bunkers", {
                        "type": "Destroy",
                        "name": "Destroy Defensive Bunkers",
                        "target_label": f"static_bunkers",
                        "required": False,  # Secondary but important
                        "completion_reward": 75,
                        "description": f"Destroy {len(existing_bunker_ids)} enemy defensive bunker{'s' if len(existing_bunker_ids) > 1 else ''}",
                    })
                    wsm.register_asset("objective_bunkers", {
                        "structure_ids": existing_bunker_ids,
                        "target_label": "static_bunkers"
                    })
                    objective_counter += 1
                else:
                    # Single bunker = optional bonus objective
                    wsm.register_objective("optional_bunker", {
                        "type": "Destroy",
                        "name": "Destroy Enemy Bunker",
                        "target_label": f"static_bunkers",
                        "required": False,
                        "completion_reward": 40,
                        "description": "Bonus: Destroy enemy defensive bunker",
                    })
                    wsm.register_asset("objective_bunkers", {
                        "structure_ids": existing_bunker_ids,
                        "target_label": "static_bunkers"
                    })
                    objective_counter += 1
            else:
                # No valid bunker units found - skip objective creation
                self.logger.debug("PCG: Skipping bunker objective - no valid bunker units found in WorldState")
        
        # STEP 4: Build mission flow - connect objectives → behaviors → units
        try:
            from pytol.procedural.mission_flow import MissionFlowBuilder
            flow_builder = MissionFlowBuilder()
            flow_nodes = flow_builder.build_flow_from_plan(plan, wsm)
            self.logger.info(f"PCG: Built mission flow with {len(flow_nodes)} flow nodes")
            
            if flow_nodes:
                flow_builder.apply_flow_to_units(flow_nodes, wsm)
                
                # Log how many units got waypoint strategies
                units_with_strategies = sum(1 for pi in wsm.unit_placements.values() if pi.get("waypoint_strategy"))
                self.logger.info(f"PCG: Applied waypoint strategies to {units_with_strategies} units")
                
                # Log flow node details
                for node_id, node in flow_nodes.items():
                    self.logger.debug(f"PCG: Flow node '{node_id}': strategy={node.waypoint_strategy}, target={node.target_label}")
            else:
                self.logger.warning("PCG: No flow nodes generated from mission plan")
        except Exception as exc:
            self.logger.warning("PCG: Could not build mission flow: %s", exc)
            import traceback
            self.logger.debug("PCG: Mission flow error traceback: %s", traceback.format_exc())
        
        # Generate triggers for static structure destruction events
        # When structures are destroyed, spawn reinforcements or unlock new objectives
        for struct_id, struct_info in static_structures_data.items():
            struct_type = struct_info.get('structure_type', 'bunker')
            
            # Create trigger metadata for structure destruction
            # High-value structures (factories, silos) trigger reinforcements
            if struct_type in ['factory', 'missile_silo']:
                wsm.register_trigger(f"structure_destroyed_{struct_id}", {
                    "type": "unit_destroyed",
                    "target_unit_key": struct_id,
                    "description": f"Trigger when {struct_type} is destroyed",
                    "event_type": "spawn_reinforcements",  # Can spawn enemy reinforcements
                    "delay_seconds": 5.0,  # 5 second delay before reinforcements
                })
            elif struct_type == 'bunker':
                # Bunkers might unlock secondary objectives or change enemy behavior
                wsm.register_trigger(f"bunker_destroyed_{struct_id}", {
                    "type": "unit_destroyed",
                    "target_unit_key": struct_id,
                    "description": f"Trigger when bunker is destroyed",
                    "event_type": "unlock_objective",  # Can unlock nearby objectives
                })
        
        # Generate secondary objectives based on mission type and spawned units
        # SEAD missions: Secondary objective to destroy SAM network
        if player_role.lower() == "sead" and len(sam_units) >= 3:
            wsm.register_objective("secondary_sam_network", {
                "type": "Destroy",
                "name": "Destroy SAM Network",
                "target_label": "sam_network",
                "required": False,  # Secondary = optional but important
                "completion_reward": 75,
                "description": "Destroy all SAM sites to establish air superiority",
                "unlocks_after": "primary_player_objective",  # Unlocks after primary completes
            })
            objective_counter += 1
        
        # Strike missions: Secondary objective to destroy specific targets
        if player_role.lower() == "strike" and len(sam_units) >= 2:
            wsm.register_objective("secondary_sam_suppression", {
                "type": "Destroy",
                "name": "Suppress Air Defenses",
                "target_label": "sam_network",
                "required": False,
                "completion_reward": 60,
                "description": "Destroy enemy SAM sites to clear approach route",
            })
            objective_counter += 1
        
        # CAS missions: Secondary objective to destroy artillery
        if player_role.lower() == "cas" and len(artillery_units) >= 1:
            wsm.register_objective("secondary_artillery", {
                "type": "Destroy",
                "name": "Neutralize Artillery",
                "target_label": "artillery_battery",
                "required": False,
                "completion_reward": 50,
                "description": "Destroy enemy artillery positions",
            })
            objective_counter += 1
        
        # Optional objectives (bonus targets) - respect complexity settings
        complexity = plan.metadata.get("complexity", {})
        objective_count = complexity.get("objective_count", "auto")
        
        # Adjust objective generation probability based on complexity
        if objective_count == "few":
            optional_obj_prob = 0.3  # Lower chance for optional objectives
        elif objective_count == "many":
            optional_obj_prob = 0.9  # Higher chance
        else:  # "auto"
            optional_obj_prob = 0.6
        
        if len(convoy_units) >= 1 and self.rng.random() < optional_obj_prob:
            wsm.register_objective("optional_convoy", {
                "type": "Destroy",
                "name": "Destroy Enemy Convoy",
                "target_label": "convoy",
                "required": False,
                "completion_reward": 40,
                "description": "Bonus: Destroy enemy supply convoy",
            })
            objective_counter += 1
        
        if len(artillery_units) >= 2 and player_role.lower() != "cas" and self.rng.random() < 0.4:  # 40% chance
            wsm.register_objective("optional_artillery", {
                "type": "Destroy",
                "name": "Destroy Artillery Battery",
                "target_label": "artillery_battery",
                "required": False,
                "completion_reward": 35,
                "description": "Bonus: Destroy enemy artillery positions",
            })
            objective_counter += 1
        
        # Generate dynamic triggers for threat layers (SAM activation on proximity)
        # This creates a "living battlefield" feel - SAMs activate when player approaches
        trigger_probability = {"low": 0.3, "medium": 0.5, "high": 0.7, "extreme": 0.9}.get(threat_level, 0.5)
        
        # Convert sam_units list to dict format for trigger generation
        sam_units_for_triggers = []
        for sam_key in sam_units:
            unit_obj = wsm.units.get(sam_key)
            if unit_obj:
                sam_units_for_triggers.append({"key": sam_key, "unit": unit_obj})
        
        # Create proximity triggers for SAM activation if we have SAMs and threat level warrants it
        if sam_units_for_triggers and self.rng.random() < trigger_probability:
            # Group SAMs by approximate location to avoid too many triggers
            # Simple heuristic: first SAM gets a trigger
            first_sam = sam_units_for_triggers[0]
            sam_key = first_sam.get("key")
            
            if sam_key:
                # Get SAM position
                sam_pos = None
                sam_unit = first_sam["unit"]
                if isinstance(sam_unit, dict):
                    sam_pos = sam_unit.get("pos")
                else:
                    sam_pos = getattr(sam_unit, "global_position", None)
                
                if sam_pos:
                    # Normalize position to (x, y, z)
                    if isinstance(sam_pos, (list, tuple)):
                        if len(sam_pos) == 2:
                            sam_pos = (sam_pos[0], 0, sam_pos[1])
                        elif len(sam_pos) >= 3:
                            sam_pos = (sam_pos[0], sam_pos[1], sam_pos[2])
                    else:
                        sam_pos = (x_m, 0, 0)  # Fallback
                    
                    # Create a proximity trigger metadata (will be converted to Trigger object by compiler)
                    # Scale trigger radius based on threat level
                    base_radius = 5000.0
                    radius_multiplier = {"low": 0.7, "medium": 1.0, "high": 1.3, "extreme": 1.5}.get(threat_level, 1.0)
                    trigger_radius = base_radius * radius_multiplier
                    
                    wsm.register_trigger("sam_activation_1", {
                        "type": "proximity",
                        "name": "SAM Site Activation",
                        "center": sam_pos,
                        "radius": trigger_radius,
                        "target_unit_key": sam_key,
                        "action": "activate_sam",  # Will activate SAM radar
                        "description": "SAM sites activate when player approaches target area"
                    })
                    self.logger.info("PCG: Created proximity trigger for SAM activation at %s (radius: %.0fm)", sam_pos, trigger_radius)
                    
                    # Generate additional triggers for high threat missions
                    if threat_level in ("high", "extreme") and len(sam_units_for_triggers) > 1:
                        # Add reinforcement trigger: spawn additional SAMs when primary target is destroyed
                        if self.rng.random() < 0.5:  # 50% chance for reinforcements
                            # Pick a secondary SAM for reinforcement
                            second_sam = sam_units_for_triggers[min(1, len(sam_units_for_triggers) - 1)]
                            reinforcement_key = f"reinforcement_{self.rng.randint(1000, 9999)}"
                            wsm.register_trigger(reinforcement_key, {
                                "type": "unit_destroyed",
                                "name": "Reinforcement Spawn",
                                "target_unit_key": sam_key,  # When primary SAM is destroyed
                                "action": "spawn_reinforcements",
                                "reinforcement_unit_key": second_sam.get("key"),
                                "description": "Enemy reinforcements arrive when primary SAM is destroyed"
                            })
                            self.logger.info("PCG: Created reinforcement trigger for SAM destruction")

        # Validate mission coherence
        self._validate_mission_coherence(wsm, plan)
        
        # Validate generated mission using validation module
        validation_report = validate_generated_mission(wsm)
        if validation_report.errors:
            self.logger.error("PCG: Validation found %d errors after realize_plan()", len(validation_report.errors))
            for error in validation_report.errors[:10]:  # Log first 10 errors
                self.logger.error("PCG Validation Error: %s", error)
        if validation_report.warnings:
            self.logger.warning("PCG: Validation found %d warnings after realize_plan()", len(validation_report.warnings))
            for warning in validation_report.warnings[:10]:  # Log first 10 warnings
                self.logger.warning("PCG Validation Warning: %s", warning)
        if validation_report.info:
            for info_msg in validation_report.info[:5]:  # Log first 5 info messages
                self.logger.info("PCG Validation Info: %s", info_msg)
        
        # Optionally persist diagnostics to disk for offline analysis
        if self.diagnostics_outpath:
            try:
                import json
                with open(self.diagnostics_outpath, 'w', encoding='utf-8') as fh:
                    json.dump(self.materialization_diagnostics, fh, indent=2, ensure_ascii=False)
                self.logger.info("PCG: wrote materialization diagnostics to %s", self.diagnostics_outpath)
            except Exception as e:
                self.logger.warning("PCG: failed to write diagnostics to %s: %s", self.diagnostics_outpath, e)

    def _realize_plan_mvp(self, plan: MissionPlan, wsm: WorldState) -> None:
        """Simplified MVP version: Player placement + single objective + waypoints.
        
        This is a minimal implementation that:
        1. Places player on allied airbase (first base, first hangar)
        2. Gets first PLAYER_TASK objective from grammar
        3. Creates a waypoint at objective location
        4. Sets up player objectives and waypoints
        5. Skips all enemy unit placement
        """
        self.logger.info("PCG: Using MVP mode - simplified player-focused mission generation")
        
        # STEP 1: Place player on allied airbase (selected based on seed for variety)
        player_spawn_placed = False
        player_base_index = None
        try:
            from pytol.resources.base_spawn_points import get_available_bases
            if self.mission is not None:
                bases = get_available_bases(self.mission.tc, prefab_type=None)
                if bases:
                    # Use seed to select which base is player spawn (deterministic but varied)
                    # Hash the seed with a constant to ensure different seeds get different bases
                    # This avoids RNG state consumption issues
                    import hashlib
                    seed_hash = int(hashlib.md5(f"base_selection_{self.seed}".encode()).hexdigest(), 16)
                    player_base_index = seed_hash % len(bases)
                    base = bases[player_base_index]
                    base_pos = base.get('position', (0, 0, 0))
                    wsm.register_asset("player_spawn", {
                        "type": "airbase",
                        "pos": base_pos,
                        "base_index": player_base_index,
                        "category": "hangar",
                        "spawn_index": 0,
                        "notes": f"Player spawn at {base.get('prefab_type', 'unknown')} airbase (base {player_base_index})"
                    })
                    player_spawn_placed = True
                    self.logger.info("PCG MVP: Player spawn set to base %d hangar (seed-based selection)", player_base_index)
        except Exception as exc:
            self.logger.warning("PCG MVP: Could not find base for player spawn: %s", exc)
        
        if not player_spawn_placed:
            # Fallback: register default spawn
            wsm.register_asset("player_spawn", {
                "type": "airfield", 
                "pos": (0, 0, 0), 
                "notes": "player home (no base found)"
            })
            player_base_index = 0  # Default to first base for territory assignment
        
        # STEP 2: Find first PLAYER_TASK objective
        player_objective = None
        for obj in plan.objectives:
            if isinstance(obj, PlanObjective):
                if obj.type == "player_task" or obj.type == "PLAYER_TASK":
                    player_objective = obj
                    break
            elif isinstance(obj, dict):
                obj_type = obj.get("type", "").lower()
                if obj_type == "player_task":
                    player_objective = PlanObjective(**obj)
                    break
        
        if not player_objective:
            self.logger.warning("PCG MVP: No PLAYER_TASK objective found in plan")
            return
        
        # Get target from player objective (PlanObjective uses 'target', not 'target_label')
        # For MVP, we always place enemy_airbase units (SAMs/radar), so force target_label to match
        original_target = getattr(player_objective, 'target', None) or getattr(player_objective, 'target_label', None) or "enemy_airbase"
        target_label = "enemy_airbase"  # MVP always uses enemy_airbase (SAMs/radar units)
        
        self.logger.info("PCG MVP: Found player objective: %s (original target: %s, using: %s)", 
                        player_objective.description, original_target, target_label)
        
        # STEP 3: Define objective location (simple placement)
        # For MVP, place objective at a reasonable distance from player spawn
        player_spawn_asset = wsm.assets.get("player_spawn", {})
        player_pos = player_spawn_asset.get("pos", (0, 0, 0))
        
        # Log player spawn position for debugging
        self.logger.info("PCG MVP: Player spawn position: (%.0f, %.0f, %.0f), base_index: %s", 
                        player_pos[0] if len(player_pos) > 0 else 0,
                        player_pos[1] if len(player_pos) > 1 else 0,
                        player_pos[2] if len(player_pos) > 2 else 0,
                        player_spawn_asset.get("base_index", "N/A"))
        
        # Get map size
        map_size = 196608.0  # Default
        try:
            if self.terrain_helper and hasattr(self.terrain_helper, 'tc'):
                map_size = getattr(self.terrain_helper.tc, 'total_map_size_meters', 196608.0)
        except Exception:
            pass
        
        # Place objective at varying distances (20-70% of map width) for more variety
        duration = plan.metadata.get("duration_min", 60)
        base_distance_km = min(10 * duration / 60, map_size / 1000.0 * 0.6)  # Scale with duration
        
        # Add more variation: 20-70% of map width instead of 30-60%
        min_distance_factor = 0.2 + self.rng.random() * 0.1  # 20-30% minimum
        max_distance_factor = 0.5 + self.rng.random() * 0.2  # 50-70% maximum
        distance_factor = min_distance_factor + self.rng.random() * (max_distance_factor - min_distance_factor)
        
        target_distance_m = int(map_size * distance_factor)
        
        # Random direction (away from edges if possible)
        angle_rad = self.rng.random() * 2 * math.pi
        
        # Calculate target position relative to player spawn
        target_x = player_pos[0] + math.cos(angle_rad) * target_distance_m
        target_z = player_pos[2] + math.sin(angle_rad) * target_distance_m
        
        # Clamp to map bounds (with margin)
        margin = 5000
        target_x = max(margin, min(target_x, map_size - margin))
        target_z = max(margin, min(target_z, map_size - margin))
        
        # Get terrain height at target
        target_y = 0
        if self.terrain_helper:
            try:
                target_y = self.terrain_helper.tc.get_terrain_height(target_x, target_z)
            except Exception:
                pass
        
        objective_position = (target_x, target_y, target_z)
        
        # STEP 4: Create mission key point for objective
        objective_key_point_id = f"objective_{target_label}"
        mission_key_points = {
            objective_key_point_id: {
                "position": objective_position,
                "mission_role": "objective",
                "objective_type": player_objective.type,
                "target_label": target_label,
                "description": player_objective.description
            }
        }
        
        wsm.register_asset("mission_key_points", {
            "points": mission_key_points,
            "description": "Strategic mission locations for objectives"
        })
        
        self.logger.info("PCG MVP: Created objective key point at (%.0f, %.0f, %.0f)", 
                        objective_position[0], objective_position[1], objective_position[2])
        
        # STEP 5: Create objective in WorldState
        objective_id = f"player_objective_{target_label}"
        wsm.register_objective(objective_id, {
            "type": "Destroy",  # Default to Destroy for MVP
            "target_label": target_label,
            "required": True,
            "reward": 1000,
            "description": player_objective.description,
            "position": objective_position,
            "key_point_id": objective_key_point_id
        })
        
        # STEP 6: Create waypoint for player to navigate to objective
        # For MVP, create a simple waypoint at the objective location
        waypoint_position = (
            objective_position[0],
            objective_position[1] + 3000,  # 3km AGL for waypoint
            objective_position[2]
        )
        
        wsm.register_asset("player_waypoint", {
            "type": "waypoint",
            "pos": waypoint_position,
            "name": "Objective",
            "description": f"Navigate to {target_label}",
            "related_objective": objective_id
        })
        
        self.logger.info("PCG MVP: Created player waypoint at (%.0f, %.0f, %.0f)", 
                        waypoint_position[0], waypoint_position[1], waypoint_position[2])
        
        # STEP 7: Place enemy units at objective location (Phase 1)
        # For MVP, place simple defensive units (SAMs and radar) near the objective
        enemy_units_placed = self._place_enemy_units_for_objective_mvp(
            target_label, objective_position, objective_id, wsm
        )
        self.logger.info("PCG MVP: Placed %d enemy units at objective", enemy_units_placed)
        
        # STEP 8: Register player unit in WorldState (will be compiled to mission later)
        try:
            from pytol.classes.units import PlayerSpawn
            player_unit = PlayerSpawn(
                unit_id="PlayerSpawn",
                unit_name="Player",
                team="Allied",
                global_position=list(player_pos),
                rotation=[0.0, 0.0, 0.0],
                start_mode="Cold"
            )
            
            # Register player with base spawn info
            # Use the player_base_index that was selected earlier (or default to 0)
            if player_base_index is None:
                player_base_index = 0
            
            player_placement_info = {
                "position": player_pos,
                "base_spawn": {
                    "base_index": player_base_index,
                    "category": "hangar",
                    "spawn_index": 0
                },
                "placement_mode": "ground",
                "use_smart_placement": False,  # Base spawn handles placement
                "align_to_surface": False
            }
            
            wsm.register_unit("player", player_unit, placement_info=player_placement_info)
            self.logger.info("PCG MVP: Registered player unit in WorldState")
        except Exception as exc:
            self.logger.warning("PCG MVP: Could not register player unit: %s", exc)
        
        # STEP 9: Define territories from bases (for visualization)
        self._define_territories_mvp(wsm)
        
        self.logger.info("PCG MVP: MVP mission generation complete - Player placed, objective created, waypoint set, enemy units placed, territories defined")

    def _place_enemy_units_for_objective_mvp(
        self,
        target_label: str,
        objective_position: Tuple[float, float, float],
        objective_id: str,
        wsm: WorldState
    ) -> int:
        """Place enemy units at objective location for MVP (Phase 1).
        
        This is a simplified version that places basic defensive units:
        - For "enemy_airbase": 1-2 SAM units + 1 radar unit
        - Units placed within 2-5km of objective position
        - Simple placement (no complex formations yet)
        
        Args:
            target_label: Objective target label (e.g., "enemy_airbase")
            objective_position: Objective position (x, y, z)
            objective_id: Objective ID for linking
            wsm: WorldState to register units in
            
        Returns:
            Number of units placed
        """
        units_placed = 0
        target_lower = target_label.lower()
        
        # For MVP, only handle "enemy_airbase" objectives
        if "airbase" not in target_lower:
            self.logger.info("PCG MVP Phase 1: Skipping unit placement for target '%s' (not airbase)", target_label)
            return 0
        
        # Determine unit types to place
        # For enemy_airbase: SAMs and radar
        sam_unit_types = []
        radar_unit_type = None
        
        # Use correct SAM launcher unit type (SamBattery1 is the missile launcher)
        # SamBattery1 is the correct launcher unit, not a radar
        sam_unit_types = ["SamBattery1"]  # Always use SamBattery1 for SAM launchers
        
        # Get radar unit - use SamFCR2 (Fire Control Radar) for SAM sites, or ewRadarPyramid for early warning
        # SamFCR2 is the correct radar that works with SamBattery1
        radar_unit_type = "SamFCR2"  # Fire Control Radar for SAM sites
        
        # Place SAM units
        for i, sam_type in enumerate(sam_unit_types):
            # Place within 2-5km of objective, with some variation
            offset_distance = 2000.0 + self.rng.random() * 3000.0  # 2-5km
            angle = self.rng.random() * 2 * math.pi  # Random angle
            
            unit_x = objective_position[0] + offset_distance * math.cos(angle)
            unit_z = objective_position[2] + offset_distance * math.sin(angle)
            
            # Use smart placement to get correct terrain height and rotation
            unit_position = (unit_x, 0.0, unit_z)  # Y will be set by smart placement
            unit_rotation = [0.0, 0.0, 0.0]  # Will be set by smart placement
            
            if self.terrain_helper:
                try:
                    # Get smart placement with random yaw (0-360 degrees)
                    yaw_degrees = self.rng.random() * 360.0
                    placement = self.terrain_helper.tc.get_smart_placement(unit_x, unit_z, yaw_degrees)
                    if placement and 'position' in placement:
                        unit_position = placement['position']
                        if 'rotation' in placement:
                            unit_rotation = list(placement['rotation'])
                        else:
                            # Fallback: use yaw from smart placement
                            unit_rotation = [0.0, yaw_degrees, 0.0]
                except Exception as exc:
                    # Fallback: use simple terrain height
                    try:
                        unit_y = self.terrain_helper.tc.get_terrain_height(unit_x, unit_z)
                        unit_position = (unit_x, unit_y, unit_z)
                        unit_rotation = [0.0, self.rng.random() * 360.0, 0.0]
                    except Exception:
                        pass
            
            # Create unit object
            try:
                from pytol.classes.units import create_unit
                unit_obj = create_unit(
                    sam_type,
                    f"EnemySAM_{i+1}",
                    "Enemy",
                    list(unit_position),
                    unit_rotation
                )
                
                if unit_obj:
                    # Register unit with placement info - use smart placement for correct terrain alignment
                    placement_info = {
                        "position": unit_position,
                        "rotation": unit_rotation,  # Include rotation from smart placement
                        "placement_mode": "ground",
                        "use_smart_placement": True,  # Use smart placement for correct height/rotation
                        "align_to_surface": True,  # Align to terrain surface
                        "related_objective": objective_id,
                        "target_label": target_label
                    }
                    
                    unit_key = f"enemy_sam_{i+1}_{target_label}"
                    wsm.register_unit(unit_key, unit_obj, placement_info=placement_info)
                    units_placed += 1
                    self.logger.info("PCG MVP Phase 1: Placed SAM '%s' at (%.0f, %.0f, %.0f) rot (%.1f, %.1f, %.1f)", 
                                    sam_type, unit_position[0], unit_position[1], unit_position[2],
                                    unit_rotation[0], unit_rotation[1], unit_rotation[2])
            except Exception as exc:
                self.logger.warning("PCG MVP Phase 1: Failed to place SAM '%s': %s", sam_type, exc)
        
        # Place radar unit (closer to objective, 1-2km)
        if radar_unit_type:
            offset_distance = 1000.0 + self.rng.random() * 1000.0  # 1-2km
            angle = self.rng.random() * 2 * math.pi
            
            radar_x = objective_position[0] + offset_distance * math.cos(angle)
            radar_z = objective_position[2] + offset_distance * math.sin(angle)
            
            # Use smart placement to get correct terrain height and rotation
            radar_position = (radar_x, 0.0, radar_z)  # Y will be set by smart placement
            radar_rotation = [0.0, 0.0, 0.0]  # Will be set by smart placement
            
            if self.terrain_helper:
                try:
                    # Get smart placement with random yaw (0-360 degrees)
                    yaw_degrees = self.rng.random() * 360.0
                    placement = self.terrain_helper.tc.get_smart_placement(radar_x, radar_z, yaw_degrees)
                    if placement and 'position' in placement:
                        radar_position = placement['position']
                        if 'rotation' in placement:
                            radar_rotation = list(placement['rotation'])
                        else:
                            # Fallback: use yaw from smart placement
                            radar_rotation = [0.0, yaw_degrees, 0.0]
                except Exception as exc:
                    # Fallback: use simple terrain height
                    try:
                        radar_y = self.terrain_helper.tc.get_terrain_height(radar_x, radar_z)
                        radar_position = (radar_x, radar_y, radar_z)
                        radar_rotation = [0.0, self.rng.random() * 360.0, 0.0]
                    except Exception:
                        pass
            
            try:
                from pytol.classes.units import create_unit
                radar_obj = create_unit(
                    radar_unit_type,
                    "EnemyRadar",
                    "Enemy",
                    list(radar_position),
                    radar_rotation
                )
                
                if radar_obj:
                    placement_info = {
                        "position": radar_position,
                        "rotation": radar_rotation,  # Include rotation from smart placement
                        "placement_mode": "ground",
                        "use_smart_placement": True,  # Use smart placement for correct height/rotation
                        "align_to_surface": True,  # Align to terrain surface
                        "related_objective": objective_id,
                        "target_label": target_label
                    }
                    
                    radar_key = f"enemy_radar_{target_label}"
                    wsm.register_unit(radar_key, radar_obj, placement_info=placement_info)
                    units_placed += 1
                    self.logger.info("PCG MVP Phase 1: Placed radar '%s' at (%.0f, %.0f, %.0f) rot (%.1f, %.1f, %.1f)", 
                                    radar_unit_type, radar_position[0], radar_position[1], radar_position[2],
                                    radar_rotation[0], radar_rotation[1], radar_rotation[2])
            except Exception as exc:
                self.logger.warning("PCG MVP Phase 1: Failed to place radar '%s': %s", radar_unit_type, exc)
        
        return units_placed

    def _define_territories_mvp(self, wsm: WorldState) -> None:
        """Define territories from bases for MVP visualization.
        
        This creates friendly territory around the player's base and enemy territory
        around other bases. The player base is selected based on seed for variety.
        
        Args:
            wsm: WorldState to register territories in
        """
        try:
            from pytol.resources.base_spawn_points import get_available_bases
            from pytol.procedural.territory_helpers import define_territory_from_base
            
            if self.mission is None:
                return
            
            bases = get_available_bases(self.mission.tc, prefab_type=None)
            if not bases:
                return
            
            # Get player base index from asset (set during player spawn)
            player_base_index = 0  # Default
            player_spawn_asset = wsm.assets.get("player_spawn", {})
            if "base_index" in player_spawn_asset:
                player_base_index = player_spawn_asset["base_index"]
            else:
                # Fallback: use seed hash to select player base (same logic as spawn selection)
                import hashlib
                seed_hash = int(hashlib.md5(f"base_selection_{self.seed}".encode()).hexdigest(), 16)
                player_base_index = seed_hash % len(bases)
            
            # Define friendly territory around player's base
            if 0 <= player_base_index < len(bases):
                player_base = bases[player_base_index]
                player_base_pos = player_base.get('position', (0, 0, 0))
                player_base_2d = (player_base_pos[0], player_base_pos[2] if len(player_base_pos) >= 3 else player_base_pos[1])
                
                # Friendly territory: 30km radius around player base
                define_territory_from_base(
                    wsm=wsm,
                    base_position=player_base_2d,
                    radius=30000.0,  # 30km
                    territory_type='friendly'
                )
                self.logger.info("PCG MVP: Defined friendly territory around player base (base %d)", player_base_index)
            
            # Define enemy territory around all other bases
            enemy_base_count = 0
            for i, base in enumerate(bases):
                if i != player_base_index:  # Skip player's base
                    base_pos = base.get('position', (0, 0, 0))
                    base_2d = (base_pos[0], base_pos[2] if len(base_pos) >= 3 else base_pos[1])
                    
                    # Enemy territory: 30km radius around each enemy base
                    define_territory_from_base(
                        wsm=wsm,
                        base_position=base_2d,
                        radius=30000.0,  # 30km
                        territory_type='enemy'
                    )
                    enemy_base_count += 1
            
            if enemy_base_count > 0:
                self.logger.info("PCG MVP: Defined enemy territory around %d enemy bases", enemy_base_count)
        except Exception as exc:
            self.logger.warning("PCG MVP: Could not define territories: %s", exc)


__all__ = ["PCG"]
