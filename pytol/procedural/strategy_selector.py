from __future__ import annotations

import random
import math
from dataclasses import dataclass
from typing import List, Tuple

from pytol.terrain.mission_terrain_helper import MissionTerrainHelper
from .spec import TargetBias


@dataclass
class RoutePlan:
    """Complete route with ingress, target, and egress waypoints (x, y, z)."""
    ingress: List[Tuple[float, float, float]]
    egress: List[Tuple[float, float, float]]
    target: Tuple[float, float, float]


@dataclass
class StrategySelector:
    """
    Picks ingress/egress waypoints and a target anchor according to mission
    type, ControlMap and ThreatMap.
    
    Current implementation: simple geometric approach using map bounds and
    terrain-aware height queries. Future: integrate ControlMap/ThreatMap.
    """
    helper: MissionTerrainHelper

    def select(self, mission_type: str, timing_km: Tuple[float, float], rng: random.Random, bias: TargetBias | None = None, preferences: dict | None = None) -> RoutePlan:
        """
        Generate a route plan with ingress, target, and egress waypoints.
        
        Args:
            mission_type: Mission type (strike, cas, intercept, etc.)
            timing_km: (ingress_distance_m, egress_distance_m) from TimingModel
            rng: seeded random generator for reproducible selection
        
        Returns:
            RoutePlan with ingress/target/egress waypoints
        """
        ingress_dist, egress_dist = timing_km
        tc = self.helper.tc
        
        # Map bounds: coordinates use [0, total_map_size] in VTOL VR
        map_size = tc.total_map_size_meters

        # Choose target anywhere on the map, with mission-aware + user prefs scoring
        margin = max(1000.0, map_size * 0.02)  # keep inside edges a bit
        best = None
        prefs = preferences or {}
        avoid_water_flag = prefs.get("avoid_water", True)
        tb = bias or TargetBias()

        def slope_degrees(x: float, z: float) -> float:
            n = tc.get_terrain_normal(x, z)
            return math.degrees(math.acos(max(-1.0, min(1.0, float(n[1])))))

        def score_point(mt: str, x: float, z: float) -> float:
            y = tc.get_terrain_height(x, z)
            # Heuristic: water tends to be near min_height
            if avoid_water_flag and y <= tc.min_height + 0.5:
                return -1e9  # reject likely water
            city = tc.get_city_density(x, z)  # 0..1 (thresholded internally)
            s = slope_degrees(x, z)
            flatness = max(0.0, 1.0 - (s / 30.0))  # favor <=30° slopes
            # Road proximity (0 or 1-ish)
            try:
                info = self.helper.get_nearest_road_point(x, z)  # type: ignore[attr-defined]
                road_bonus = 1.0 if (info and info.get("distance", 9999) < 800.0) else 0.0
            except Exception:
                road_bonus = 0.0
            # Mission-aware preferences
            if mt in ("strike", "sead", "deep_strike"):
                base = 0.7 * city + 0.3 * flatness
            if mt in ("cas", "escort"):
                base = 0.5 * city + 0.3 * flatness + 0.2 * road_bonus
            if mt in ("intercept", "cap"):
                base = 0.7 * (1.0 - city) + 0.3 * flatness
            # Default: balanced
            if mt not in ("strike", "sead", "deep_strike", "cas", "escort", "intercept", "cap"):
                base = 0.5 * (1.0 - city) + 0.5 * flatness
            # Apply numeric bias weights
            score = base + tb.cities * city + tb.open * (1.0 - city) + tb.roads * road_bonus
            if avoid_water_flag and y <= tc.min_height + 0.5:
                score -= max(0.5, tb.water)  # apply at least some penalty
            else:
                # If user actually prefers water areas (tb.water < 0), add a small bonus off-water
                if tb.water < 0:
                    score += (-tb.water) * 0.1
            return score

        # Sample candidates across the whole map and keep the best
        for _ in range(64):
            cx = rng.uniform(margin, map_size - margin)
            cz = rng.uniform(margin, map_size - margin)
            sc = score_point(mission_type, cx, cz)
            # Apply user preferences as additional tilt
            if prefs.get("prefer_cities") is True:
                sc += 0.3 * tc.get_city_density(cx, cz)
            if prefs.get("prefer_open") is True:
                sc += 0.3 * (1.0 - tc.get_city_density(cx, cz))
            if prefs.get("prefer_roads") is True:
                try:
                    info = self.helper.get_nearest_road_point(cx, cz)  # type: ignore[attr-defined]
                    if info and info.get("distance", 9999) < 800.0:
                        sc += 0.2
                except Exception:
                    pass
            if best is None or sc > best[0]:
                cy = tc.get_terrain_height(cx, cz)
                best = (sc, (cx, cy, cz))

        if best is None or best[0] < -1e8:
            # Fallback: pick somewhere near center if all candidates rejected
            offset_range = min(map_size * 0.3, 15000)
            center = map_size / 2.0
            tx = rng.uniform(center - offset_range, center + offset_range)
            tz = rng.uniform(center - offset_range, center + offset_range)
            ty = tc.get_terrain_height(tx, tz)
            target = (tx, ty, tz)
        else:
            target = best[1]
        
        # Ingress: pick a bearing and place waypoint at ingress_dist
        ingress_bearing = rng.uniform(0, 2 * math.pi)
        target_x, target_y, target_z = target
        ingress_x = target_x + ingress_dist * math.cos(ingress_bearing)
        ingress_z = target_z + ingress_dist * math.sin(ingress_bearing)
        # Clamp within bounds with margin
        ingress_x = max(margin, min(map_size - margin, ingress_x))
        ingress_z = max(margin, min(map_size - margin, ingress_z))
        ingress_y = tc.get_terrain_height(ingress_x, ingress_z)
        
        # Egress: opposite side from ingress (180° ±30°)
        egress_bearing = ingress_bearing + math.pi + rng.uniform(-math.pi/6, math.pi/6)
        egress_x = target_x + egress_dist * math.cos(egress_bearing)
        egress_z = target_z + egress_dist * math.sin(egress_bearing)
        # Clamp within bounds with margin
        egress_x = max(margin, min(map_size - margin, egress_x))
        egress_z = max(margin, min(map_size - margin, egress_z))
        egress_y = tc.get_terrain_height(egress_x, egress_z)
        
        ingress = [(ingress_x, ingress_y, ingress_z)]
        egress = [(egress_x, egress_y, egress_z)]
        
        return RoutePlan(ingress=ingress, egress=egress, target=target)
