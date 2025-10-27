"""
Mathematical utility functions for pytol library.

Consolidates common mathematical operations that were duplicated across multiple files.
"""
import math
import random
import numpy as np
from typing import Tuple, List, Optional, Union

# Type definitions for positions
Position2D = Tuple[float, float]
Position3D = Tuple[float, float, float]
PositionType = Union[Position2D, Position3D]


def calculate_2d_distance(pos1: Position2D, pos2: Position2D) -> float:
    """
    Calculate 2D Euclidean distance between two points.
    
    Args:
        pos1: First position (x, z)
        pos2: Second position (x, z)
        
    Returns:
        Distance in meters
        
    Examples:
        >>> calculate_2d_distance((0, 0), (3, 4))
        5.0
        >>> calculate_2d_distance((100, 200), (103, 204))
        5.0
    """
    x1, z1 = pos1
    x2, z2 = pos2
    return math.sqrt((x2 - x1)**2 + (z2 - z1)**2)


def calculate_3d_distance(pos1: Position3D, pos2: Position3D) -> float:
    """
    Calculate 3D Euclidean distance between two points.
    
    Args:
        pos1: First position (x, y, z)
        pos2: Second position (x, y, z)
        
    Returns:
        Distance in meters
        
    Examples:
        >>> calculate_3d_distance((0, 0, 0), (3, 4, 0))
        5.0
        >>> calculate_3d_distance((0, 0, 0), (1, 1, 1))
        1.7320508075688772
    """
    x1, y1, z1 = pos1
    x2, y2, z2 = pos2
    return math.sqrt((x2 - x1)**2 + (y2 - y1)**2 + (z2 - z1)**2)


def calculate_horizontal_distance(pos1: Position3D, pos2: Position3D) -> float:
    """
    Calculate horizontal (2D) distance between two 3D points, ignoring altitude.
    
    Args:
        pos1: First position (x, y, z)
        pos2: Second position (x, y, z)
        
    Returns:
        Horizontal distance in meters
    """
    return calculate_2d_distance((pos1[0], pos1[2]), (pos2[0], pos2[2]))


def generate_random_angle(degrees: bool = False) -> float:
    """
    Generate random angle between 0 and 2π (or 0-360 degrees).
    
    Args:
        degrees: If True, return angle in degrees; otherwise radians
        
    Returns:
        Random angle
        
    Examples:
        >>> angle = generate_random_angle()
        >>> 0 <= angle <= 2 * math.pi
        True
        >>> angle_deg = generate_random_angle(degrees=True)
        >>> 0 <= angle_deg <= 360
        True
    """
    if degrees:
        return random.uniform(0, 360)
    else:
        return random.uniform(0, 2 * math.pi)


def generate_random_position_in_circle(
    center, 
    radius: float, 
    min_distance: float = 0,
    uniform_distribution: bool = False
):
    """
    Generate random position within a circle.
    
    Consolidates the common pattern found 15-20+ times in codebase:
        angle = random.uniform(0, 2 * pi)
        r = random.uniform(min_r, max_r)
        x = cx + r * cos(angle); z = cz + r * sin(angle)
    
    Args:
        center: Center of circle (x, z) or (x, y, z)
        radius: Maximum distance from center
        min_distance: Minimum distance from center (default 0)
        uniform_distribution: If True, uses sqrt for uniform spatial distribution
        
    Returns:
        Random position (x, z) or (x, y, z) matching input format
        
    Examples:
        >>> pos = generate_random_position_in_circle((0, 0), 100)
        >>> distance = calculate_2d_distance((0, 0), pos)
        >>> distance <= 100
        True
        
        >>> # With 3D position (preserves Y coordinate)
        >>> pos = generate_random_position_in_circle((5000, 100, 3000), 1000)
        # Returns: (x, 100, z)
        
    Notes:
        - uniform_distribution=True for even spatial distribution (slightly slower)
        - Simple distribution (False) is faster but concentrates points near center
        - Preserves Y coordinate for 3D positions
    """
    # Extract center coordinates
    if len(center) == 2:
        cx, cz = center
        is_3d = False
    else:  # 3D position (x, y, z)
        cx, cy, cz = center[0], center[1], center[2]
        is_3d = True
    
    # Generate random angle
    angle = generate_random_angle()
    
    # Generate radius with optional uniform distribution
    if uniform_distribution:
        # Square root for uniform area distribution
        distance = math.sqrt(random.uniform(min_distance**2, radius**2))
    else:
        # Simple linear distribution (faster)
        distance = random.uniform(min_distance, radius)
    
    # Convert polar to Cartesian
    x = cx + distance * math.cos(angle)
    z = cz + distance * math.sin(angle)
    
    # Return in original format
    if is_3d:
        return (x, cy, z)
    else:
        return (x, z)


