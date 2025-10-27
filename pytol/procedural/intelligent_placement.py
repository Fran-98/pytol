"""Intelligent unit placement strategies based on terrain and tactical considerations."""

from __future__ import annotations

import math
import random
from typing import List, Tuple
from dataclasses import dataclass

from pytol.terrain.mission_terrain_helper import MissionTerrainHelper
from pytol.misc.math_utils import calculate_slope_from_normal


@dataclass
class PlacementZone:
    """A zone suitable for unit placement."""
    center: Tuple[float, float, float]  # x, y, z
    radius: float
    terrain_type: str  # "urban", "open", "hill", "water"
    defensibility_score: float  # 0..1


class IntelligentPlacer:
    """Places units intelligently based on terrain and tactical doctrine."""
    
    def __init__(self, helper: MissionTerrainHelper):
        self.helper = helper
        self.tc = helper.tc
    
    def find_placement_zones(
        self,
        center: Tuple[float, float, float],
        radius: float,
        num_zones: int,
        rng: random.Random,
        prefer_urban: bool = False,
        prefer_defensive: bool = False
    ) -> List[PlacementZone]:
        """
        Find tactically sound placement zones around a center point.
        
        Args:
            center: (x, y, z) center point
            radius: Search radius in meters
            num_zones: Number of zones to find
            rng: Random number generator
            prefer_urban: Prefer city areas
            prefer_defensive: Prefer elevated/defensive positions
            
        Returns:
            List of PlacementZone objects
        """
        cx, _, cz = center
        zones = []
        attempts = num_zones * 10  # Try multiple times to find good zones
        
        for _ in range(attempts):
            if len(zones) >= num_zones:
                break
            
            # Random position within radius
            angle = rng.uniform(0, 2 * math.pi)
            dist = rng.uniform(radius * 0.3, radius)
            x = cx + dist * math.cos(angle)
            z = cz + dist * math.sin(angle)
            
            try:
                y = self.tc.get_terrain_height(x, z)
            except Exception:
                continue
            
            # Check if valid (not water)
            if y <= self.tc.min_height + 2.0:
                continue
            
            # Score this position
            score = self._score_position(x, z, prefer_urban, prefer_defensive)
            
            if score > 0.3:  # Threshold for acceptability
                terrain_type = self._classify_terrain(x, z)
                zones.append(PlacementZone(
                    center=(x, y, z),
                    radius=50.0,  # Small zone radius
                    terrain_type=terrain_type,
                    defensibility_score=score
                ))
        
        # Sort by score and return best
        zones.sort(key=lambda z: z.defensibility_score, reverse=True)
        return zones[:num_zones]
    
    def _score_position(self, x: float, z: float, prefer_urban: bool, prefer_defensive: bool) -> float:
        """Score a position for tactical placement."""
        score = 0.5  # Base score
        
        # City density
        city = self.tc.get_city_density(x, z)
        if prefer_urban:
            score += 0.3 * city
        else:
            score += 0.1 * (1.0 - city)  # Slight bonus for open areas
        
        # Terrain slope (defensive positions on hills)
        normal = self.tc.get_terrain_normal(x, z)
        slope_deg = calculate_slope_from_normal(normal)
        
        if prefer_defensive:
            # Prefer moderate slopes (5-20 degrees) for defense
            if 5 < slope_deg < 20:
                score += 0.3
            elif slope_deg > 30:
                score -= 0.2  # Too steep
        else:
            # Prefer flat ground for vehicles
            if slope_deg < 10:
                score += 0.2
            elif slope_deg > 25:
                score -= 0.3
        
        # Road proximity (easier to deploy)
        try:
            info = self.helper.get_nearest_road_point(x, z)
            if info and info.get("distance", 9999) < 500:
                score += 0.2
        except Exception:
            pass
        
        return max(0.0, min(1.0, score))
    
    def _classify_terrain(self, x: float, z: float) -> str:
        """Classify terrain type at position."""
        y = self.tc.get_terrain_height(x, z)
        city = self.tc.get_city_density(x, z)
        
        if y <= self.tc.min_height + 2.0:
            return "water"
        elif city > 0.5:
            return "urban"
        elif y > self.tc.max_height * 0.6:
            return "hill"
        else:
            return "open"
    
    def cluster_units(
        self,
        units: List[str],
        zones: List[PlacementZone],
        rng: random.Random
    ) -> List[Tuple[str, Tuple[float, float, float]]]:
        """
        Cluster units into tactical groups within zones.
        
        Args:
            units: List of unit types to place
            zones: Available placement zones
            rng: Random number generator
            
        Returns:
            List of (unit_type, (x, y, z)) tuples
        """
        if not zones:
            return []
        
        placements = []
        units_per_zone = max(1, len(units) // len(zones))
        
        zone_idx = 0
        for i, unit_type in enumerate(units):
            # Rotate through zones
            if i > 0 and i % units_per_zone == 0:
                zone_idx = (zone_idx + 1) % len(zones)
            
            zone = zones[zone_idx]
            zx, zy, zz = zone.center
            
            # Place within zone radius with some randomness
            angle = rng.uniform(0, 2 * math.pi)
            dist = rng.uniform(0, zone.radius)
            x = zx + dist * math.cos(angle)
            z = zz + dist * math.sin(angle)
            
            try:
                y = self.tc.get_terrain_height(x, z)
                placements.append((unit_type, (x, y, z)))
            except Exception:
                # Fallback to zone center
                placements.append((unit_type, zone.center))
        
        return placements
    
    def place_sam_network(
        self,
        center: Tuple[float, float, float],
        radius: float,
        num_sam_sites: int,
        rng: random.Random
    ) -> List[Tuple[str, Tuple[float, float, float]]]:
        """
        Place SAM sites in a defensive network with overlapping coverage.
        
        Returns list of ("SAM" or "Radar", position) tuples.
        """
        placements = []
        cx, _, cz = center
        
        # Place central radar
        try:
            cy = self.tc.get_terrain_height(cx, cz)
            placements.append(("Radar", (cx, cy, cz)))
        except Exception:
            pass
        
        # Place SAM sites in a ring around center
        for i in range(num_sam_sites):
            angle = (2 * math.pi * i / num_sam_sites) + rng.uniform(-0.3, 0.3)
            dist = radius * rng.uniform(0.5, 0.8)
            x = cx + dist * math.cos(angle)
            z = cz + dist * math.sin(angle)
            
            try:
                y = self.tc.get_terrain_height(x, z)
                if y > self.tc.min_height + 2.0:
                    placements.append(("SAM", (x, y, z)))
            except Exception:
                continue
        
        return placements
