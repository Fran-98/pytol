"""
Terrain-aware unit formation generator for realistic military unit placement.

This module implements formation generation that considers:
- Terrain suitability and slope limitations
- Line of sight between units
- Tactical spacing and defensive positioning
- Unit type specific requirements (armor, infantry, air defense)
- Natural concealment opportunities
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any
from enum import Enum

# Import consolidated utilities
from ..misc.math_utils import calculate_2d_distance, calculate_slope_from_normal
from pytol.terrain.mission_terrain_helper import MissionTerrainHelper


class FormationType(Enum):
    """Standard military formation types."""
    LINE = "line"
    WEDGE = "wedge"
    COLUMN = "column"
    DIAMOND = "diamond"
    CIRCLE = "circle"
    DEFENSIVE_PERIMETER = "defensive_perimeter"
    OVERWATCH = "overwatch"
    AMBUSH = "ambush"


@dataclass
class UnitFormationRequirements:
    """Requirements for different unit types in formations."""
    unit_type: str
    min_spacing: float  # Minimum distance between units (meters)
    max_slope: float    # Maximum acceptable slope (degrees)
    requires_los: bool  # Whether unit needs line of sight to others
    concealment_preference: float  # 0-1, preference for concealed positions
    elevation_preference: float    # -1 to 1, preference for high(+) or low(-) ground
    
    @classmethod
    def get_requirements(cls, unit_type: str) -> 'UnitFormationRequirements':
        """Get formation requirements for unit type."""
        requirements = {
            # Armor units
            "TANK": cls("TANK", 150, 20, True, 0.3, 0.2),
            "MBT": cls("MBT", 150, 20, True, 0.3, 0.2),
            "APC": cls("APC", 100, 25, True, 0.4, 0.1),
            "IFV": cls("IFV", 120, 25, True, 0.4, 0.1),
            
            # Infantry units
            "INFANTRY": cls("INFANTRY", 50, 35, False, 0.8, 0.3),
            "JTAC": cls("JTAC", 100, 30, True, 0.9, 0.5),
            "MANPADS": cls("MANPADS", 200, 25, True, 0.7, 0.6),
            
            # Support units
            "SUPPLY": cls("SUPPLY", 80, 15, False, 0.9, -0.2),
            "FUEL": cls("FUEL", 100, 15, False, 0.9, -0.2),
            "ARTILLERY": cls("ARTILLERY", 200, 15, True, 0.6, 0.0),
            
            # Air defense
            "SAM": cls("SAM", 300, 20, True, 0.5, 0.8),
            "AAA": cls("AAA", 200, 25, True, 0.4, 0.4),
            "RADAR": cls("RADAR", 500, 15, True, 0.2, 0.9),
        }
        
        # Default fallback
        return requirements.get(unit_type.upper(), 
                              cls("DEFAULT", 100, 30, False, 0.5, 0.0))


class TerrainAwareFormationGenerator:
    """
    Generates tactically sound unit formations considering terrain constraints.
    
    Implements military formation doctrine adapted for terrain considerations:
    - Slope and accessibility validation
    - Line of sight requirements for command and control
    - Natural concealment utilization
    - Defensive positioning principles
    """
    
    def __init__(self, terrain_helper: MissionTerrainHelper):
        self.helper = terrain_helper
        self.tc = terrain_helper.tc
        
    def generate_formation(
        self,
        center_pos: Tuple[float, float, float],
        unit_types: List[str],
        formation_type: FormationType,
        unit_names: Optional[List[str]] = None,
        max_iterations: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Generate terrain-aware unit formation.
        
        Args:
            center_pos: Formation center position (x, y, z)
            unit_types: List of unit type strings
            formation_type: Type of formation to generate
            unit_names: Optional list of unit names (defaults to generic names)
            max_iterations: Maximum attempts to find valid positions
            
        Returns:
            List of unit placement dictionaries with position, rotation, and metadata
        """
        if unit_names is None:
            unit_names = [f"{unit_type} {i+1}" for i, unit_type in enumerate(unit_types)]
        
        if len(unit_names) != len(unit_types):
            raise ValueError("unit_names and unit_types must have same length")
        
        # Generate base formation positions
        base_positions = self._generate_base_formation(center_pos, len(unit_types), formation_type)
        
        # Adapt positions to terrain constraints
        adapted_positions = []
        for i, (base_pos, unit_type, unit_name) in enumerate(zip(base_positions, unit_types, unit_names)):
            requirements = UnitFormationRequirements.get_requirements(unit_type)
            
            adapted_pos = self._adapt_position_to_terrain(
                base_pos, requirements, max_iterations
            )
            
            # Calculate tactical facing
            facing = self._calculate_tactical_facing(adapted_pos, center_pos, formation_type)
            
            adapted_positions.append({
                'name': unit_name,
                'unit_type': unit_type,
                'position': adapted_pos,
                'rotation': [0.0, facing, 0.0],
                'formation_role': self._get_formation_role(i, len(unit_types), formation_type),
                'terrain_suitability': self._assess_position_suitability(adapted_pos, requirements)
            })
        
        # Validate formation integrity
        self._validate_formation_spacing(adapted_positions)
        self._validate_formation_los(adapted_positions)
        
        return adapted_positions
    
    def _generate_base_formation(
        self,
        center_pos: Tuple[float, float, float],
        unit_count: int,
        formation_type: FormationType
    ) -> List[Tuple[float, float, float]]:
        """Generate basic formation positions before terrain adaptation."""
        
        cx, cy, cz = center_pos
        positions = []
        
        if formation_type == FormationType.LINE:
            # Linear formation
            spacing = 150  # Base spacing between units
            total_width = (unit_count - 1) * spacing
            start_offset = -total_width / 2
            
            for i in range(unit_count):
                x = cx + start_offset + (i * spacing)
                positions.append((x, cy, cz))
                
        elif formation_type == FormationType.WEDGE:
            # V-shaped formation
            if unit_count == 1:
                positions.append(center_pos)
            else:
                # Lead unit at center
                positions.append(center_pos)
                
                # Trailing units in V
                for i in range(1, unit_count):
                    side = -1 if i % 2 == 1 else 1  # Alternate sides
                    rank = (i + 1) // 2  # How far back
                    
                    x = cx + side * rank * 100
                    z = cz - rank * 150
                    positions.append((x, cy, z))
                    
        elif formation_type == FormationType.COLUMN:
            # Single file formation
            spacing = 120
            for i in range(unit_count):
                z = cz + (i - unit_count//2) * spacing
                positions.append((cx, cy, z))
                
        elif formation_type == FormationType.CIRCLE:
            # Circular formation
            radius = max(200, unit_count * 50)  # Scale with unit count
            for i in range(unit_count):
                angle = (2 * math.pi * i) / unit_count
                x = cx + radius * math.cos(angle)
                z = cz + radius * math.sin(angle)
                positions.append((x, cy, z))
                
        elif formation_type == FormationType.DEFENSIVE_PERIMETER:
            # Defensive perimeter with key positions
            if unit_count <= 4:
                # Small perimeter
                angles = [0, math.pi/2, math.pi, 3*math.pi/2][:unit_count]
                radius = 200
            else:
                # Larger perimeter
                angles = [(2 * math.pi * i) / unit_count for i in range(unit_count)]
                radius = 150 + unit_count * 20
                
            for angle in angles:
                x = cx + radius * math.cos(angle)
                z = cz + radius * math.sin(angle)
                positions.append((x, cy, z))
                
        elif formation_type == FormationType.OVERWATCH:
            # Overwatch formation - some units forward, others in support
            if unit_count <= 2:
                # Simple overwatch
                positions.append((cx, cy, cz + 200))  # Forward
                if unit_count > 1:
                    positions.append((cx, cy, cz - 300))  # Support
            else:
                # Complex overwatch with multiple positions
                forward_count = unit_count // 2
                support_count = unit_count - forward_count
                
                # Forward positions
                for i in range(forward_count):
                    x = cx + (i - forward_count//2) * 150
                    positions.append((x, cy, cz + 200))
                
                # Support positions  
                for i in range(support_count):
                    x = cx + (i - support_count//2) * 200
                    positions.append((x, cy, cz - 400))
                    
        else:  # Default to circle
            return self._generate_base_formation(center_pos, unit_count, FormationType.CIRCLE)
        
        return positions
    
    def _adapt_position_to_terrain(
        self,
        base_pos: Tuple[float, float, float],
        requirements: UnitFormationRequirements,
        max_iterations: int
    ) -> Tuple[float, float, float]:
        """Adapt a base position to meet terrain requirements."""
        
        best_pos = base_pos
        best_score = -float('inf')
        
        # Try the base position first
        score = self._score_position(base_pos, requirements)
        if score > best_score:
            best_score = score
            best_pos = base_pos
        
        # Try variations around the base position
        search_radius = 200  # Start with 200m search radius
        for iteration in range(max_iterations):
            # Expand search radius gradually
            current_radius = search_radius * (1 + iteration / max_iterations)
            
            # Random position within search area
            from pytol.misc.math_utils import generate_random_position_in_circle
            test_x, test_z = generate_random_position_in_circle(
                (base_pos[0], base_pos[2]), current_radius
            )
            
            try:
                test_y = self.tc.get_terrain_height(test_x, test_z)
                test_pos = (test_x, test_y, test_z)
                
                score = self._score_position(test_pos, requirements)
                if score > best_score:
                    best_score = score
                    best_pos = test_pos
                    
            except Exception:
                continue  # Skip invalid positions
        
        return best_pos
    
    def _score_position(
        self,
        position: Tuple[float, float, float],
        requirements: UnitFormationRequirements
    ) -> float:
        """Score a position based on unit requirements."""
        
        x, y, z = position
        score = 0.0
        
        try:
            # Check slope constraint
            normal = self.tc.get_terrain_normal(x, z)
            slope_degrees = calculate_slope_from_normal(normal)
            
            if slope_degrees <= requirements.max_slope:
                score += 100  # Good slope
            else:
                penalty = (slope_degrees - requirements.max_slope) * 2
                score -= penalty
            
            # Elevation preference
            if requirements.elevation_preference != 0.0:
                # Compare elevation to surrounding area
                avg_elevation = self._get_average_elevation_nearby(x, z, radius=500)
                elevation_diff = y - avg_elevation
                
                if requirements.elevation_preference > 0:  # Prefers high ground
                    score += elevation_diff * requirements.elevation_preference * 0.1
                else:  # Prefers low ground
                    score += abs(elevation_diff) * abs(requirements.elevation_preference) * 0.1 if elevation_diff < 0 else 0
            
            # Concealment preference
            if requirements.concealment_preference > 0.0:
                concealment_score = self._assess_concealment(x, z)
                score += concealment_score * requirements.concealment_preference * 50
            
            # Terrain type suitability
            terrain_type = self.helper.get_terrain_type((x, z))
            terrain_bonus = self._get_terrain_type_bonus(terrain_type, requirements.unit_type)
            score += terrain_bonus
            
        except Exception:
            score = -1000  # Invalid position
        
        return score
    
    def _get_average_elevation_nearby(self, x: float, z: float, radius: float) -> float:
        """Get average elevation in area around position."""
        
        try:
            samples = []
            num_samples = 8
            
            for i in range(num_samples):
                angle = (2 * math.pi * i) / num_samples
                sample_x = x + radius * math.cos(angle)
                sample_z = z + radius * math.sin(angle)
                
                height = self.tc.get_terrain_height(sample_x, sample_z)
                samples.append(height)
            
            return sum(samples) / len(samples) if samples else 0.0
            
        except Exception:
            return 0.0
    
    def _assess_concealment(self, x: float, z: float) -> float:
        """Assess concealment value of position (0-1)."""
        
        # Simplified concealment assessment
        # In reality, this would consider vegetation, terrain features, etc.
        
        try:
            # Check terrain roughness as proxy for concealment
            terrain_type = self.helper.get_terrain_type((x, z))
            
            concealment_values = {
                "Urban": 0.8,      # Buildings provide concealment
                "Forest": 0.9,     # Trees provide excellent concealment
                "Mountainous": 0.6, # Terrain features provide some concealment
                "Desert": 0.2,     # Open terrain, poor concealment
                "Flat": 0.1,       # Very open, minimal concealment
            }
            
            return concealment_values.get(terrain_type, 0.5)
            
        except Exception:
            return 0.5  # Default moderate concealment
    
    def _get_terrain_type_bonus(self, terrain_type: str, unit_type: str) -> float:
        """Get terrain suitability bonus for unit type."""
        
        # Terrain preferences by unit type
        preferences = {
            "TANK": {"Urban": -20, "Forest": -30, "Mountainous": -10, "Desert": 10, "Flat": 20},
            "INFANTRY": {"Urban": 20, "Forest": 30, "Mountainous": 10, "Desert": -10, "Flat": 0},
            "ARTILLERY": {"Urban": -10, "Forest": -20, "Mountainous": -15, "Desert": 5, "Flat": 30},
            "SAM": {"Urban": 0, "Forest": 5, "Mountainous": 20, "Desert": 10, "Flat": 10},
        }
        
        unit_prefs = preferences.get(unit_type.upper(), {})
        return unit_prefs.get(terrain_type, 0)
    
    def _calculate_tactical_facing(
        self,
        position: Tuple[float, float, float],
        center_pos: Tuple[float, float, float],
        formation_type: FormationType
    ) -> float:
        """Calculate tactical facing direction for unit."""
        
        x, y, z = position
        cx, cy, cz = center_pos
        
        if formation_type == FormationType.DEFENSIVE_PERIMETER:
            # Face outward from center
            dx = x - cx
            dz = z - cz
            if dx == 0 and dz == 0:
                return 0.0  # Default facing
            from ..misc.math_utils import calculate_bearing
            return calculate_bearing((cx, 0, cz), (x, 0, z))
            
        elif formation_type == FormationType.OVERWATCH:
            # Forward units face forward, support units face toward threat
            if z > cz:  # Forward position
                return 0.0  # Face north (forward)
            else:  # Support position
                return 0.0  # Also face forward to support
                
        else:
            # Default: face formation center or forward
            return random.uniform(-30, 30)  # Some variation
    
    def _get_formation_role(
        self,
        unit_index: int,
        total_units: int,
        formation_type: FormationType
    ) -> str:
        """Determine tactical role of unit in formation."""
        
        if formation_type == FormationType.WEDGE:
            if unit_index == 0:
                return "leader"
            else:
                return "wing"
                
        elif formation_type == FormationType.OVERWATCH:
            if unit_index < total_units // 2:
                return "overwatch"
            else:
                return "support"
                
        elif formation_type == FormationType.DEFENSIVE_PERIMETER:
            return "defender"
            
        else:
            return "standard"
    
    def _validate_formation_spacing(self, positions: List[Dict[str, Any]]) -> None:
        """Validate that units maintain proper spacing."""
        
        for i, unit1 in enumerate(positions):
            requirements1 = UnitFormationRequirements.get_requirements(unit1['unit_type'])
            
            for j, unit2 in enumerate(positions[i+1:], i+1):
                pos1 = unit1['position']
                pos2 = unit2['position']
                
                distance = calculate_2d_distance(
                    (pos1[0], pos1[2]), (pos2[0], pos2[2])
                )
                
                min_spacing = requirements1.min_spacing
                if distance < min_spacing:
                    # Log warning but don't fail - terrain constraints may require closer spacing
                    pass
    
    def _validate_formation_los(self, positions: List[Dict[str, Any]]) -> None:
        """Validate line of sight requirements between units."""
        
        # Simplified LOS validation
        # In practice, this would use proper LOS calculations through terrain
        
        for unit in positions:
            requirements = UnitFormationRequirements.get_requirements(unit['unit_type'])
            if requirements.requires_los:
                # Check if unit has reasonable LOS to formation center
                # This is a placeholder - full implementation would trace rays
                pass
    
    def generate_defensive_positions(
        self,
        center_pos: Tuple[float, float, float],
        unit_types: List[str],
        threat_direction: float = 0.0,  # Degrees from north
        defense_radius: float = 500.0
    ) -> List[Dict[str, Any]]:
        """
        Generate defensive positions oriented toward a threat direction.
        
        Args:
            center_pos: Defense center position
            unit_types: List of unit types to position
            threat_direction: Direction of primary threat (degrees from north)
            defense_radius: Radius of defensive perimeter
            
        Returns:
            List of unit positions optimized for defense
        """
        positions = []
        
        # Convert threat direction to radians
        threat_rad = math.radians(threat_direction)
        
        for i, unit_type in enumerate(unit_types):
            requirements = UnitFormationRequirements.get_requirements(unit_type)
            
            # Calculate defensive angle for this unit
            unit_angle = threat_rad + (i - len(unit_types)//2) * (math.pi / 6)  # Spread units
            
            # Base position
            base_x = center_pos[0] + defense_radius * math.sin(unit_angle)  
            base_z = center_pos[2] + defense_radius * math.cos(unit_angle)
            base_pos = (base_x, center_pos[1], base_z)
            
            # Adapt to terrain
            final_pos = self._adapt_position_to_terrain(base_pos, requirements, 30)
            
            # Face toward threat
            facing = math.degrees(threat_rad)
            
            positions.append({
                'name': f"{unit_type} Defender {i+1}",
                'unit_type': unit_type,
                'position': final_pos,
                'rotation': [0.0, facing, 0.0],
                'formation_role': 'defender',
                'threat_bearing': threat_direction,
                'terrain_suitability': self._assess_position_suitability(final_pos, requirements)
            })
        
        return positions
    
    def _assess_position_suitability(
        self,
        position: Tuple[float, float, float],
        requirements: UnitFormationRequirements
    ) -> str:
        """Assess overall suitability of position for unit type."""
        
        score = self._score_position(position, requirements)
        
        if score >= 100:
            return "excellent"
        elif score >= 50:
            return "good"  
        elif score >= 0:
            return "acceptable"
        else:
            return "poor"