def generate_random_position_in_ring(
    center: Position2D,
    inner_radius: float, 
    outer_radius: float
) -> Position2D:
    """
    Generate random position within a ring (donut shape).
    
    Args:
        center: Center of ring (x, z)
        inner_radius: Inner radius (exclusion zone)
        outer_radius: Outer radius
        
    Returns:
        Random position (x, z)
    """
    return generate_random_position_in_circle(center, outer_radius, inner_radius)


def interpolate_positions(
    start: PositionType, 
    end: PositionType, 
    steps: int
) -> List[PositionType]:
    """
    Interpolate positions between start and end points.
    
    Args:
        start: Starting position
        end: Ending position  
        steps: Number of interpolation steps
        
    Returns:
        List of interpolated positions
        
    Examples:
        >>> positions = interpolate_positions((0, 0), (10, 0), 3)
        >>> len(positions)
        3
        >>> positions[0]
        (0.0, 0.0)
        >>> positions[-1]
        (10.0, 0.0)
    """
    if len(start) != len(end):
        raise ValueError("Start and end positions must have same dimensions")
    
    positions = []
    for i in range(steps):
        t = i / (steps - 1) if steps > 1 else 0
        
        if len(start) == 2:
            x = start[0] + t * (end[0] - start[0])
            z = start[1] + t * (end[1] - start[1])
            positions.append((x, z))
        else:  # 3D
            x = start[0] + t * (end[0] - start[0])
            y = start[1] + t * (end[1] - start[1])
            z = start[2] + t * (end[2] - start[2])
            positions.append((x, y, z))
    
    return positions


def calculate_bearing(from_pos, to_pos, degrees: bool = True, normalize: bool = True) -> float:
    """
    Calculate bearing (direction) from one position to another.
    
    Uses standard navigation convention: 0° = North (+Z), 90° = East (+X).
    This consolidates 5+ inconsistent bearing calculations and fixes bugs from
    incorrect atan2 parameter order.
    
    Args:
        from_pos: Starting position (x, z) or (x, y, z) - z is forward
        to_pos: Target position (x, z) or (x, y, z)
        degrees: Return in degrees (default True)
        normalize: Normalize to 0-360° or 0-2π range (default True)
    
    Returns:
        Bearing angle using navigation convention (0° = North)
        
    Examples:
        >>> # Target directly north (in +Z direction)
        >>> calculate_bearing((0, 0), (0, 100), degrees=True)
        0.0
        
        >>> # Target directly east (in +X direction)
        >>> calculate_bearing((0, 0), (100, 0), degrees=True)
        90.0
        
        >>> # Target directly south
        >>> calculate_bearing((0, 0), (0, -100), degrees=True)
        180.0
    
    Notes:
        - Uses atan2(dx, dz) for correct navigation bearing
        - Parameter order is CRITICAL: atan2(x_component, z_component)
        - Z axis is assumed to be "forward/north" direction (VTOL VR convention)
        - Handles both 2D (x, z) and 3D (x, y, z) positions
    """
    # Extract x and z components (handle both 2D and 3D positions)
    if len(from_pos) == 2:
        fx, fz = from_pos
    else:  # 3D position (x, y, z)
        fx, fz = from_pos[0], from_pos[2]
    
    if len(to_pos) == 2:
        tx, tz = to_pos
    else:  # 3D position (x, y, z)
        tx, tz = to_pos[0], to_pos[2]
    
    dx = tx - fx  # East-West component
    dz = tz - fz  # North-South component (z is forward)
    
    # atan2(dx, dz) gives bearing with 0° = North, 90° = East
    angle = math.atan2(dx, dz)
    
    # Normalize to positive range if requested
    if normalize and angle < 0:
        angle += 2 * math.pi
    
    return math.degrees(angle) if degrees else angle


def normalize_angle(angle: float, degrees: bool = False) -> float:
    """
    Normalize angle to 0-2π range (or 0-360° for degrees).
    
    Args:
        angle: Input angle
        degrees: Whether angle is in degrees
        
    Returns:
        Normalized angle
        
    Examples:
        >>> normalize_angle(3 * math.pi)  # > 2π
        3.141592653589793
        >>> normalize_angle(-math.pi)  # negative
        3.141592653589793
    """
    if degrees:
        return angle % 360
    else:
        return angle % (2 * math.pi)


