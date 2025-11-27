"""Mission Flow System - Connects objectives → behaviors → units.

This module defines how mission objectives from the grammar translate into
unit behaviors, waypoints, and mission flow logic.
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import math


@dataclass
class MissionFlowNode:
    """Represents a node in the mission flow graph."""
    objective_id: str
    objective_type: str  # "player_task", "ai_task", "spawn", etc.
    target_label: str
    unit_behaviors: List[Dict[str, Any]]  # List of behaviors units should have
    waypoint_strategy: Optional[str] = None  # How to generate waypoints
    enemy_ai_behavior: Optional[str] = None  # How enemy AI should behave
    support_flight_behavior: Optional[str] = None  # How support flights should behave


class MissionFlowBuilder:
    """Builds mission flow from grammar objectives."""
    
    @staticmethod
    def build_flow_from_plan(plan, wsm) -> Dict[str, MissionFlowNode]:
        """Build mission flow graph from mission plan and world state.
        
        Args:
            plan: MissionPlan with objectives
            wsm: WorldState with registered units and objectives
            
        Returns:
            Dict mapping objective_id to MissionFlowNode
        """
        flow_nodes = {}
        
        # Process player task
        player_task = wsm.assets.get("player_task", {})
        if player_task:
            role = player_task.get("role", "strike")
            target = player_task.get("target", "enemy_unit")
            
            flow_nodes["player_task"] = MissionFlowNode(
                objective_id="player_task",
                objective_type="player_task",
                target_label=target,
                unit_behaviors=[],
                waypoint_strategy=_get_player_waypoint_strategy(role, target),
                enemy_ai_behavior=_get_enemy_ai_behavior_for_target(target),
                support_flight_behavior=None  # Player doesn't need support behavior
            )
        
        # Process AI tasks
        for key, asset in wsm.assets.items():
            if isinstance(asset, dict) and asset.get("type") == "ai_task":
                action = asset.get("action", "").upper()
                target = asset.get("target", "")
                
                flow_nodes[key] = MissionFlowNode(
                    objective_id=key,
                    objective_type="ai_task",
                    target_label=target,
                    unit_behaviors=_get_ai_task_behaviors(action, target),
                    waypoint_strategy=_get_ai_task_waypoint_strategy(action, target),
                    enemy_ai_behavior=None,  # AI tasks are for friendly units
                    support_flight_behavior=action
                )
        
        # Process spawn objectives - these define enemy unit behaviors
        for obj_key, obj_info in wsm.objectives.items():
            if isinstance(obj_info, dict):
                obj_type = obj_info.get("type", "")
                target_label = obj_info.get("target_label", "")
                
                if obj_type == "Destroy" and target_label:
                    # Enemy units defending this objective should behave defensively
                    flow_nodes[f"spawn_{obj_key}"] = MissionFlowNode(
                        objective_id=f"spawn_{obj_key}",
                        objective_type="spawn",
                        target_label=target_label,
                        unit_behaviors=_get_defensive_behaviors(target_label),
                        waypoint_strategy="defensive_patrol",
                        enemy_ai_behavior="defend_objective",
                        support_flight_behavior=None
                    )
        
        return flow_nodes
    
    @staticmethod
    def apply_flow_to_units(flow_nodes: Dict[str, MissionFlowNode], wsm) -> None:
        """Apply mission flow behaviors to units in WorldState.
        
        This connects objectives to unit behaviors by:
        1. Finding units related to each objective
        2. Setting appropriate behaviors based on objective type
        3. Generating waypoints based on waypoint strategy
        """
        for node_id, node in flow_nodes.items():
            # Find units related to this objective
            related_units = _find_units_for_objective(node.target_label, wsm)
            
            # Also find units by checking all units and matching to objective
            # This ensures we catch units that might not be found by pattern matching
            if not related_units:
                # Try to find units by checking placement info for objective relationships
                for unit_key, placement_info in wsm.unit_placements.items():
                    # Check if unit is near objective key point
                    if node.waypoint_strategy:
                        # Mark all units for this objective type
                        unit_obj = wsm.units.get(unit_key)
                        if unit_obj:
                            unit_type = ""
                            if isinstance(unit_obj, dict):
                                unit_type = unit_obj.get("type", "").lower()
                            else:
                                unit_type = getattr(unit_obj, "unit_type", "").lower()
                            
                            # Match unit type to objective
                            target_lower = node.target_label.lower()
                            unit_matches = False
                            if "sam" in unit_type and ("sam" in target_lower or "air_defense" in target_lower):
                                unit_matches = True
                            elif "artillery" in unit_type and ("artillery" in target_lower or "battery" in target_lower):
                                unit_matches = True
                            elif any(t in unit_type for t in ["convoy", "logistic"]) and ("convoy" in target_lower or "logistic" in target_lower):
                                unit_matches = True
                            elif "airbase" in target_lower and any(t in unit_type for t in ["sam", "aa", "radar", "defense"]):
                                unit_matches = True
                            
                            if unit_matches and unit_key not in related_units:
                                related_units.append(unit_key)
            
            for unit_key in related_units:
                # Get or create placement_info
                placement_info = wsm.unit_placements.get(unit_key, {})
                
                # Always add waypoint strategy and related objective, even if no behaviors
                placement_info["waypoint_strategy"] = node.waypoint_strategy
                placement_info["related_objective"] = node.objective_id
                
                # Add behavior metadata to placement info
                if node.unit_behaviors:
                    placement_info["mission_behaviors"] = node.unit_behaviors
                    placement_info["enemy_ai_behavior"] = node.enemy_ai_behavior
                    placement_info["support_flight_behavior"] = node.support_flight_behavior
                
                # Ensure position is in placement_info (needed for waypoint generation)
                if "position" not in placement_info:
                    unit_obj = wsm.units.get(unit_key)
                    if unit_obj:
                        if isinstance(unit_obj, dict):
                            pos = unit_obj.get("pos")
                        else:
                            pos = getattr(unit_obj, "global_position", None)
                        if pos and len(pos) >= 3:
                            placement_info["position"] = pos
                
                wsm.unit_placements[unit_key] = placement_info


def _get_player_waypoint_strategy(role: str, target: str) -> str:
    """Get waypoint strategy for player based on role and target."""
    if role == "strike" or role == "sead":
        return "strike_route"  # Direct route to target
    elif role == "cap":
        return "patrol_zone"  # Patrol friendly airspace
    elif role == "cas":
        return "cas_loiter"  # Loiter near friendly ground forces
    elif role == "recon":
        return "recon_route"  # Route through recon zones
    else:
        return "direct_route"


def _get_enemy_ai_behavior_for_target(target: str) -> str:
    """Get enemy AI behavior based on target type."""
    target_lower = target.lower()
    
    if "airbase" in target_lower or "base" in target_lower:
        return "defend_base"  # Defend the airbase
    elif "sam" in target_lower or "air_defense" in target_lower:
        return "defend_network"  # Defend SAM network
    elif "convoy" in target_lower:
        return "escort_convoy"  # Escort the convoy
    elif "artillery" in target_lower:
        return "defend_battery"  # Defend artillery battery
    else:
        return "defend_objective"  # Generic defensive behavior


def _get_ai_task_behaviors(action: str, target: str) -> List[Dict[str, Any]]:
    """Get behaviors for AI task units."""
    behaviors = []
    
    if action == "ESCORT":
        behaviors.append({
            "type": "escort",
            "target": target,
            "formation": "close_escort",
            "engagement_rules": "defensive_only"
        })
    elif action == "AWACS":
        behaviors.append({
            "type": "awacs",
            "orbit_radius": 50000,  # 50km orbit
            "altitude": 10000,  # 10km altitude
            "target": target
        })
    elif action == "TANKER":
        behaviors.append({
            "type": "tanker",
            "orbit_radius": 30000,  # 30km orbit
            "altitude": 6000,  # 6km altitude
            "target": target
        })
    elif action == "SEAD":
        behaviors.append({
            "type": "sead",
            "target": target,
            "engagement_rules": "suppress_sams",
            "standoff_distance": 20000  # 20km standoff
        })
    
    return behaviors


def _get_ai_task_waypoint_strategy(action: str, target: str) -> str:
    """Get waypoint strategy for AI task."""
    if action == "ESCORT":
        return "escort_formation"
    elif action == "AWACS" or action == "TANKER":
        return "orbit_pattern"
    elif action == "SEAD":
        return "sead_route"
    else:
        return "support_route"


def _get_defensive_behaviors(target_label: str) -> List[Dict[str, Any]]:
    """Get defensive behaviors for units defending an objective."""
    behaviors = []
    target_lower = target_label.lower()
    
    if "airbase" in target_lower or "base" in target_lower:
        behaviors.append({
            "type": "defensive_patrol",
            "patrol_radius": 15000,  # 15km patrol radius
            "engagement_rules": "defend_base",
            "priority_targets": ["aircraft", "missiles"]
        })
    elif "sam" in target_lower:
        behaviors.append({
            "type": "network_defense",
            "coordination": "sam_network",
            "engagement_rules": "prioritize_aircraft"
        })
    elif "artillery" in target_lower:
        behaviors.append({
            "type": "battery_defense",
            "defense_radius": 5000,  # 5km defense radius
            "engagement_rules": "defend_battery"
        })
    else:
        behaviors.append({
            "type": "objective_defense",
            "defense_radius": 10000,  # 10km defense radius
            "engagement_rules": "defend_objective"
        })
    
    return behaviors


def _find_units_for_objective(target_label: str, wsm) -> List[str]:
    """Find units related to an objective target label."""
    related_units = []
    target_lower = target_label.lower()
    
    # Query units by pattern
    try:
        matching_units = wsm.query_units_by_pattern(target_label)
        for unit in matching_units:
            # Find unit key
            for unit_key, unit_obj in wsm.units.items():
                if unit_obj is unit:
                    related_units.append(unit_key)
                    break
    except Exception:
        pass
    
    # Also check placement info for objective relationships
    for unit_key, placement_info in wsm.unit_placements.items():
        if placement_info.get("related_objective") == target_label:
            if unit_key not in related_units:
                related_units.append(unit_key)
    
    # Enhanced matching: match units by type and target label patterns
    if not related_units:
        for unit_key, unit_obj in wsm.units.items():
            # Get unit type - try multiple attributes
            unit_type = ""
            unit_class_name = ""
            if isinstance(unit_obj, dict):
                unit_type = unit_obj.get("type", "").lower()
            else:
                # Try unit_type, type, unit_id, or class name
                unit_type = (
                    getattr(unit_obj, "unit_type", None) or
                    getattr(unit_obj, "type", None) or
                    getattr(unit_obj, "unit_id", None) or
                    ""
                )
                if unit_type:
                    unit_type = str(unit_type).lower()
                unit_class_name = type(unit_obj).__name__.lower()
            
            # Match based on target label patterns
            unit_matches = False
            
            # Get unit team
            unit_team = ""
            if isinstance(unit_obj, dict):
                unit_team = unit_obj.get("team", "").lower()
            else:
                unit_team = getattr(unit_obj, "team", "").lower()
            
            # Match enemy_airbase -> enemy units (SAMs, radars, aircraft, etc.)
            if "enemy_airbase" in target_lower or "airbase" in target_lower:
                # Check by class name (AIFixedSAMSpawn, AILockingRadarSpawn, etc.) or type
                if (any(t in unit_class_name for t in ["sam", "radar", "aa", "aircraft", "airbase", "defense"]) or
                    any(t in unit_type for t in ["sam", "radar", "aa", "aircraft", "airbase", "defense", "battery", "launcher", "ewradar"])):
                    if "enemy" in unit_team:
                        unit_matches = True
            
            # Match sam_network or air_defense -> SAM units
            elif "sam" in target_lower or "air_defense" in target_lower:
                if ("sam" in unit_class_name or "sam" in unit_type or 
                    "battery" in unit_type or "launcher" in unit_type):
                    unit_matches = True
            
            # Match artillery_battery -> artillery units
            elif "artillery" in target_lower or "battery" in target_lower:
                if "artillery" in unit_type or "artillery" in unit_class_name:
                    unit_matches = True
            
            # Match convoy -> convoy/logistic units
            elif "convoy" in target_lower or "logistic" in target_lower:
                if (any(t in unit_class_name for t in ["convoy", "logistic", "truck", "vehicle", "ground"]) or
                    any(t in unit_type for t in ["convoy", "logistic", "truck", "vehicle", "elogistics"])):
                    unit_matches = True
            
            # Match static_bunkers -> bunker/defensive structure units
            # BUT: static structures shouldn't get waypoints - they don't move!
            # Only match for behavior assignment, not waypoint generation
            elif "bunker" in target_lower or "static" in target_lower:
                # Don't match static structures for waypoint generation
                # They are fixed in place and don't need waypoints
                pass
            
            # Match theater -> friendly support units (AWACS, tanker, etc.)
            elif "theater" in target_lower:
                if (any(t in unit_class_name for t in ["awacs", "tanker", "support", "aircraft"]) or
                    any(t in unit_type for t in ["awacs", "tanker", "support"])):
                    if "allied" in unit_team or "friendly" in unit_team:
                        unit_matches = True
            
            if unit_matches and unit_key not in related_units:
                related_units.append(unit_key)
    
    return related_units


class WaypointGenerator:
    """Generates waypoints and paths based on mission flow strategies."""
    
    def __init__(self, terrain_helper=None):
        self.terrain_helper = terrain_helper
    
    def generate_waypoints_for_strategy(
        self,
        strategy: str,
        unit_position: Tuple[float, float, float],
        target_position: Optional[Tuple[float, float, float]] = None,
        objective_key_point: Optional[Dict[str, Any]] = None,
        wsm: Optional[Any] = None
    ) -> List[Tuple[float, float, float]]:
        """Generate waypoints based on strategy.
        
        Args:
            strategy: Waypoint strategy (strike_route, patrol_zone, orbit_pattern, etc.)
            unit_position: Starting position of unit
            target_position: Target position (for strike routes)
            objective_key_point: Key point info for objective
            wsm: WorldState for querying related units
            
        Returns:
            List of (x, y, z) waypoint positions
        """
        if not self.terrain_helper:
            return []
        
        waypoints = []
        helper = self.terrain_helper
        
        if strategy == "strike_route" and target_position:
            # Direct route to target with ingress/egress waypoints
            waypoints = self._generate_strike_route(unit_position, target_position)
        
        elif strategy == "patrol_zone":
            # Circular patrol pattern
            center = target_position if target_position else unit_position
            waypoints = self._generate_patrol_zone(center, radius=15000, num_waypoints=6)
        
        elif strategy == "orbit_pattern":
            # Orbit pattern for AWACS/tanker
            center = target_position if target_position else unit_position
            orbit_radius = 30000 if "tanker" in str(objective_key_point).lower() else 50000
            waypoints = self._generate_orbit_pattern(center, orbit_radius, num_waypoints=8)
        
        elif strategy == "escort_formation":
            # Escort formation waypoints
            if target_position:
                waypoints = self._generate_escort_formation(unit_position, target_position)
            else:
                waypoints = [unit_position]  # Fallback
        
        elif strategy == "defensive_patrol":
            # Defensive patrol around objective - only for aircraft
            # Ground units don't need waypoints for defensive patrol
            center = target_position if target_position else unit_position
            # Ensure center is a 3-tuple
            if center and len(center) >= 3:
                waypoints = self._generate_defensive_patrol(center, radius=10000, num_waypoints=4)
            else:
                # Fallback: use unit position
                if unit_position and len(unit_position) >= 3:
                    waypoints = self._generate_defensive_patrol(unit_position, radius=10000, num_waypoints=4)
        
        elif strategy == "sead_route" and target_position:
            # SEAD route with standoff waypoints
            waypoints = self._generate_sead_route(unit_position, target_position)
        
        else:
            # Default: single waypoint at target or unit position
            waypoints = [target_position if target_position else unit_position]
        
        return waypoints
    
    def _generate_strike_route(
        self,
        start: Tuple[float, float, float],
        target: Tuple[float, float, float]
    ) -> List[Tuple[float, float, float]]:
        """Generate strike route with ingress and egress waypoints."""
        if not self.terrain_helper:
            return []
        
        waypoints = []
        
        # Calculate route
        from pytol.misc.math_utils import calculate_bearing, calculate_2d_distance
        
        distance = calculate_2d_distance((start[0], start[2]), (target[0], target[2]))
        bearing = calculate_bearing((start[0], start[2]), (target[0], target[2]), degrees=True)
        
        # Ingress waypoint (20km before target)
        ingress_dist = min(20000, distance * 0.3)
        ingress_x = target[0] - math.cos(math.radians(bearing)) * ingress_dist
        ingress_z = target[2] - math.sin(math.radians(bearing)) * ingress_dist
        ingress_y = self.terrain_helper.tc.get_terrain_height(ingress_x, ingress_z) + 500  # 500m AGL
        waypoints.append((ingress_x, ingress_y, ingress_z))
        
        # Target waypoint
        target_y = self.terrain_helper.tc.get_terrain_height(target[0], target[2]) + 500
        waypoints.append((target[0], target_y, target[2]))
        
        # Egress waypoint (20km after target)
        egress_x = target[0] + math.cos(math.radians(bearing)) * ingress_dist
        egress_z = target[2] + math.sin(math.radians(bearing)) * ingress_dist
        egress_y = self.terrain_helper.tc.get_terrain_height(egress_x, egress_z) + 500
        waypoints.append((egress_x, egress_y, egress_z))
        
        return waypoints
    
    def _generate_patrol_zone(
        self,
        center: Tuple[float, float, float],
        radius: float,
        num_waypoints: int
    ) -> List[Tuple[float, float, float]]:
        """Generate circular patrol zone waypoints."""
        if not self.terrain_helper:
            return []
        
        waypoints = []
        center_x, center_z = center[0], center[2]
        
        for i in range(num_waypoints):
            angle = (360.0 / num_waypoints) * i
            angle_rad = math.radians(angle)
            x = center_x + radius * math.cos(angle_rad)
            z = center_z + radius * math.sin(angle_rad)
            y = self.terrain_helper.tc.get_terrain_height(x, z) + 3000  # 3km AGL for patrol
            waypoints.append((x, y, z))
        
        return waypoints
    
    def _generate_orbit_pattern(
        self,
        center: Tuple[float, float, float],
        radius: float,
        num_waypoints: int
    ) -> List[Tuple[float, float, float]]:
        """Generate orbit pattern waypoints."""
        return self._generate_patrol_zone(center, radius, num_waypoints)
    
    def _generate_escort_formation(
        self,
        escort_pos: Tuple[float, float, float],
        target_pos: Tuple[float, float, float]
    ) -> List[Tuple[float, float, float]]:
        """Generate escort formation waypoints."""
        if not self.terrain_helper:
            return []
        
        # Escort stays 2-5km offset from target
        from pytol.misc.math_utils import calculate_bearing
        
        bearing = calculate_bearing((target_pos[0], target_pos[2]), (escort_pos[0], escort_pos[2]), degrees=True)
        offset_dist = 3000  # 3km offset
        
        offset_x = target_pos[0] + math.cos(math.radians(bearing)) * offset_dist
        offset_z = target_pos[2] + math.sin(math.radians(bearing)) * offset_dist
        offset_y = self.terrain_helper.tc.get_terrain_height(offset_x, offset_z) + 2000  # 2km AGL
        
        return [(offset_x, offset_y, offset_z)]
    
    def _generate_defensive_patrol(
        self,
        center: Tuple[float, float, float],
        radius: float,
        num_waypoints: int
    ) -> List[Tuple[float, float, float]]:
        """Generate defensive patrol waypoints."""
        return self._generate_patrol_zone(center, radius, num_waypoints)
    
    def _generate_sead_route(
        self,
        start: Tuple[float, float, float],
        target: Tuple[float, float, float]
    ) -> List[Tuple[float, float, float]]:
        """Generate SEAD route with standoff waypoints."""
        if not self.terrain_helper:
            return []
        
        from pytol.misc.math_utils import calculate_bearing
        
        bearing = calculate_bearing((start[0], start[2]), (target[0], target[2]), degrees=True)
        standoff_dist = 20000  # 20km standoff
        
        # Standoff waypoint (perpendicular to approach)
        perp_angle = bearing + 90
        standoff_x = target[0] + math.cos(math.radians(perp_angle)) * standoff_dist
        standoff_z = target[2] + math.sin(math.radians(perp_angle)) * standoff_dist
        standoff_y = self.terrain_helper.tc.get_terrain_height(standoff_x, standoff_z) + 5000  # 5km AGL
        waypoints = [(standoff_x, standoff_y, standoff_z)]
        
        # Approach waypoint (closer to target)
        approach_dist = standoff_dist * 0.5
        approach_x = target[0] + math.cos(math.radians(perp_angle)) * approach_dist
        approach_z = target[2] + math.sin(math.radians(perp_angle)) * approach_dist
        approach_y = self.terrain_helper.tc.get_terrain_height(approach_x, approach_z) + 3000
        waypoints.append((approach_x, approach_y, approach_z))
        
        return waypoints

