"""World State Manager (WSM) skeleton.

The WSM is a minimal in-memory authoritative store for units and strategic assets
used by the procedural pipeline. It's intentionally small here; later iterations
will add query helpers, spatial indices, and persistence helpers.
"""
from typing import Dict, Any, List, Optional, Tuple


class WorldState:
    """Simple world state registry.

    Units are stored in a dict keyed by unique id. Each unit is represented by a
    small dict containing at least 'type' and 'pos' keys. This class is thread
    safe only for single-threaded usage in the MVP.
    """

    def __init__(self) -> None:
        self.units: Dict[str, Any] = {}  # unit_id -> Unit object or dict
        self.assets: Dict[str, Dict[str, Any]] = {}
        # Track objectives metadata (will be converted to Objective objects by compiler)
        self.objectives: Dict[str, Dict[str, Any]] = {}
        # Track conditionals metadata (will be registered in Mission)
        self.conditionals: Dict[str, Any] = {}
        # Track triggers/events metadata
        self.triggers: Dict[str, Dict[str, Any]] = {}
        # Track global values metadata
        self.global_values: Dict[str, Dict[str, Any]] = {}
        # Track placement metadata for units (position, rotation, placement mode, etc.)
        self.unit_placements: Dict[str, Dict[str, Any]] = {}
        # Track territory control zones (enemy/friendly/neutral)
        # Format: {'enemy': [{'type': 'circle', 'center': (x, z), 'radius': float}, ...], ...}
        self.territory_zones: Dict[str, List[Dict[str, Any]]] = {
            'enemy': [],
            'friendly': [],
            'neutral': []
        }

    def register_unit(self, unit_id: str, info: Any, placement_info: Optional[Dict[str, Any]] = None) -> None:
        """Register a unit. Info can be a Unit dataclass or a dict.
        
        Args:
            unit_id: Unique identifier for the unit
            info: Unit object or dict
            placement_info: Optional placement metadata (position, rotation, placement_mode, etc.)
        """
        self.units[unit_id] = info
        if placement_info:
            self.unit_placements[unit_id] = placement_info

    def register_asset(self, asset_id: str, info: Dict[str, Any]) -> None:
        self.assets[asset_id] = info

    def register_objective(self, objective_id: str, info: Dict[str, Any]) -> None:
        """Register objective metadata. Will be converted to Objective objects by compiler."""
        self.objectives[objective_id] = info

    def register_conditional(self, conditional_id: str, conditional_obj: Any) -> None:
        """Register a conditional object. Will be registered in Mission by compiler."""
        self.conditionals[conditional_id] = conditional_obj

    def register_trigger(self, trigger_id: str, info: Dict[str, Any]) -> None:
        """Register trigger/event metadata."""
        self.triggers[trigger_id] = info

    def register_global_value(self, gv_name: str, info: Dict[str, Any]) -> None:
        """Register global value metadata."""
        self.global_values[gv_name] = info

    def query_units_by_type(self, unit_type: str) -> List[Any]:
        """Query units by type. Returns list of Unit objects or dicts."""
        results = []
        for u in self.units.values():
            try:
                if isinstance(u, dict):
                    if u.get('type') == unit_type:
                        results.append(u)
                else:
                    # assume dataclass Unit with attribute 'unit_id' or 'unit_type'
                    uid = getattr(u, 'unit_id', None)
                    utype = getattr(u, 'unit_type', None)
                    if uid == unit_type or utype == unit_type:
                        results.append(u)
            except Exception:
                continue
        return results

    def query_units_by_team(self, team: str) -> List[Any]:
        """Query units by team (Allied, Enemy, etc.)."""
        results = []
        for u in self.units.values():
            try:
                if isinstance(u, dict):
                    if u.get('team') == team:
                        results.append(u)
                else:
                    # Check team attribute
                    u_team = getattr(u, 'team', None)
                    if u_team == team:
                        results.append(u)
            except Exception:
                continue
        return results

    def get_unit_ids(self, team: Optional[str] = None) -> List[str]:
        """Get all unit IDs, optionally filtered by team."""
        if team is None:
            return list(self.units.keys())
        return [uid for uid, u in self.units.items() 
                if (isinstance(u, dict) and u.get('team') == team) or
                   (hasattr(u, 'team') and getattr(u, 'team') == team)]

    def get_placement_info(self, unit_id: str) -> Optional[Dict[str, Any]]:
        """Get placement metadata for a unit."""
        return self.unit_placements.get(unit_id)
    
    def query_units_by_pattern(self, pattern: str, team: Optional[str] = None) -> List[Any]:
        """Query units by pattern match in type, name, or tactical role.
        
        Args:
            pattern: Pattern to search for in unit type, name, or tactical role (case-insensitive)
            team: Optional team filter (e.g., "Enemy", "Allied")
        
        Returns:
            List of matching Unit objects or dicts
        """
        results = []
        units_to_check = self.query_units_by_team(team) if team else list(self.units.values())
        
        pattern_lower = pattern.lower()
        for u in units_to_check:
            try:
                unit_type = ""
                unit_name = ""
                tactical_role = ""
                
                if isinstance(u, dict):
                    unit_type = str(u.get("type", "")).lower()
                    unit_name = str(u.get("name", "")).lower()
                    placement_info = u.get("placement_info", {})
                    if isinstance(placement_info, dict):
                        tactical_role = str(placement_info.get("tactical_role", "")).lower()
                else:
                    unit_type = str(getattr(u, "unit_type", "")).lower()
                    unit_name = str(getattr(u, "unit_name", "")).lower()
                    placement_info = getattr(u, "placement_info", None)
                    if isinstance(placement_info, dict):
                        tactical_role = str(placement_info.get("tactical_role", "")).lower()
                
                if (pattern_lower in unit_type or 
                    pattern_lower in unit_name or 
                    pattern_lower in tactical_role):
                    results.append(u)
            except Exception:
                continue
        return results
    
    def get_unit_keys_by_pattern(self, pattern: str, team: Optional[str] = None) -> List[str]:
        """Get unit IDs that match a pattern.
        
        Args:
            pattern: Pattern to search for in unit type, name, or tactical role (case-insensitive)
            team: Optional team filter (e.g., "Enemy", "Allied")
        
        Returns:
            List of unit IDs (keys in self.units)
        """
        matching_units = self.query_units_by_pattern(pattern, team)
        # Map units back to their keys
        result_keys = []
        for unit_obj in matching_units:
            for uid, u in self.units.items():
                if u is unit_obj:
                    result_keys.append(uid)
                    break
        return result_keys
    
    def register_territory_zone(self, territory_type: str, zone: Dict[str, Any]) -> None:
        """Register a territory control zone.
        
        Args:
            territory_type: 'enemy', 'friendly', or 'neutral'
            zone: Zone specification dict:
                - {'type': 'circle', 'center': (x, z), 'radius': float} for circular zone
                - {'type': 'polygon', 'vertices': [(x1, z1), (x2, z2), ...]} for polygonal zone
        """
        if territory_type in self.territory_zones:
            self.territory_zones[territory_type].append(zone)
    
    def get_territory_constraints(self, team: str, include_excluded: bool = True) -> Dict[str, Any]:
        """Get constraint areas for a team.
        
        Args:
            team: Team name ('Enemy', 'Allied', etc.)
            include_excluded: If True, also returns excluded areas (opposing team territories)
        
        Returns:
            Dict with 'constraint_area' (list of allowed zones) and optionally 'excluded_areas'
        """
        # Map team names to territory types
        team_to_territory = {
            'Enemy': 'enemy',
            'Allied': 'friendly',
            'Friendly': 'friendly',
        }
        territory_type = team_to_territory.get(team, 'neutral')
        
        # Get allowed zones for this team
        allowed_zones = self.territory_zones.get(territory_type, [])
        
        result = {}
        
        # If there are allowed zones, combine them (use first as constraint, others can be checked by validator)
        if allowed_zones:
            # For now, use the first zone as the primary constraint
            # In the future, could combine multiple zones
            result['constraint_area'] = allowed_zones[0] if len(allowed_zones) == 1 else None
            
            # If multiple zones, we'll need a validator function
            if len(allowed_zones) > 1:
                def _multi_zone_validator(pos_2d):
                    """Check if position is in any allowed zone."""
                    from pytol.misc.math_utils import is_position_in_circle
                    x, z = pos_2d
                    for zone in allowed_zones:
                        if zone.get('type') == 'circle':
                            center = zone['center']
                            radius = zone['radius']
                            if is_position_in_circle((x, z), center, radius):
                                return True
                        elif zone.get('type') == 'polygon':
                            # Would need access to terrain calculator for this
                            # For now, skip polygon validation in multi-zone case
                            pass
                    return False
                result['position_validator'] = _multi_zone_validator
        
        # Get excluded areas (opposing team territories)
        if include_excluded:
            excluded = []
            if territory_type == 'enemy':
                excluded.extend(self.territory_zones.get('friendly', []))
            elif territory_type == 'friendly':
                excluded.extend(self.territory_zones.get('enemy', []))
            if excluded:
                result['excluded_areas'] = excluded
        
        return result
    
    def get_unit_allowed_in_territory(
        self, 
        unit_type: str, 
        territory_type: str
    ) -> bool:
        """
        Check if unit type is allowed in territory type.
        
        Rules:
        - Neutral: ONLY mobile units (tanks, APCs, trucks, mobile artillery, infantry, aircraft)
                  FORBIDDEN: Any static defense (SAMs, radars, bunkers, static artillery)
        - Enemy/Friendly: All units allowed
        
        Args:
            unit_type: Unit type string (e.g., 'SAM', 'TANK', 'enemyMBT1', 'PatriotLauncher')
            territory_type: Territory type ('enemy', 'friendly', 'neutral')
        
        Returns:
            bool: True if unit is allowed in this territory type
        
        Example:
            # Check if SAM is allowed in neutral territory
            allowed = wsm.get_unit_allowed_in_territory('SAM', 'neutral')
            # Returns False - SAMs not allowed in neutral territory
            
            # Check if tank is allowed in neutral territory
            allowed = wsm.get_unit_allowed_in_territory('TANK', 'neutral')
            # Returns True - mobile units allowed
        """
        # If not neutral territory, all units are allowed
        if territory_type != 'neutral':
            return True
        
        # For neutral territory, only mobile units are allowed
        # Static defenses are FORBIDDEN
        
        unit_lower = unit_type.lower()
        
        # Check for static SAM/AAA patterns
        static_sam_patterns = [
            'sam', 'aaa', 'ciws', 'patriot', 'backstop', 'phallanx',
            'staticciws', 'staticaaa', 'staticaa', 'launcher',
            'radar', 'ewradar', 'patradar', 'bstopradar', 'srad'
        ]
        
        # Check for bunker patterns
        bunker_patterns = [
            'bunker', 'missilesilo', 'silo'
        ]
        
        # Check for static artillery patterns (non-mobile)
        static_artillery_patterns = [
            'staticartillery', 'fixedartillery'
        ]
        
        # Check for radar emitter patterns (static defenses)
        radar_patterns = [
            'radar', 'ewradar', 'patradar', 'bstopradar', 'srad', 'radartrailer'
        ]
        
        # If matches any static defense pattern, forbid it
        if any(pattern in unit_lower for pattern in static_sam_patterns):
            return False
        
        if any(pattern in unit_lower for pattern in bunker_patterns):
            return False
        
        if any(pattern in unit_lower for pattern in static_artillery_patterns):
            return False
        
        # Allow radar only if it's mobile (trailer, truck-mounted)
        # Static radars (without 'truck' or 'trailer') are forbidden
        if any(pattern in unit_lower for pattern in radar_patterns):
            # Allow only mobile radars (truck, trailer, mobile variants)
            if 'truck' in unit_lower or 'trailer' in unit_lower or 'mobile' in unit_lower:
                return True  # Mobile radar allowed
            else:
                return False  # Static radar forbidden
        
        # All other units are considered mobile and allowed
        # This includes: tanks, APCs, trucks, mobile artillery, infantry, aircraft, ships
        return True
    
    def get_territory_at_position(self, x: float, z: float) -> Optional[str]:
        """
        Return territory type ('friendly', 'enemy', 'neutral') at position.
        
        Args:
            x: X coordinate (world position)
            z: Z coordinate (world position)
        
        Returns:
            Territory type string ('friendly', 'enemy', 'neutral') or None if position
            is not in any defined territory
        """
        # Check each territory type in order of precedence
        # Priority: friendly > enemy > neutral (if explicitly defined)
        
        # Check friendly territories first
        for zone in self.territory_zones.get('friendly', []):
            if zone.get('type') == 'circle':
                center = zone['center']
                radius = zone['radius']
                from pytol.misc.math_utils import is_position_in_circle
                if is_position_in_circle((x, z), center, radius):
                    return 'friendly'
            elif zone.get('type') == 'polygon':
                vertices = zone.get('vertices', [])
                if vertices and self._point_in_polygon(x, z, vertices):
                    return 'friendly'
        
        # Check enemy territories
        for zone in self.territory_zones.get('enemy', []):
            if zone.get('type') == 'circle':
                center = zone['center']
                radius = zone['radius']
                from pytol.misc.math_utils import is_position_in_circle
                if is_position_in_circle((x, z), center, radius):
                    return 'enemy'
            elif zone.get('type') == 'polygon':
                vertices = zone.get('vertices', [])
                if vertices and self._point_in_polygon(x, z, vertices):
                    return 'enemy'
        
        # Check neutral territories (explicitly defined)
        for zone in self.territory_zones.get('neutral', []):
            if zone.get('type') == 'circle':
                center = zone['center']
                radius = zone['radius']
                from pytol.misc.math_utils import is_position_in_circle
                if is_position_in_circle((x, z), center, radius):
                    return 'neutral'
            elif zone.get('type') == 'polygon':
                vertices = zone.get('vertices', [])
                if vertices and self._point_in_polygon(x, z, vertices):
                    return 'neutral'
        
        # If not in any explicitly defined territory, assume neutral (no-man's-land)
        # This handles the case where territories don't cover the entire map
        return 'neutral'
    
    def is_position_in_territory(
        self, 
        x: float, z: float, 
        territory_types: List[str]
    ) -> bool:
        """
        Check if position is in any of the specified territory types.
        
        Args:
            x: X coordinate (world position)
            z: Z coordinate (world position)
            territory_types: List of territory types to check ('friendly', 'enemy', 'neutral')
        
        Returns:
            True if position is in any of the specified territory types
        """
        territory_at_pos = self.get_territory_at_position(x, z)
        if territory_at_pos is None:
            return False
        
        return territory_at_pos in territory_types
    
    def _point_in_polygon(self, x: float, z: float, polygon: List[Tuple[float, float]]) -> bool:
        """
        Ray casting algorithm to determine if a point is inside a polygon.
        
        Args:
            x: X coordinate of point
            z: Z coordinate of point
            polygon: List of (x, z) vertex pairs defining the polygon
        
        Returns:
            bool: True if point is inside polygon
        """
        n = len(polygon)
        inside = False
        
        p1x, p1z = polygon[0]
        for i in range(1, n + 1):
            p2x, p2z = polygon[i % n]
            if z > min(p1z, p2z):
                if z <= max(p1z, p2z):
                    if x <= max(p1x, p2x):
                        if p1z != p2z:
                            x_inters = (z - p1z) * (p2x - p1x) / (p2z - p1z) + p1x
                        if p1x == p2x or x <= x_inters:
                            inside = not inside
            p1x, p1z = p2x, p2z
        
        return inside

    def to_dict(self) -> Dict[str, Any]:
        return {
            "units": self.units,
            "assets": self.assets,
            "objectives": self.objectives,
            "conditionals": self.conditionals,
            "triggers": self.triggers,
            "global_values": self.global_values,
            "unit_placements": self.unit_placements,
        }


__all__ = ["WorldState"]