def angle_difference(angle1: float, angle2: float, degrees: bool = False) -> float:
    """
    Calculate the shortest angular difference between two angles.
    
    Args:
        angle1: First angle
        angle2: Second angle
        degrees: Whether angles are in degrees
        
    Returns:
        Angular difference (-π to π for radians, -180° to 180° for degrees)
        
    Examples:
        >>> abs(angle_difference(0, math.pi)) < 0.001  # 180° difference
        True
        >>> abs(angle_difference(350, 10, degrees=True) - 20) < 0.001  # 20° difference
        True
    """
    max_angle = 360 if degrees else 2 * math.pi
    half_angle = 180 if degrees else math.pi
    
    diff = (angle2 - angle1) % max_angle
    if diff > half_angle:
        diff -= max_angle
    
    return diff


def is_position_in_circle(
    position: Position2D, 
    center: Position2D, 
    radius: float
) -> bool:
    """
    Check if position is within a circular area.
    
    Args:
        position: Position to check (x, z)
        center: Circle center (x, z)
        radius: Circle radius
        
    Returns:
        True if position is within circle
        
    Examples:
        >>> is_position_in_circle((5, 0), (0, 0), 10)
        True
        >>> is_position_in_circle((15, 0), (0, 0), 10)
        False
    """
    distance = calculate_2d_distance(position, center)
    return distance <= radius


def find_closest_position(
    target: PositionType, 
    candidates: List[PositionType]
) -> Tuple[PositionType, float]:
    """
    Find the closest position from a list of candidates.
    
    Args:
        target: Target position
        candidates: List of candidate positions
        
    Returns:
        Tuple of (closest_position, distance)
        
    Raises:
        ValueError: If no candidates provided
        
    Examples:
        >>> candidates = [(0, 0), (5, 0), (10, 0)]
        >>> closest, dist = find_closest_position((3, 0), candidates)
        >>> closest
        (5, 0)
        >>> abs(dist - 2.0) < 0.001
        True
    """
    if not candidates:
        raise ValueError("No candidate positions provided")
    
    closest_pos = candidates[0]
    
    if len(target) == 2:
        min_distance = calculate_2d_distance(target, closest_pos)
        for candidate in candidates[1:]:
            distance = calculate_2d_distance(target, candidate)
            if distance < min_distance:
                min_distance = distance
                closest_pos = candidate
    else:  # 3D
        min_distance = calculate_3d_distance(target, closest_pos)
        for candidate in candidates[1:]:
            distance = calculate_3d_distance(target, candidate)
            if distance < min_distance:
                min_distance = distance
                closest_pos = candidate
    
    return closest_pos, min_distance


def calculate_centroid(positions: List[PositionType]) -> PositionType:
    """
    Calculate the centroid (center) of a list of positions.
    
    Args:
        positions: List of positions
        
    Returns:
        Centroid position
        
    Raises:
        ValueError: If no positions provided
        
    Examples:
        >>> positions = [(0, 0), (10, 0), (0, 10)]
        >>> centroid = calculate_centroid(positions)
        >>> abs(centroid[0] - 3.333) < 0.01 and abs(centroid[1] - 3.333) < 0.01
        True
    """
    if not positions:
        raise ValueError("No positions provided")
    
    if len(positions[0]) == 2:
        x_sum = sum(pos[0] for pos in positions)
        z_sum = sum(pos[1] for pos in positions)
        count = len(positions)
        return (x_sum / count, z_sum / count)
    else:  # 3D
        x_sum = sum(pos[0] for pos in positions)
        y_sum = sum(pos[1] for pos in positions)
        z_sum = sum(pos[2] for pos in positions)
        count = len(positions)
        return (x_sum / count, y_sum / count, z_sum / count)


# Convenience functions for common military operations
def distribute_positions_in_circle(
    center: Position2D,
    radius: float,
    count: int,
    start_angle: float = 0,
    degrees: bool = False
) -> List[Position2D]:
    """
    Distribute positions evenly around a circle.
    
    Args:
        center: Circle center (x, z)
        radius: Distance from center
        count: Number of positions
        start_angle: Starting angle offset
        degrees: Whether start_angle is in degrees
        
    Returns:
        List of positions arranged in circle
        
    Examples:
        >>> positions = distribute_positions_in_circle((0, 0), 10, 4)
        >>> len(positions)
        4
    """
    if count <= 0:
        return []
    
    if not degrees:
        start_angle = math.degrees(start_angle)
    
    positions = []
    angle_step = 360 / count
    
    for i in range(count):
        angle_deg = start_angle + i * angle_step
        angle_rad = math.radians(angle_deg)
        
        x = center[0] + radius * math.cos(angle_rad)
        z = center[1] + radius * math.sin(angle_rad)
        
        positions.append((x, z))
    
    return positions


