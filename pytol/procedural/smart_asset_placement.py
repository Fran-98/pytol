"""
Smart Asset Placement System for realistic military infrastructure.

This system intelligently places military assets based on:
- Realistic military planning doctrine
- Terrain suitability and accessibility
- Strategic positioning for logistics and operations
- Mutual support and defensive considerations
- Supply line optimization and vulnerability assessment
- Forward operating base placement principles
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
from enum import Enum

from pytol.terrain.mission_terrain_helper import MissionTerrainHelper
from pytol.misc.math_utils import calculate_slope_from_normal


class AssetType(Enum):
    """Types of military assets."""
    MAIN_AIRBASE = "main_airbase"           # Primary air operations hub
    FORWARD_AIRSTRIP = "forward_airstrip"   # Advanced tactical airstrip
    HELIPAD = "helipad"                     # Helicopter operations
    LOGISTICS_HUB = "logistics_hub"         # Supply and maintenance
    FUEL_DEPOT = "fuel_depot"               # Fuel storage and distribution
    AMMUNITION_DEPOT = "ammunition_depot"   # Weapons and ammo storage
    COMMAND_POST = "command_post"           # Command and control
    RADAR_SITE = "radar_site"               # Surveillance and early warning
    COMM_RELAY = "comm_relay"               # Communications relay
    HOSPITAL = "hospital"                   # Medical facilities
    REPAIR_FACILITY = "repair_facility"     # Maintenance and repair
    CHECKPOINT = "checkpoint"               # Security checkpoint
    SUPPLY_CONVOY_STOP = "supply_stop"      # Convoy rest/resupply point


class TerrainSuitability(Enum):
    """Terrain suitability ratings."""
    EXCELLENT = "excellent"  # Perfect conditions
    GOOD = "good"           # Suitable with minor issues
    ACCEPTABLE = "acceptable" # Usable but suboptimal
    POOR = "poor"           # Major challenges
    UNSUITABLE = "unsuitable" # Cannot be used


@dataclass
class AssetRequirements:
    """Requirements for different asset types."""
    asset_type: AssetType
    min_flat_area: float        # Required flat area in square meters
    max_slope: float           # Maximum acceptable slope in degrees
    min_altitude: float        # Minimum altitude AGL (negative = below sea level OK)
    max_altitude: float        # Maximum altitude AGL
    requires_road_access: bool # Needs road connectivity
    min_distance_to_water: float # Minimum distance to water (meters)
    max_distance_to_water: float # Maximum distance to water (meters, for seaplanes)
    security_buffer: float     # Minimum distance from threats (meters)
    mutual_support_range: float # Range for mutual support with other assets
    supply_line_range: float   # Maximum distance from supply sources
    
    @classmethod
    def get_requirements(cls, asset_type: AssetType) -> 'AssetRequirements':
        """Get requirements for specific asset type."""
        
        requirements = {
            AssetType.MAIN_AIRBASE: cls(
                asset_type=AssetType.MAIN_AIRBASE,
                min_flat_area=2000000,    # 2 km² flat area
                max_slope=2.0,            # Nearly flat
                min_altitude=-50,         # Can be near sea level
                max_altitude=500,         # Not too high for operations
                requires_road_access=True,
                min_distance_to_water=500,
                max_distance_to_water=50000,
                security_buffer=5000,     # 5km security perimeter
                mutual_support_range=20000,
                supply_line_range=100000
            ),
            
            AssetType.FORWARD_AIRSTRIP: cls(
                asset_type=AssetType.FORWARD_AIRSTRIP,
                min_flat_area=500000,     # 0.5 km² flat area
                max_slope=3.0,
                min_altitude=-20,
                max_altitude=1000,
                requires_road_access=True,
                min_distance_to_water=200,
                max_distance_to_water=20000,
                security_buffer=2000,     # 2km security
                mutual_support_range=15000,
                supply_line_range=50000
            ),
            
            AssetType.HELIPAD: cls(
                asset_type=AssetType.HELIPAD,
                min_flat_area=10000,      # Small flat area
                max_slope=5.0,
                min_altitude=-10,
                max_altitude=2000,
                requires_road_access=False, # Can be air-supplied
                min_distance_to_water=50,
                max_distance_to_water=100000,
                security_buffer=1000,
                mutual_support_range=10000,
                supply_line_range=30000
            ),
            
            AssetType.LOGISTICS_HUB: cls(
                asset_type=AssetType.LOGISTICS_HUB,
                min_flat_area=100000,     # Need space for storage
                max_slope=5.0,
                min_altitude=-10,
                max_altitude=800,
                requires_road_access=True, # Critical for truck transport
                min_distance_to_water=100,
                max_distance_to_water=10000,
                security_buffer=3000,
                mutual_support_range=25000,
                supply_line_range=80000
            ),
            
            AssetType.FUEL_DEPOT: cls(
                asset_type=AssetType.FUEL_DEPOT,
                min_flat_area=50000,
                max_slope=3.0,
                min_altitude=0,           # Above sea level for safety
                max_altitude=1000,
                requires_road_access=True,
                min_distance_to_water=500, # Safety buffer from water
                max_distance_to_water=5000,
                security_buffer=2000,     # Fuel is high-value target
                mutual_support_range=15000,
                supply_line_range=60000
            ),
            
            AssetType.RADAR_SITE: cls(
                asset_type=AssetType.RADAR_SITE,
                min_flat_area=5000,
                max_slope=10.0,
                min_altitude=100,         # Higher is better for radar
                max_altitude=3000,
                requires_road_access=True,
                min_distance_to_water=0,
                max_distance_to_water=100000,
                security_buffer=1500,
                mutual_support_range=50000, # Long-range mutual support
                supply_line_range=40000
            ),
            
            AssetType.COMMAND_POST: cls(
                asset_type=AssetType.COMMAND_POST,
                min_flat_area=20000,
                max_slope=8.0,
                min_altitude=50,          # Some elevation for comm
                max_altitude=1500,
                requires_road_access=True,
                min_distance_to_water=100,
                max_distance_to_water=20000,
                security_buffer=3000,     # High-value target
                mutual_support_range=30000,
                supply_line_range=50000
            )
        }
        
        return requirements.get(asset_type, requirements[AssetType.HELIPAD])


@dataclass
class MilitaryAsset:
    """A placed military asset with all relevant information."""
    asset_id: str
    asset_type: AssetType
    position: Tuple[float, float, float]
    
    # Terrain assessment
    terrain_suitability: TerrainSuitability
    slope: float
    elevation: float
    terrain_type: str
    
    # Connectivity
    road_access: bool
    nearest_road_distance: float
    threat_exposure: float  # 0-1, higher = more exposed
    supply_line_connections: List[str] = field(default_factory=list)
    
    # Security
    defensive_positions: List[Tuple[float, float, float]] = field(default_factory=list)
    supporting_assets: List[str] = field(default_factory=list)
    
    # Operations
    operational_status: str = "active"  # active, damaged, destroyed, under_construction
    supply_level: float = 1.0          # 0-1, current supply status
    personnel_capacity: int = 100      # Personnel capacity
    
    # Metadata
    construction_difficulty: float = 1.0  # Relative construction effort
    strategic_value: float = 1.0         # Strategic importance


class SmartAssetPlacementSystem:
    """
    Intelligently places military assets based on realistic military planning.
    
    Considers:
    - Terrain suitability and engineering requirements
    - Strategic positioning and mutual support
    - Supply line optimization and vulnerability
    - Threat exposure and defensive positioning
    - Operational efficiency and accessibility
    """
    
    def __init__(self, terrain_helper: MissionTerrainHelper):
        self.terrain_helper = terrain_helper
        self.placed_assets: Dict[str, MilitaryAsset] = {}
        self.supply_network: Dict[str, List[str]] = {}  # Asset connections
        self.road_network: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
        
    def plan_military_infrastructure(
        self,
        area_center: Tuple[float, float, float],
        area_radius: float,
        force_size: str = "battalion",  # squad, platoon, company, battalion, brigade
        mission_duration: str = "extended"  # temporary, short_term, extended, permanent
    ) -> Dict[str, List[MilitaryAsset]]:
        """
        Plan comprehensive military infrastructure for an area of operations.
        
        Args:
            area_center: Center of operational area
            area_radius: Radius of operational area in meters
            force_size: Size of force to support
            mission_duration: Expected duration of operations
            
        Returns:
            Dictionary of asset categories with placed assets
        """
        
        infrastructure_plan = {
            "airbases": [],
            "logistics": [],
            "command_control": [],
            "support": []
        }
        
        # Determine required assets based on force size and duration
        required_assets = self._determine_required_assets(force_size, mission_duration)
        
        # 1. Place primary airbase (highest priority)
        if AssetType.MAIN_AIRBASE in required_assets:
            airbase = self._place_primary_airbase(area_center, area_radius)
            if airbase:
                infrastructure_plan["airbases"].append(airbase)
                self.placed_assets[airbase.asset_id] = airbase
        
        # 2. Place forward airstrips for tactical operations
        for i in range(required_assets.get(AssetType.FORWARD_AIRSTRIP, 0)):
            airstrip = self._place_forward_airstrip(area_center, area_radius, i+1)
            if airstrip:
                infrastructure_plan["airbases"].append(airstrip)
                self.placed_assets[airstrip.asset_id] = airstrip
        
        # 3. Place logistics infrastructure
        logistics_assets = self._place_logistics_network(area_center, area_radius, required_assets)
        infrastructure_plan["logistics"].extend(logistics_assets)
        for asset in logistics_assets:
            self.placed_assets[asset.asset_id] = asset
        
        # 4. Place command and control assets
        c2_assets = self._place_command_control(area_center, area_radius, required_assets)
        infrastructure_plan["command_control"].extend(c2_assets)
        for asset in c2_assets:
            self.placed_assets[asset.asset_id] = asset
        
        # 5. Place support facilities
        support_assets = self._place_support_facilities(area_center, area_radius, required_assets)
        infrastructure_plan["support"].extend(support_assets)
        for asset in support_assets:
            self.placed_assets[asset.asset_id] = asset
        
        # 6. Establish supply networks and connections
        self._establish_supply_networks()
        
        # 7. Plan defensive positions
        self._plan_defensive_positions()
        
        return infrastructure_plan
    
    def _determine_required_assets(
        self,
        force_size: str,
        mission_duration: str
    ) -> Dict[AssetType, int]:
        """Determine required assets based on force size and mission duration."""
        
        base_requirements = {
            "squad": {
                AssetType.HELIPAD: 1,
                AssetType.COMMAND_POST: 1
            },
            "platoon": {
                AssetType.HELIPAD: 2,
                AssetType.COMMAND_POST: 1,
                AssetType.LOGISTICS_HUB: 1
            },
            "company": {
                AssetType.FORWARD_AIRSTRIP: 1,
                AssetType.HELIPAD: 3,
                AssetType.COMMAND_POST: 1,
                AssetType.LOGISTICS_HUB: 1,
                AssetType.FUEL_DEPOT: 1
            },
            "battalion": {
                AssetType.MAIN_AIRBASE: 1,
                AssetType.FORWARD_AIRSTRIP: 2,
                AssetType.HELIPAD: 4,
                AssetType.COMMAND_POST: 2,
                AssetType.LOGISTICS_HUB: 2,
                AssetType.FUEL_DEPOT: 2,
                AssetType.RADAR_SITE: 1
            },
            "brigade": {
                AssetType.MAIN_AIRBASE: 1,
                AssetType.FORWARD_AIRSTRIP: 3,
                AssetType.HELIPAD: 6,
                AssetType.COMMAND_POST: 3,
                AssetType.LOGISTICS_HUB: 3,
                AssetType.FUEL_DEPOT: 3,
                AssetType.RADAR_SITE: 2,
                AssetType.AMMUNITION_DEPOT: 1
            }
        }
        
        requirements = base_requirements.get(force_size, base_requirements["company"])
        
        # Modify based on mission duration
        if mission_duration == "permanent":
            # Add more robust infrastructure
            requirements[AssetType.REPAIR_FACILITY] = requirements.get(AssetType.REPAIR_FACILITY, 0) + 1
            requirements[AssetType.HOSPITAL] = requirements.get(AssetType.HOSPITAL, 0) + 1
        elif mission_duration == "temporary":
            # Reduce permanent infrastructure
            if AssetType.MAIN_AIRBASE in requirements:
                del requirements[AssetType.MAIN_AIRBASE]
                requirements[AssetType.FORWARD_AIRSTRIP] = requirements.get(AssetType.FORWARD_AIRSTRIP, 0) + 1
        
        return requirements
    
    def _place_primary_airbase(
        self,
        area_center: Tuple[float, float, float],
        area_radius: float
    ) -> Optional[MilitaryAsset]:
        """Place the primary airbase in optimal location."""
        
        requirements = AssetRequirements.get_requirements(AssetType.MAIN_AIRBASE)
        
        # Search for suitable location
        best_position = None
        best_score = -float('inf')
        
        # Search in expanding rings from center
        for ring in range(3):
            search_radius = area_radius * (0.3 + ring * 0.3)  # 30%, 60%, 90% of area
            
            from ..misc.math_utils import generate_random_position_in_circle
            for attempt in range(50):  # 50 attempts per ring
                # Random position in ring
                x, _, z = generate_random_position_in_circle(
                    area_center, search_radius, search_radius * 0.7
                )
                
                
                try:
                    y = self.terrain_helper.tc.get_terrain_height(x, z)
                    position = (x, y, z)
                    
                    score = self._score_airbase_position(position, requirements)
                    
                    if score > best_score:
                        best_score = score
                        best_position = position
                        
                except Exception:
                    continue
        
        if best_position and best_score > 0:  # Only place if score is positive
            return self._create_asset(
                "main_airbase_1",
                AssetType.MAIN_AIRBASE,
                best_position,
                requirements
            )
        
        return None
    
    def _score_airbase_position(
        self,
        position: Tuple[float, float, float],
        requirements: AssetRequirements
    ) -> float:
        """Score a potential airbase position using mission helper assessment."""
        
        # Use consolidated airbase assessment from mission helper
        runway_length = 3000 if requirements.runway_length > 2500 else 2000
        assessment = self.terrain_helper.assess_airbase_suitability(position, runway_length)
        
        # Convert assessment to score
        score = assessment['overall_score'] * 20  # Scale to match existing scoring
        
        # Apply construction difficulty penalty
        score -= (assessment['construction_difficulty'] - 1.0) * 15
        
        # Add strategic value bonus
        score += assessment['strategic_value'] * 10
        
        return max(0.0, score)
    
    def _place_forward_airstrip(
        self,
        area_center: Tuple[float, float, float],
        area_radius: float,
        airstrip_number: int
    ) -> Optional[MilitaryAsset]:
        """Place a forward airstrip for tactical operations."""
        
        requirements = AssetRequirements.get_requirements(AssetType.FORWARD_AIRSTRIP)
        
        # Forward airstrips should be closer to the operational area edges
        # for tactical flexibility
        best_position = None
        best_score = -float('inf')
        
        from ..misc.math_utils import generate_random_position_in_circle
        for attempt in range(100):
            # Bias toward operational area perimeter (60-90% of radius)
            x, _, z = generate_random_position_in_circle(
                area_center, area_radius * 0.9, area_radius * 0.6
            )
            
            # Add angular adjustment for multiple airstrips
            # Rotate position for 120° separation
            if airstrip_number > 1:
                cx, cz = area_center[0], area_center[2]
                dx, dz = x - cx, z - cz
                rotation_angle = (airstrip_number - 1) * (2 * math.pi / 3)
                x = cx + dx * math.cos(rotation_angle) - dz * math.sin(rotation_angle)
                z = cz + dx * math.sin(rotation_angle) + dz * math.cos(rotation_angle)
            
            
            try:
                y = self.terrain_helper.tc.get_terrain_height(x, z)
                position = (x, y, z)
                
                score = self._score_forward_airstrip_position(position, requirements)
                
                # Avoid placing too close to existing assets
                min_distance_to_existing = self._min_distance_to_existing_assets(position)
                if min_distance_to_existing < 5000:  # Less than 5km
                    score -= 50
                
                if score > best_score:
                    best_score = score
                    best_position = position
                    
            except Exception:
                continue
        
        if best_position and best_score > 0:
            return self._create_asset(
                f"forward_airstrip_{airstrip_number}",
                AssetType.FORWARD_AIRSTRIP,
                best_position,
                requirements
            )
        
        return None
    
    def _score_forward_airstrip_position(
        self,
        position: Tuple[float, float, float],
        requirements: AssetRequirements
    ) -> float:
        """Score forward airstrip position with tactical considerations."""
        
        # Similar to airbase scoring but with different priorities
        x, y, z = position
        score = 0.0
        
        try:
            # Terrain suitability (slightly more lenient than main airbase)
            normal = self.terrain_helper.tc.get_terrain_normal(x, z)
            slope = calculate_slope_from_normal(normal)
            
            if slope <= requirements.max_slope:
                score += 80 - slope * 8
            else:
                score -= (slope - requirements.max_slope) * 15
            
            # Altitude (more flexible)
            if requirements.min_altitude <= y <= requirements.max_altitude:
                score += 40
            else:
                score -= 80
            
            # Terrain type
            terrain_type = self.terrain_helper.get_terrain_type((x, z))
            terrain_scores = {
                "Flat": 90,
                "Desert": 85,
                "Urban": -20,  # Less penalty than main airbase
                "Forest": -40,
                "Mountainous": -30,
            }
            score += terrain_scores.get(terrain_type, 0)
            
            # Road access (important but not critical)
            if self.terrain_helper.tc.is_on_road(x, z, tolerance=3000):
                score += 60
            else:
                road_distance = self._find_nearest_road_distance(x, z)
                if road_distance < 10000:
                    score += 30 - (road_distance / 200)
                else:
                    score -= 30
            
            # Tactical positioning - prefer some concealment
            concealment_score = self._assess_concealment(x, z)
            score += concealment_score * 30  # Up to 30 points for good concealment
            
        except Exception:
            score = -1000
        
        return score
    
    def _place_logistics_network(
        self,
        area_center: Tuple[float, float, float],
        area_radius: float,
        required_assets: Dict[AssetType, int]
    ) -> List[MilitaryAsset]:
        """Place logistics infrastructure optimally."""
        
        logistics_assets = []
        
        # Place logistics hubs
        for i in range(required_assets.get(AssetType.LOGISTICS_HUB, 0)):
            asset = self._place_logistics_asset(
                AssetType.LOGISTICS_HUB,
                area_center,
                area_radius,
                f"logistics_hub_{i+1}"
            )
            if asset:
                logistics_assets.append(asset)
        
        # Place fuel depots
        for i in range(required_assets.get(AssetType.FUEL_DEPOT, 0)):
            asset = self._place_logistics_asset(
                AssetType.FUEL_DEPOT,
                area_center,
                area_radius,
                f"fuel_depot_{i+1}"
            )
            if asset:
                logistics_assets.append(asset)
        
        # Place ammunition depots
        for i in range(required_assets.get(AssetType.AMMUNITION_DEPOT, 0)):
            asset = self._place_logistics_asset(
                AssetType.AMMUNITION_DEPOT,
                area_center,
                area_radius,
                f"ammo_depot_{i+1}"
            )
            if asset:
                logistics_assets.append(asset)
        
        return logistics_assets
    
    def _place_logistics_asset(
        self,
        asset_type: AssetType,
        area_center: Tuple[float, float, float],
        area_radius: float,
        asset_id: str
    ) -> Optional[MilitaryAsset]:
        """Place a single logistics asset."""
        
        requirements = AssetRequirements.get_requirements(asset_type)
        
        best_position = None
        best_score = -float('inf')
        
        from ..misc.math_utils import generate_random_position_in_circle
        for attempt in range(80):
            # Logistics assets prefer central locations for efficiency (20-70%)
            x, _, z = generate_random_position_in_circle(
                area_center, area_radius * 0.7, area_radius * 0.2
            )
            
            try:
                y = self.terrain_helper.tc.get_terrain_height(x, z)
                position = (x, y, z)
                
                score = self._score_logistics_position(position, requirements, asset_type)
                
                # Ensure separation from existing assets
                min_distance = self._min_distance_to_existing_assets(position)
                if min_distance < 2000:  # 2km minimum separation
                    score -= 100
                
                if score > best_score:
                    best_score = score
                    best_position = position
                    
            except Exception:
                continue
        
        if best_position and best_score > 0:
            return self._create_asset(asset_id, asset_type, best_position, requirements)
        
        return None
    
    def _score_logistics_position(
        self,
        position: Tuple[float, float, float],
        requirements: AssetRequirements,
        asset_type: AssetType
    ) -> float:
        """Score logistics asset position."""
        
        x, y, z = position
        score = 0.0
        
        try:
            # Basic terrain suitability
            normal = self.terrain_helper.tc.get_terrain_normal(x, z)
            slope = calculate_slope_from_normal(normal)
            
            if slope <= requirements.max_slope:
                score += 70 - slope * 5
            else:
                score -= (slope - requirements.max_slope) * 10
            
            # Road access is critical for logistics
            if self.terrain_helper.tc.is_on_road(x, z, tolerance=1000):
                score += 100  # Major bonus for road access
            else:
                road_distance = self._find_nearest_road_distance(x, z)
                if road_distance < 5000:
                    score += 50 - (road_distance / 100)
                else:
                    score -= 80  # Major penalty for poor road access
            
            # Central location bonus for logistics efficiency
            center_distance = math.sqrt(
                (x - self.terrain_helper.tc.map_size_m/2)**2 + 
                (z - self.terrain_helper.tc.map_size_m/2)**2
            )
            if center_distance < self.terrain_helper.tc.map_size_m * 0.3:
                score += 40  # Bonus for central location
            
            # Security considerations
            if asset_type == AssetType.FUEL_DEPOT:
                # Fuel depots need extra security and concealment
                concealment = self._assess_concealment(x, z)
                score += concealment * 50
                
                # Prefer some distance from populated areas
                terrain_type = self.terrain_helper.get_terrain_type((x, z))
                if terrain_type == "Urban":
                    score -= 30  # Penalty for urban areas (fire risk)
            
        except Exception:
            score = -1000
        
        return score
    
    def _place_command_control(
        self,
        area_center: Tuple[float, float, float],
        area_radius: float,
        required_assets: Dict[AssetType, int]
    ) -> List[MilitaryAsset]:
        """Place command and control assets."""
        
        c2_assets = []
        
        # Place command posts
        for i in range(required_assets.get(AssetType.COMMAND_POST, 0)):
            asset = self._place_c2_asset(
                AssetType.COMMAND_POST,
                area_center,
                area_radius,
                f"command_post_{i+1}"
            )
            if asset:
                c2_assets.append(asset)
        
        # Place radar sites
        for i in range(required_assets.get(AssetType.RADAR_SITE, 0)):
            asset = self._place_c2_asset(
                AssetType.RADAR_SITE,
                area_center,
                area_radius,
                f"radar_site_{i+1}"
            )
            if asset:
                c2_assets.append(asset)
        
        return c2_assets
    
    def _place_c2_asset(
        self,
        asset_type: AssetType,
        area_center: Tuple[float, float, float],
        area_radius: float,
        asset_id: str
    ) -> Optional[MilitaryAsset]:
        """Place command and control asset."""
        
        requirements = AssetRequirements.get_requirements(asset_type)
        
        best_position = None
        best_score = -float('inf')
        
        from ..misc.math_utils import generate_random_position_in_circle
        for attempt in range(100):
            if asset_type == AssetType.RADAR_SITE:
                # Radar sites prefer elevated positions on perimeter
                x, _, z = generate_random_position_in_circle(
                    area_center, area_radius, area_radius * 0.7
                )
            else:
                # Command posts prefer protected central locations
                x, _, z = generate_random_position_in_circle(
                    area_center, area_radius * 0.6, area_radius * 0.3
                )
            
            
            try:
                y = self.terrain_helper.tc.get_terrain_height(x, z)
                position = (x, y, z)
                
                score = self._score_c2_position(position, requirements, asset_type)
                
                # Ensure separation
                min_distance = self._min_distance_to_existing_assets(position)
                if min_distance < 1500:
                    score -= 75
                
                if score > best_score:
                    best_score = score
                    best_position = position
                    
            except Exception:
                continue
        
        if best_position and best_score > 0:
            return self._create_asset(asset_id, asset_type, best_position, requirements)
        
        return None
    
    def _score_c2_position(
        self,
        position: Tuple[float, float, float],
        requirements: AssetRequirements,
        asset_type: AssetType
    ) -> float:
        """Score command and control position."""
        
        x, y, z = position
        score = 0.0
        
        try:
            # Basic terrain check
            normal = self.terrain_helper.tc.get_terrain_normal(x, z)
            slope = calculate_slope_from_normal(normal)
            
            if slope <= requirements.max_slope:
                score += 60 - slope * 3
            else:
                score -= (slope - requirements.max_slope) * 8
            
            if asset_type == AssetType.RADAR_SITE:
                # Radar sites benefit from elevation
                elevation_samples = self._sample_surrounding_elevation(x, z, 3000)
                if elevation_samples:
                    avg_elevation = sum(elevation_samples) / len(elevation_samples)
                    if y > avg_elevation + 50:  # At least 50m above surroundings
                        score += 100
                    elif y > avg_elevation:
                        score += 50
                    else:
                        score -= 20  # Penalty for low position
                
                # Prefer positions with good line of sight
                terrain_type = self.terrain_helper.get_terrain_type((x, z))
                if terrain_type in ["Mountainous", "Flat"]:
                    score += 40
                elif terrain_type == "Forest":
                    score -= 30  # Trees interfere with radar
                
            else:  # Command post
                # Command posts prefer some concealment and protection
                concealment = self._assess_concealment(x, z)
                score += concealment * 40
                
                # Prefer moderate elevation
                if 100 <= y <= 800:
                    score += 30
            
            # Road access important for both
            if self.terrain_helper.tc.is_on_road(x, z, tolerance=2000):
                score += 60
            
        except Exception:
            score = -1000
        
        return score
    
    def _place_support_facilities(
        self,
        area_center: Tuple[float, float, float],
        area_radius: float,
        required_assets: Dict[AssetType, int]
    ) -> List[MilitaryAsset]:
        """Place support facilities like hospitals, repair shops, etc."""
        
        support_assets = []
        
        # Place helipads
        for i in range(required_assets.get(AssetType.HELIPAD, 0)):
            asset = self._place_helipad(area_center, area_radius, i+1)
            if asset:
                support_assets.append(asset)
        
        # Place other support facilities
        for asset_type in [AssetType.HOSPITAL, AssetType.REPAIR_FACILITY]:
            for i in range(required_assets.get(asset_type, 0)):
                asset = self._place_support_asset(
                    asset_type, area_center, area_radius, f"{asset_type.value}_{i+1}"
                )
                if asset:
                    support_assets.append(asset)
        
        return support_assets
    
    def _place_helipad(
        self,
        area_center: Tuple[float, float, float],
        area_radius: float,
        helipad_number: int
    ) -> Optional[MilitaryAsset]:
        """Place helipad with tactical considerations."""
        
        requirements = AssetRequirements.get_requirements(AssetType.HELIPAD)
        
        best_position = None
        best_score = -float('inf')
        
        from ..misc.math_utils import generate_random_position_in_circle
        for attempt in range(60):
            # Distribute helipads around the operational area
            # Generate base position in ring (40-80% of radius)
            x, _, z = generate_random_position_in_circle(
                area_center, area_radius * 0.8, area_radius * 0.4
            )
            
            # Apply rotation for separation (assume max 4 helipads)
            if helipad_number > 0:
                cx, cz = area_center[0], area_center[2]
                dx, dz = x - cx, z - cz
                base_angle = (2 * math.pi * helipad_number) / 4
                x = cx + dx * math.cos(base_angle) - dz * math.sin(base_angle)
                z = cz + dx * math.sin(base_angle) + dz * math.cos(base_angle)
            
            try:
                y = self.terrain_helper.tc.get_terrain_height(x, z)
                position = (x, y, z)
                
                score = self._score_helipad_position(position, requirements)
                
                # Ensure separation from other assets
                min_distance = self._min_distance_to_existing_assets(position)
                if min_distance < 1000:  # 1km minimum
                    score -= 50
                
                if score > best_score:
                    best_score = score
                    best_position = position
                    
            except Exception:
                continue
        
        if best_position and best_score > 0:
            return self._create_asset(
                f"helipad_{helipad_number}",
                AssetType.HELIPAD,
                best_position,
                requirements
            )
        
        return None
    
    def _score_helipad_position(
        self,
        position: Tuple[float, float, float],
        requirements: AssetRequirements
    ) -> float:
        """Score helipad position."""
        
        x, y, z = position
        score = 0.0
        
        try:
            # Slope is critical for helipads
            normal = self.terrain_helper.tc.get_terrain_normal(x, z)
            slope = calculate_slope_from_normal(normal)
            
            if slope <= requirements.max_slope:
                score += 80 - slope * 10  # Very flat preferred
            else:
                score -= (slope - requirements.max_slope) * 15
            
            # Helipads are flexible with terrain types
            terrain_type = self.terrain_helper.get_terrain_type((x, z))
            terrain_scores = {
                "Flat": 70,
                "Desert": 60,
                "Urban": 30,    # Can work in urban areas
                "Forest": -10,  # Need clearing but possible
                "Mountainous": 40,  # Good for tactical helipads
            }
            score += terrain_scores.get(terrain_type, 20)
            
            # Some concealment is good for tactical helipads
            concealment = self._assess_concealment(x, z)
            score += concealment * 25
            
            # Road access helpful but not critical
            if self.terrain_helper.tc.is_on_road(x, z, tolerance=3000):
                score += 30
            
        except Exception:
            score = -1000
        
        return score
    
    def _place_support_asset(
        self,
        asset_type: AssetType,
        area_center: Tuple[float, float, float],
        area_radius: float,
        asset_id: str
    ) -> Optional[MilitaryAsset]:
        """Place general support asset."""
        
        requirements = AssetRequirements.get_requirements(asset_type)
        
        best_position = None
        best_score = -float('inf')
        
        from ..misc.math_utils import generate_random_position_in_circle
        for attempt in range(50):
            # Support facilities prefer protected central locations
            x, _, z = generate_random_position_in_circle(
                area_center, area_radius * 0.5, area_radius * 0.2
            )
            
            
            try:
                y = self.terrain_helper.tc.get_terrain_height(x, z)
                position = (x, y, z)
                
                # Basic scoring similar to logistics assets
                score = self._score_logistics_position(position, requirements, asset_type)
                
                # Extra concealment for medical facilities
                if asset_type == AssetType.HOSPITAL:
                    concealment = self._assess_concealment(x, z)
                    score += concealment * 30
                
                # Ensure separation
                min_distance = self._min_distance_to_existing_assets(position)
                if min_distance < 1000:
                    score -= 40
                
                if score > best_score:
                    best_score = score
                    best_position = position
                    
            except Exception:
                continue
        
        if best_position and best_score > 0:
            return self._create_asset(asset_id, asset_type, best_position, requirements)
        
        return None
    
    def _create_asset(
        self,
        asset_id: str,
        asset_type: AssetType,
        position: Tuple[float, float, float],
        requirements: AssetRequirements
    ) -> MilitaryAsset:
        """Create a military asset with full assessment."""
        
        x, y, z = position
        
        # Assess terrain suitability
        terrain_suitability = self._assess_terrain_suitability(position, requirements)
        
        # Calculate terrain metrics
        normal = self.terrain_helper.tc.get_terrain_normal(x, z)
        slope = calculate_slope_from_normal(normal)
        terrain_type = self.terrain_helper.get_terrain_type((x, z))
        
        # Assess road access
        road_access = self.terrain_helper.tc.is_on_road(x, z, tolerance=1000)
        nearest_road_distance = self._find_nearest_road_distance(x, z)
        
        # Assess threat exposure (simplified)
        threat_exposure = self._assess_threat_exposure(position)
        
        # Calculate construction difficulty
        construction_difficulty = self._calculate_construction_difficulty(
            position, requirements, slope, terrain_type
        )
        
        # Calculate strategic value
        strategic_value = self._calculate_strategic_value(position, asset_type)
        
        return MilitaryAsset(
            asset_id=asset_id,
            asset_type=asset_type,
            position=position,
            terrain_suitability=terrain_suitability,
            slope=slope,
            elevation=y,
            terrain_type=terrain_type,
            road_access=road_access,
            nearest_road_distance=nearest_road_distance,
            threat_exposure=threat_exposure,
            construction_difficulty=construction_difficulty,
            strategic_value=strategic_value
        )
    
    def _assess_terrain_suitability(
        self,
        position: Tuple[float, float, float],
        requirements: AssetRequirements
    ) -> TerrainSuitability:
        """Assess overall terrain suitability for asset type."""
        
        x, y, z = position
        
        try:
            # Check slope
            normal = self.terrain_helper.tc.get_terrain_normal(x, z)
            slope = calculate_slope_from_normal(normal)
            
            if slope > requirements.max_slope * 1.5:
                return TerrainSuitability.UNSUITABLE
            elif slope > requirements.max_slope:
                return TerrainSuitability.POOR
            elif slope <= requirements.max_slope * 0.5:
                slope_rating = TerrainSuitability.EXCELLENT
            else:
                slope_rating = TerrainSuitability.GOOD
            
            # Check altitude
            if not (requirements.min_altitude <= y <= requirements.max_altitude):
                return TerrainSuitability.POOR
            
            # Check terrain type
            terrain_type = self.terrain_helper.get_terrain_type((x, z))
            terrain_suitability = {
                "Flat": TerrainSuitability.EXCELLENT,
                "Desert": TerrainSuitability.GOOD,
                "Urban": TerrainSuitability.ACCEPTABLE,
                "Forest": TerrainSuitability.POOR,
                "Mountainous": TerrainSuitability.ACCEPTABLE
            }
            
            terrain_rating = terrain_suitability.get(terrain_type, TerrainSuitability.ACCEPTABLE)
            
            # Return the worst rating
            ratings = [slope_rating, terrain_rating]
            rating_values = {
                TerrainSuitability.EXCELLENT: 4,
                TerrainSuitability.GOOD: 3,
                TerrainSuitability.ACCEPTABLE: 2,
                TerrainSuitability.POOR: 1,
                TerrainSuitability.UNSUITABLE: 0
            }
            
            min_rating_value = min(rating_values[r] for r in ratings)
            for rating, value in rating_values.items():
                if value == min_rating_value:
                    return rating
            
        except Exception:
            return TerrainSuitability.UNSUITABLE
        
        return TerrainSuitability.ACCEPTABLE
    
    # Helper methods
    def _find_nearest_road_distance(self, x: float, z: float) -> float:
        """Find distance to nearest road (simplified)."""
        # This is a simplified implementation
        # Real implementation would query the actual road network
        if self.terrain_helper.tc.is_on_road(x, z, tolerance=10000):
            return 0.0
        return 5000.0  # Default estimate
    
    def _assess_concealment(self, x: float, z: float) -> float:
        """Assess concealment value (0-1)."""
        terrain_type = self.terrain_helper.get_terrain_type((x, z))
        concealment_values = {
            "Forest": 0.9,
            "Urban": 0.7,
            "Mountainous": 0.6,
            "Desert": 0.2,
            "Flat": 0.1
        }
        return concealment_values.get(terrain_type, 0.5)
    
    def _sample_surrounding_elevation(
        self,
        x: float,
        z: float,
        radius: float
    ) -> List[float]:
        """Sample elevation in area around position."""
        samples = []
        try:
            for i in range(8):  # 8 samples around position
                angle = (2 * math.pi * i) / 8
                sample_x = x + radius * math.cos(angle)
                sample_z = z + radius * math.sin(angle)
                elevation = self.terrain_helper.tc.get_terrain_height(sample_x, sample_z)
                samples.append(elevation)
        except Exception:
            pass
        return samples
    
    def _min_distance_to_existing_assets(self, position: Tuple[float, float, float]) -> float:
        """Find minimum distance to existing assets."""
        if not self.placed_assets:
            return float('inf')
        
        min_distance = float('inf')
        x, y, z = position
        
        from ..misc.math_utils import calculate_2d_distance
        for asset in self.placed_assets.values():
            ax, ay, az = asset.position
            distance = calculate_2d_distance((x, z), (ax, az))
            min_distance = min(min_distance, distance)
        
        return min_distance
    
    def _assess_threat_exposure(self, position: Tuple[float, float, float]) -> float:
        """Assess threat exposure (simplified, 0-1)."""
        # Simplified assessment based on terrain and position
        x, y, z = position
        
        # Higher positions are more exposed
        exposure = min(y / 1000, 1.0)  # Normalize by 1000m
        
        # Edge positions are more exposed
        edge_distance = min(
            x, z,
            self.terrain_helper.tc.map_size_m - x,
            self.terrain_helper.tc.map_size_m - z
        )
        
        if edge_distance < 5000:
            exposure += 0.3
        
        return min(exposure, 1.0)
    
    def _calculate_construction_difficulty(
        self,
        position: Tuple[float, float, float],
        requirements: AssetRequirements,
        slope: float,
        terrain_type: str
    ) -> float:
        """Calculate relative construction difficulty (1.0 = normal)."""
        
        difficulty = 1.0
        
        # Slope affects construction
        if slope > 5.0:
            difficulty += (slope - 5.0) * 0.1
        
        # Terrain type affects construction
        terrain_multipliers = {
            "Flat": 1.0,
            "Desert": 1.1,
            "Urban": 1.5,  # Need to work around existing structures
            "Forest": 1.3,  # Need clearing
            "Mountainous": 1.8  # Difficult terrain
        }
        
        difficulty *= terrain_multipliers.get(terrain_type, 1.0)
        
        # Large assets are more difficult
        if requirements.min_flat_area > 1000000:  # 1 km²
            difficulty *= 1.2
        
        return difficulty
    
    def _calculate_strategic_value(
        self,
        position: Tuple[float, float, float],
        asset_type: AssetType
    ) -> float:
        """Calculate strategic value of position for asset type."""
        
        # Base values by asset type
        base_values = {
            AssetType.MAIN_AIRBASE: 1.0,
            AssetType.FORWARD_AIRSTRIP: 0.8,
            AssetType.COMMAND_POST: 0.9,
            AssetType.RADAR_SITE: 0.7,
            AssetType.LOGISTICS_HUB: 0.6,
            AssetType.FUEL_DEPOT: 0.5,
            AssetType.HELIPAD: 0.4
        }
        
        value = base_values.get(asset_type, 0.5)
        
        # Central positions are generally more valuable
        x, y, z = position
        map_center_x = self.terrain_helper.tc.map_size_m / 2
        map_center_z = self.terrain_helper.tc.map_size_m / 2
        
        distance_from_center = math.sqrt(
            (x - map_center_x)**2 + (z - map_center_z)**2
        )
        
        # Normalize by map size and adjust value
        normalized_distance = distance_from_center / (self.terrain_helper.tc.map_size_m / 2)
        centrality_bonus = max(0, 0.3 * (1.0 - normalized_distance))
        
        return value + centrality_bonus
    
    def _establish_supply_networks(self) -> None:
        """Establish supply line connections between assets."""
        
        # Connect each asset to nearby logistics hubs and other assets
        logistics_hubs = [a for a in self.placed_assets.values() 
                         if a.asset_type == AssetType.LOGISTICS_HUB]
        
        for asset in self.placed_assets.values():
            requirements = AssetRequirements.get_requirements(asset.asset_type)
            
            # Connect to nearest logistics hub within range
            for hub in logistics_hubs:
                distance = math.sqrt(
                    (asset.position[0] - hub.position[0])**2 + 
                    (asset.position[2] - hub.position[2])**2
                )
                
                if distance <= requirements.supply_line_range:
                    asset.supply_line_connections.append(hub.asset_id)
                    if asset.asset_id not in self.supply_network:
                        self.supply_network[asset.asset_id] = []
                    self.supply_network[asset.asset_id].append(hub.asset_id)
    
    def _plan_defensive_positions(self) -> None:
        """Plan defensive positions for high-value assets."""
        
        high_value_assets = [
            a for a in self.placed_assets.values()
            if a.asset_type in [AssetType.MAIN_AIRBASE, AssetType.COMMAND_POST, AssetType.RADAR_SITE]
        ]
        
        for asset in high_value_assets:
            # Generate defensive positions around the asset
            defensive_positions = []
            center = asset.position
            
            # Create defensive ring
            for i in range(6):  # 6 defensive positions
                angle = (2 * math.pi * i) / 6
                distance = 1500  # 1.5km defensive perimeter
                
                def_x = center[0] + distance * math.cos(angle)
                def_z = center[2] + distance * math.sin(angle)
                
                try:
                    def_y = self.terrain_helper.tc.get_terrain_height(def_x, def_z)
                    defensive_positions.append((def_x, def_y, def_z))
                except Exception:
                    continue
            
            asset.defensive_positions = defensive_positions
    
    def get_infrastructure_summary(self) -> Dict[str, Any]:
        """Get comprehensive infrastructure summary."""
        
        summary = {
            "total_assets": len(self.placed_assets),
            "asset_breakdown": {},
            "terrain_suitability": {},
            "construction_difficulty": 0.0,
            "strategic_value": 0.0,
            "supply_network_connectivity": 0.0
        }
        
        # Asset breakdown
        for asset in self.placed_assets.values():
            asset_type = asset.asset_type.value
            summary["asset_breakdown"][asset_type] = summary["asset_breakdown"].get(asset_type, 0) + 1
        
        # Terrain suitability breakdown
        for asset in self.placed_assets.values():
            suitability = asset.terrain_suitability.value
            summary["terrain_suitability"][suitability] = summary["terrain_suitability"].get(suitability, 0) + 1
        
        # Average metrics
        if self.placed_assets:
            total_construction_difficulty = sum(a.construction_difficulty for a in self.placed_assets.values())
            total_strategic_value = sum(a.strategic_value for a in self.placed_assets.values())
            
            summary["construction_difficulty"] = total_construction_difficulty / len(self.placed_assets)
            summary["strategic_value"] = total_strategic_value / len(self.placed_assets)
            
            # Supply network connectivity
            connected_assets = sum(1 for a in self.placed_assets.values() if a.supply_line_connections)
            summary["supply_network_connectivity"] = connected_assets / len(self.placed_assets)
        
        return summary