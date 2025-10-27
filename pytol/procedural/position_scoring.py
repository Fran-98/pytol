"""
Unified Position Scoring Framework for pytol library.

Consolidates the multiple _score_*_position() functions scattered across files into
a coherent, extensible framework with consistent scoring logic.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, List, Optional
from dataclasses import dataclass

# Import consolidated utilities
from ..misc.math_utils import calculate_3d_distance, calculate_slope_from_normal
from ..terrain.mission_terrain_helper import MissionTerrainHelper


@dataclass
class PositionRequirements:
    """Base requirements for position scoring."""
    min_altitude: float = 0
    max_altitude: float = 3000
    max_slope: float = 15  # degrees
    min_clearance: float = 100  # meters from obstacles
    requires_road_access: bool = False
    max_road_distance: float = 5000  # meters
    threat_tolerance: float = 0.5  # 0-1, higher = more tolerant
    

@dataclass
class PositionScore:
    """Comprehensive position scoring result."""
    total_score: float
    terrain_score: float
    accessibility_score: float
    strategic_score: float
    threat_score: float
    detailed_breakdown: Dict[str, Any]
    meets_requirements: bool
    issues: List[str]


class BasePositionScorer(ABC):
    """Abstract base class for position scoring systems."""
    
    def __init__(self, terrain_helper: MissionTerrainHelper):
        self.terrain_helper = terrain_helper
        self.tc = terrain_helper.tc
    
    @abstractmethod
    def score_position(
        self, 
        position: Tuple[float, float, float], 
        requirements: PositionRequirements
    ) -> PositionScore:
        """Score a position based on specific criteria."""
        pass
    
    def _base_terrain_score(
        self, 
        position: Tuple[float, float, float], 
        requirements: PositionRequirements
    ) -> Tuple[float, List[str]]:
        """Calculate base terrain suitability score."""
        x, y, z = position
        score = 0.0
        issues = []
        
        try:
            # 1. Altitude check
            if requirements.min_altitude <= y <= requirements.max_altitude:
                score += 25
            else:
                penalty = min(abs(y - requirements.min_altitude), 
                            abs(y - requirements.max_altitude)) / 100
                score -= penalty
                issues.append(f"Altitude {y:.0f}m outside range {requirements.min_altitude}-{requirements.max_altitude}m")
            
            # 2. Slope check
            try:
                normal = self.tc.get_terrain_normal(x, z)
                slope = calculate_slope_from_normal(normal)
                
                if slope <= requirements.max_slope:
                    score += 25 - slope  # Flatter is better
                else:
                    score -= (slope - requirements.max_slope) * 2
                    issues.append(f"Slope {slope:.1f}° exceeds maximum {requirements.max_slope}°")
            except Exception:
                issues.append("Could not determine slope")
            
            # 3. Terrain type assessment
            terrain_type = self.terrain_helper.get_terrain_type(position)
            terrain_bonuses = self._get_terrain_type_bonus(terrain_type)
            score += terrain_bonuses
            
        except Exception as e:
            issues.append(f"Terrain analysis error: {e}")
            score = -100
        
        return score, issues
    
    def _accessibility_score(
        self, 
        position: Tuple[float, float, float], 
        requirements: PositionRequirements
    ) -> Tuple[float, List[str]]:
        """Calculate accessibility score."""
        x, y, z = position
        score = 0.0
        issues = []
        
        if requirements.requires_road_access:
            try:
                road_point = self.terrain_helper.get_nearest_road_point(x, z)
                if road_point and road_point.get('distance', float('inf')) < requirements.max_road_distance:
                    distance = road_point['distance']
                    # Closer to road = better score
                    score += 25 * (1 - distance / requirements.max_road_distance)
                else:
                    score -= 20
                    issues.append(f"No road access within {requirements.max_road_distance/1000:.1f}km")
            except Exception:
                issues.append("Could not assess road access")
        else:
            score += 10  # Small bonus for not requiring roads
        
        return score, issues
    
    def _strategic_score(
        self, 
        position: Tuple[float, float, float], 
        center: Optional[Tuple[float, float, float]] = None
    ) -> float:
        """Calculate strategic positioning score."""
        x, y, z = position
        score = 0.0
        
        # Distance from map edges (prefer central positions)
        try:
            map_size = getattr(self.tc, 'map_size_m', 100000)  # Default 100km
            edge_distances = [x, z, map_size - x, map_size - z]
            min_edge_distance = min(edge_distances)
            
            if min_edge_distance > 20000:  # >20km from edge
                score += 15
            elif min_edge_distance > 10000:  # >10km from edge
                score += 10
            elif min_edge_distance < 2000:  # <2km from edge
                score -= 10
        except Exception:
            pass
        
        # Elevation advantage
        if y > 500:  # Some elevation is strategic
            score += min(y / 100, 10)  # Cap at 10 points
        
        return score
    
    def _threat_exposure_score(
        self, 
        position: Tuple[float, float, float], 
        requirements: PositionRequirements
    ) -> float:
        """Calculate threat exposure score."""
        # Use the threat exposure calculation from mission helper
        exposure = self.terrain_helper._calculate_threat_exposure(position)
        
        # Convert exposure to score (lower exposure = higher score)
        max_score = 20
        tolerance_factor = requirements.threat_tolerance
        
        # More tolerant positions accept higher exposure with less penalty
        adjusted_exposure = exposure * (1 - tolerance_factor * 0.5)
        score = max_score * (1 - adjusted_exposure)
        
        return score
    
    @abstractmethod
    def _get_terrain_type_bonus(self, terrain_type: str) -> float:
        """Get terrain type bonus - must be overridden by subclasses."""
        pass


class AirbaseScorer(BasePositionScorer):
    """Scorer for airbase positions."""
    
    def score_position(
        self, 
        position: Tuple[float, float, float], 
        requirements: PositionRequirements
    ) -> PositionScore:
        """Score airbase position."""
        
        # Use the consolidated airbase assessment from mission helper
        runway_length = getattr(requirements, 'runway_length', 3000)
        assessment = self.terrain_helper.assess_airbase_suitability(position, runway_length)
        
        # Convert assessment to our scoring format
        terrain_score = assessment['overall_score'] * 5  # Scale up
        accessibility_score, access_issues = self._accessibility_score(position, requirements)
        strategic_score = self._strategic_score(position)
        threat_score = self._threat_exposure_score(position, requirements)
        
        total_score = terrain_score + accessibility_score + strategic_score + threat_score
        
        # Check if meets requirements
        meets_requirements = (
            assessment['terrain_suitable'] and 
            assessment['space_available'] and
            len(access_issues) == 0
        )
        
        return PositionScore(
            total_score=total_score,
            terrain_score=terrain_score,
            accessibility_score=accessibility_score,
            strategic_score=strategic_score,
            threat_score=threat_score,
            detailed_breakdown=assessment,
            meets_requirements=meets_requirements,
            issues=assessment.get('issues', []) + access_issues
        )
    
    def _get_terrain_type_bonus(self, terrain_type: str) -> float:
        """Airbase terrain type bonuses."""
        bonuses = {
            'flat': 15,      # Perfect for runways
            'desert': 12,    # Good hard surface
            'rocky': 8,      # Acceptable with work
            'hilly': -5,     # Challenging
            'forested': -15, # Requires clearing
            'urban': -20,    # Not suitable
            'water': -50     # Impossible
        }
        return bonuses.get(terrain_type.lower(), 0)


class DefensivePositionScorer(BasePositionScorer):
    """Scorer for defensive positions (SAM, radar, etc.)."""
    
    def __init__(self, terrain_helper: MissionTerrainHelper, system_type: str = 'generic'):
        super().__init__(terrain_helper)
        self.system_type = system_type
    
    def score_position(
        self, 
        position: Tuple[float, float, float], 
        requirements: PositionRequirements
    ) -> PositionScore:
        """Score defensive position."""
        
        terrain_score, terrain_issues = self._base_terrain_score(position, requirements)
        accessibility_score, access_issues = self._accessibility_score(position, requirements)
        strategic_score = self._strategic_score(position)
        threat_score = self._threat_exposure_score(position, requirements)
        
        # Add system-specific bonuses
        system_bonus = self._get_system_specific_bonus(position)
        terrain_score += system_bonus
        
        total_score = terrain_score + accessibility_score + strategic_score + threat_score
        
        meets_requirements = len(terrain_issues + access_issues) == 0
        
        return PositionScore(
            total_score=total_score,
            terrain_score=terrain_score,
            accessibility_score=accessibility_score,
            strategic_score=strategic_score,
            threat_score=threat_score,
            detailed_breakdown={
                'system_type': self.system_type,
                'system_bonus': system_bonus
            },
            meets_requirements=meets_requirements,
            issues=terrain_issues + access_issues
        )
    
    def _get_terrain_type_bonus(self, terrain_type: str) -> float:
        """Defensive position terrain bonuses."""
        bonuses = {
            'rocky': 12,     # Excellent for fixed positions
            'hilly': 10,     # Good elevation and concealment
            'forested': 6,   # Good concealment
            'flat': 4,       # Easy construction but exposed
            'desert': 2,     # Open but stable
            'urban': -5,     # Vulnerable to indirect fire
            'water': -30     # Generally unsuitable
        }
        return bonuses.get(terrain_type.lower(), 0)
    
    def _get_system_specific_bonus(self, position: Tuple[float, float, float]) -> float:
        """System-specific positioning bonuses."""
        x, y, z = position
        bonus = 0
        
        if self.system_type == 'radar':
            # Radars need elevation and clear lines of sight
            bonus += min(y / 50, 15)  # Up to 15 points for elevation
            
        elif self.system_type == 'sam':
            # SAMs need balance of concealment and coverage
            bonus += min(y / 100, 8)  # Moderate elevation bonus
            
        elif self.system_type == 'aaa':
            # AAA needs mobility and clear fields of fire
            if y < 200:  # Prefer lower altitudes for mobility  
                bonus += 5
                
        elif self.system_type == 'c2':
            # Command posts need protection and communications
            bonus += min(y / 75, 10)  # Elevation for comms
            
        return bonus


class TacticalPositionScorer(BasePositionScorer):
    """Scorer for tactical positions (overwatch, ambush, support)."""
    
    def __init__(self, terrain_helper: MissionTerrainHelper, position_type: str = 'generic'):
        super().__init__(terrain_helper)
        self.position_type = position_type
    
    def score_position(
        self, 
        position: Tuple[float, float, float], 
        requirements: PositionRequirements
    ) -> PositionScore:
        """Score tactical position."""
        
        terrain_score, terrain_issues = self._base_terrain_score(position, requirements)
        accessibility_score, access_issues = self._accessibility_score(position, requirements)
        strategic_score = self._strategic_score(position)
        threat_score = self._threat_exposure_score(position, requirements)
        
        # Add tactical bonuses
        tactical_bonus = self._get_tactical_bonus(position)
        strategic_score += tactical_bonus
        
        total_score = terrain_score + accessibility_score + strategic_score + threat_score
        
        meets_requirements = len(terrain_issues + access_issues) == 0
        
        return PositionScore(
            total_score=total_score,
            terrain_score=terrain_score,
            accessibility_score=accessibility_score,
            strategic_score=strategic_score,
            threat_score=threat_score,
            detailed_breakdown={
                'position_type': self.position_type,
                'tactical_bonus': tactical_bonus
            },
            meets_requirements=meets_requirements,
            issues=terrain_issues + access_issues
        )
    
    def _get_terrain_type_bonus(self, terrain_type: str) -> float:
        """Tactical position terrain bonuses."""
        base_bonuses = {
            'rocky': 8,
            'hilly': 10,
            'forested': 12,
            'urban': 3,
            'flat': 2,
            'desert': 4,
            'water': -20
        }
        
        # Adjust based on position type
        if self.position_type == 'overwatch':
            # Overwatch prefers elevation
            base_bonuses['hilly'] += 5
            base_bonuses['rocky'] += 3
        elif self.position_type == 'ambush':
            # Ambush prefers concealment
            base_bonuses['forested'] += 5
            base_bonuses['rocky'] += 3
        elif self.position_type == 'support':
            # Support prefers accessibility
            base_bonuses['flat'] += 3
            base_bonuses['urban'] += 5
        
        return base_bonuses.get(terrain_type.lower(), 0)
    
    def _get_tactical_bonus(self, position: Tuple[float, float, float]) -> float:
        """Tactical positioning bonus."""
        x, y, z = position
        bonus = 0
        
        if self.position_type == 'overwatch':
            # Overwatch benefits from elevation
            bonus += min(y / 25, 20)
            
        elif self.position_type == 'ambush':
            # Ambush benefits from moderate elevation and concealment
            if 50 < y < 500:  # Sweet spot for ambush positions
                bonus += 15
                
        elif self.position_type == 'support':
            # Support positions benefit from central location and access
            # (handled by accessibility score)
            bonus += 5
            
        elif self.position_type == 'rally_point':
            # Rally points need to be accessible but protected
            if y < 300:  # Not too high
                bonus += 10
        
        return bonus


class LogisticsScorer(BasePositionScorer):
    """Scorer for logistics positions."""
    
    def score_position(
        self, 
        position: Tuple[float, float, float], 
        requirements: PositionRequirements
    ) -> PositionScore:
        """Score logistics position."""
        
        # Logistics heavily weights road access
        requirements.requires_road_access = True
        requirements.max_road_distance = 2000  # Stricter road requirement
        
        terrain_score, terrain_issues = self._base_terrain_score(position, requirements)
        accessibility_score, access_issues = self._accessibility_score(position, requirements)
        strategic_score = self._strategic_score(position)
        threat_score = self._threat_exposure_score(position, requirements)
        
        # Logistics gets extra accessibility weight
        accessibility_score *= 1.5
        
        total_score = terrain_score + accessibility_score + strategic_score + threat_score
        
        meets_requirements = len(terrain_issues + access_issues) == 0
        
        return PositionScore(
            total_score=total_score,
            terrain_score=terrain_score,
            accessibility_score=accessibility_score,
            strategic_score=strategic_score,
            threat_score=threat_score,
            detailed_breakdown={'logistics_focus': True},
            meets_requirements=meets_requirements,
            issues=terrain_issues + access_issues
        )
    
    def _get_terrain_type_bonus(self, terrain_type: str) -> float:
        """Logistics terrain bonuses."""
        bonuses = {
            'flat': 15,      # Easy vehicle access
            'urban': 10,     # Good infrastructure
            'rocky': 5,      # Stable but harder access
            'desert': 8,     # Open but challenging
            'hilly': -2,     # Difficult access
            'forested': -8,  # Very difficult access
            'water': -40     # Impossible
        }
        return bonuses.get(terrain_type.lower(), 0)


def create_scorer(
    scorer_type: str, 
    terrain_helper: MissionTerrainHelper, 
    **kwargs
) -> BasePositionScorer:
    """
    Factory function to create appropriate scorer.
    
    Args:
        scorer_type: Type of scorer ('airbase', 'defensive', 'tactical', 'logistics')
        terrain_helper: MissionTerrainHelper instance
        **kwargs: Additional arguments for specific scorers
        
    Returns:
        Appropriate scorer instance
    """
    if scorer_type == 'airbase':
        return AirbaseScorer(terrain_helper)
    elif scorer_type == 'defensive':
        system_type = kwargs.get('system_type', 'generic')
        return DefensivePositionScorer(terrain_helper, system_type)
    elif scorer_type == 'tactical':
        position_type = kwargs.get('position_type', 'generic')
        return TacticalPositionScorer(terrain_helper, position_type)
    elif scorer_type == 'logistics':
        return LogisticsScorer(terrain_helper)
    else:
        raise ValueError(f"Unknown scorer type: {scorer_type}")


def find_best_positions(
    scorer: BasePositionScorer,
    search_center: Tuple[float, float, float],
    search_radius: float,
    requirements: PositionRequirements,
    count: int = 1,
    min_separation: float = 1000,
    max_attempts: int = 100
) -> List[Tuple[Tuple[float, float, float], PositionScore]]:
    """
    Find best positions using the given scorer.
    
    Args:
        scorer: Position scorer to use
        search_center: Center of search area
        search_radius: Search radius in meters
        requirements: Position requirements
        count: Number of positions to find
        min_separation: Minimum distance between positions
        max_attempts: Maximum search attempts
        
    Returns:
        List of (position, score) tuples sorted by score
    """
    candidates = []
    attempts = 0
    
    while len(candidates) < count and attempts < max_attempts:
        attempts += 1
        
        # Generate random position
        from ..misc.math_utils import generate_random_position_in_circle
        x_2d, z_2d = generate_random_position_in_circle(
            (search_center[0], search_center[2]), 
            search_radius
        )
        
        # Get terrain height
        y = scorer.terrain_helper.get_terrain_height_safe(x_2d, z_2d)
        position = (x_2d, y, z_2d)
        
        # Check separation from existing candidates
        too_close = False
        for existing_pos, _ in candidates:
            if calculate_3d_distance(position, existing_pos) < min_separation:
                too_close = True
                break
        
        if too_close:
            continue
        
        # Score position
        score_result = scorer.score_position(position, requirements)
        
        # Only keep positions that meet basic requirements
        if score_result.meets_requirements and score_result.total_score > 0:
            candidates.append((position, score_result))
    
    # Sort by score and return best positions
    candidates.sort(key=lambda x: x[1].total_score, reverse=True)
    return candidates[:count]