def calculate_formation_positions(
    leader_pos: Position2D,
    leader_heading: float,
    formation_type: str,
    count: int,
    spacing: float = 100
) -> List[Position2D]:
    """
    Calculate formation positions relative to leader.
    
    Args:
        leader_pos: Leader position (x, z)
        leader_heading: Leader heading in radians
        formation_type: 'line', 'wedge', 'diamond', 'box'
        count: Number of wingmen
        spacing: Distance between units
        
    Returns:
        List of wingman positions
        
    Examples:
        >>> positions = calculate_formation_positions((0, 0), 0, 'line', 2)
        >>> len(positions)
        2
    """
    positions = []
    
    if formation_type == 'line':
        # Line abreast formation
        for i in range(count):
            offset = (i + 1) * spacing
            side = 1 if i % 2 == 0 else -1
            
            # Position to the side of leader
            x = leader_pos[0] + side * offset * math.cos(leader_heading + math.pi/2)
            z = leader_pos[1] + side * offset * math.sin(leader_heading + math.pi/2)
            positions.append((x, z))
    
    elif formation_type == 'wedge':
        # V formation behind leader
        for i in range(count):
            offset = (i // 2 + 1) * spacing
            side = 1 if i % 2 == 0 else -1
            
            # Position behind and to the side
            x = leader_pos[0] - offset * math.cos(leader_heading) + side * offset * 0.5 * math.cos(leader_heading + math.pi/2)
            z = leader_pos[1] - offset * math.sin(leader_heading) + side * offset * 0.5 * math.sin(leader_heading + math.pi/2)
            positions.append((x, z))
    
    elif formation_type == 'diamond':
        # Diamond formation
        if count >= 1:
            # Tail position
            x = leader_pos[0] - spacing * math.cos(leader_heading)
            z = leader_pos[1] - spacing * math.sin(leader_heading)
            positions.append((x, z))
        
        if count >= 2:
            # Left wing
            x = leader_pos[0] - spacing * 0.5 * math.cos(leader_heading) - spacing * 0.5 * math.cos(leader_heading + math.pi/2)
            z = leader_pos[1] - spacing * 0.5 * math.sin(leader_heading) - spacing * 0.5 * math.sin(leader_heading + math.pi/2)
            positions.append((x, z))
        
        if count >= 3:
            # Right wing
            x = leader_pos[0] - spacing * 0.5 * math.cos(leader_heading) + spacing * 0.5 * math.cos(leader_heading + math.pi/2)
            z = leader_pos[1] - spacing * 0.5 * math.sin(leader_heading) + spacing * 0.5 * math.sin(leader_heading + math.pi/2)
            positions.append((x, z))
    
    elif formation_type == 'box':
        # Box formation
        positions_per_side = max(1, count // 4)
        remaining = count
        
        # Behind leader
        for i in range(min(positions_per_side, remaining)):
            x = leader_pos[0] - (i + 1) * spacing * math.cos(leader_heading)
            z = leader_pos[1] - (i + 1) * spacing * math.sin(leader_heading)
            positions.append((x, z))
            remaining -= 1
        
        # To the sides (left and right)
        for side in [-1, 1]:
            for i in range(min(positions_per_side, remaining)):
                x = leader_pos[0] + side * (i + 1) * spacing * math.cos(leader_heading + math.pi/2)
                z = leader_pos[1] + side * (i + 1) * spacing * math.sin(leader_heading + math.pi/2)
                positions.append((x, z))
                remaining -= 1
                if remaining <= 0:
                    break
            if remaining <= 0:
                break
    
    return positions[:count]


def calculate_slope_from_normal(normal: Tuple[float, float, float], degrees: bool = True) -> float:
    """
    Calculate terrain slope angle from surface normal vector.
    
    This consolidates 13+ instances of slope calculation scattered across the codebase.
    The normal vector is assumed to have Y as the up axis.
    
    Args:
        normal: Surface normal vector (x, y, z) where y is up
        degrees: Return angle in degrees (default) or radians
    
    Returns:
        Slope angle from horizontal plane. 0° = flat, 90° = vertical wall
        
    Examples:
        >>> # Flat terrain (normal pointing straight up)
        >>> calculate_slope_from_normal((0, 1, 0))
        0.0
        
        >>> # 45-degree slope
        >>> calculate_slope_from_normal((0.707, 0.707, 0))
        45.0
        
        >>> # Vertical wall
        >>> calculate_slope_from_normal((1, 0, 0))
        90.0
    
    Notes:
        - Y component is clamped to [-1, 1] range to avoid math domain errors
        - Returns angle from horizontal (0° = flat, not angle from vertical)
        - Used extensively in terrain analysis for placement validation
    """
    # Clamp Y component to valid range for acos [-1, 1]
    # This prevents math domain errors from numerical precision issues
    y_component = max(-1.0, min(1.0, float(normal[1])))
    
    # acos(y) gives angle from up direction, so result is already slope from horizontal
    angle_rad = math.acos(y_component)
    
    return math.degrees(angle_rad) if degrees else angle_rad