"""
Equipment system for VTOL VR missions with validation and helper classes.
Provides type-safe equipment selection and loadout building.
"""

import json
import os
from typing import List, Dict, Optional
from dataclasses import dataclass, field


def load_vehicle_equip_database() -> Dict[str, List[str]]:
    """Load the vehicle equipment database from JSON."""
    db_path = os.path.join(os.path.dirname(__file__), "vehicle_equip_database.json")
    with open(db_path, 'r', encoding='utf-8') as f:
        return json.load(f)


# Load database at module level
_EQUIP_DB = load_vehicle_equip_database()


class EquipmentNotFoundError(ValueError):
    """Raised when an equipment ID is not valid for the vehicle."""
    pass


class InvalidLoadoutError(ValueError):
    """Raised when a loadout configuration is invalid."""
    pass


@dataclass
class HardpointConfig:
    """Configuration for a vehicle's hardpoint layout."""
    vehicle_name: str
    hardpoint_count: int
    hardpoint_names: List[str] = field(default_factory=list)
    available_equipment: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.hardpoint_names:
            # Generate generic names if not provided
            self.hardpoint_names = [f"HP{i+1}" for i in range(self.hardpoint_count)]
        
        # Load equipment from database
        if not self.available_equipment and self.vehicle_name in _EQUIP_DB:
            self.available_equipment = _EQUIP_DB[self.vehicle_name]


# Vehicle hardpoint configurations
VEHICLE_HARDPOINTS: Dict[str, HardpointConfig] = {
    "F/A-26B": HardpointConfig(
        vehicle_name="F/A-26B",
        hardpoint_count=7,
        hardpoint_names=["Nose Gun", "Left Inner", "Left Wing", "Center", "Right Wing", "Right Inner", "Right Outer"]
    ),
    "AV-42C": HardpointConfig(
        vehicle_name="AV-42C",
        hardpoint_count=6,
        hardpoint_names=["Gun Pod", "Left Inner", "Left Outer", "Right Inner", "Right Outer", "Belly"]
    ),
    "F-45A": HardpointConfig(
        vehicle_name="F-45A",
        hardpoint_count=8,
        hardpoint_names=["Gun", "Left Bay 1", "Left Bay 2", "Right Bay 1", "Right Bay 2", "Left Wing", "Center", "Right Wing"]
    ),
    "AH-94": HardpointConfig(
        vehicle_name="AH-94",
        hardpoint_count=4,
        hardpoint_names=["Gun", "Left Inner", "Left Outer", "Right Inner", "Right Outer"]
    ),
    "EF-24G": HardpointConfig(
        vehicle_name="EF-24G",
        hardpoint_count=7,
        hardpoint_names=["Gun", "Left Inner", "Left Mid", "Left Outer", "Center", "Right Outer", "Right Mid", "Right Inner"]
    ),
}


class EquipmentBuilder:
    """
    Fluent API for building equipment loadouts with validation.
    
    Example:
        loadout = (EquipmentBuilder("F/A-26B")
            .set_hardpoint(0, "fa26_gun")
            .set_hardpoint(1, "fa26_aim9x2")
            .set_hardpoint(2, "fa26_droptank")
            .build())
    """
    
    def __init__(self, vehicle: str):
        self.vehicle = vehicle
        
        if vehicle not in VEHICLE_HARDPOINTS:
            # Create generic config for unknown vehicles
            equips = _EQUIP_DB.get(vehicle, [])
            # Try to infer hardpoint count from typical patterns
            typical_counts = {"B-11 Bomber": 4, "T-55": 0}
            hp_count = typical_counts.get(vehicle, 7)  # Default to 7
            self.config = HardpointConfig(vehicle, hp_count, available_equipment=equips)
        else:
            self.config = VEHICLE_HARDPOINTS[vehicle]
        
        self.loadout: List[str] = [""] * self.config.hardpoint_count
    
    def set_hardpoint(self, index: int, equipment: str) -> 'EquipmentBuilder':
        """
        Set equipment for a specific hardpoint.
        
        Args:
            index: Hardpoint index (0-based)
            equipment: Equipment ID (e.g., "fa26_gun", "fa26_aim9x2")
        
        Returns:
            Self for chaining
        
        Raises:
            IndexError: If hardpoint index is invalid
            EquipmentNotFoundError: If equipment is not valid for this vehicle
        """
        if index < 0 or index >= self.config.hardpoint_count:
            raise IndexError(
                f"Hardpoint index {index} out of range. "
                f"{self.vehicle} has {self.config.hardpoint_count} hardpoints (0-{self.config.hardpoint_count-1})"
            )
        
        if equipment and equipment not in self.config.available_equipment:
            raise EquipmentNotFoundError(
                f"Equipment '{equipment}' not available for {self.vehicle}. "
                f"Use get_available_equipment() to see valid options."
            )
        
        self.loadout[index] = equipment
        return self
    
    def set_by_name(self, hardpoint_name: str, equipment: str) -> 'EquipmentBuilder':
        """
        Set equipment by hardpoint name.
        
        Args:
            hardpoint_name: Name of hardpoint (e.g., "Left Wing", "Center")
            equipment: Equipment ID
        
        Returns:
            Self for chaining
        """
        try:
            index = self.config.hardpoint_names.index(hardpoint_name)
        except ValueError:
            available = ", ".join(self.config.hardpoint_names)
            raise ValueError(f"Hardpoint '{hardpoint_name}' not found. Available: {available}")
        
        return self.set_hardpoint(index, equipment)
    
    def clear_hardpoint(self, index: int) -> 'EquipmentBuilder':
        """Clear (empty) a hardpoint."""
        self.loadout[index] = ""
        return self
    
    def clear_all(self) -> 'EquipmentBuilder':
        """Clear all hardpoints."""
        self.loadout = [""] * self.config.hardpoint_count
        return self
    
    def get_available_equipment(self) -> List[str]:
        """Get list of all available equipment IDs for this vehicle."""
        return self.config.available_equipment.copy()
    
    def get_hardpoint_names(self) -> List[str]:
        """Get list of hardpoint names."""
        return self.config.hardpoint_names.copy()
    
    def print_loadout(self):
        """Print current loadout in human-readable format."""
        print(f"\n{self.vehicle} Loadout:")
        print("=" * 60)
        for i, (name, equip) in enumerate(zip(self.config.hardpoint_names, self.loadout)):
            status = equip if equip else "(empty)"
            print(f"  {i}. {name:20s} -> {status}")
        print("=" * 60)
    
    def build(self) -> List[str]:
        """
        Build and return the equipment list.
        
        Returns:
            List of equipment IDs suitable for use in Mission or Unit configuration
        """
        return self.loadout.copy()
    
    def build_vts_string(self) -> str:
        """
        Build equipment string in VTS format (semicolon-separated with trailing semicolon).
        
        Returns:
            VTS-formatted equipment string
        """
        return ";".join(self.loadout) + ";"


class LoadoutPresets:
    """
    Pre-configured loadouts for common mission types.
    """
    
    @staticmethod
    def fa26_air_to_air() -> List[str]:
        """F/A-26B: Air superiority loadout."""
        return (EquipmentBuilder("F/A-26B")
            .set_hardpoint(0, "fa26_gun")
            .set_hardpoint(1, "fa26_aim9x2")
            .set_hardpoint(2, "af_amraamRailx2")  # Fixed: use af_ prefix
            .set_hardpoint(3, "")  # Center empty
            .set_hardpoint(4, "af_amraamRailx2")  # Fixed: use af_ prefix
            .set_hardpoint(5, "fa26_aim9x2")
            .set_hardpoint(6, "")  # Outer empty
            .build())
    
    @staticmethod
    def fa26_cas() -> List[str]:
        """F/A-26B: Close air support with Mavericks."""
        return (EquipmentBuilder("F/A-26B")
            .set_hardpoint(0, "fa26_gun")
            .set_hardpoint(1, "fa26_iris-t-x2")
            .set_hardpoint(2, "fa26_maverickx3")
            .set_hardpoint(3, "fa26_tgp")  # Targeting pod
            .set_hardpoint(4, "fa26_maverickx3")
            .set_hardpoint(5, "fa26_iris-t-x2")
            .set_hardpoint(6, "")
            .build())
    
    @staticmethod
    def fa26_strike() -> List[str]:
        """F/A-26B: Precision strike with GPS bombs."""
        return (EquipmentBuilder("F/A-26B")
            .set_hardpoint(0, "fa26_gun")
            .set_hardpoint(1, "fa26_iris-t-x2")  # Self-defense
            .set_hardpoint(2, "fa26_gbu38x3")
            .set_hardpoint(3, "fa26_droptank")
            .set_hardpoint(4, "fa26_gbu38x3")
            .set_hardpoint(5, "fa26_iris-t-x2")  # Self-defense
            .set_hardpoint(6, "")
            .build())
    
    @staticmethod
    def av42_transport() -> List[str]:
        """AV-42C: Light transport with self-defense."""
        return (EquipmentBuilder("AV-42C")
            .set_hardpoint(0, "gau-8")  # Gun pod
            .set_hardpoint(1, "sidewinderx2")
            .set_hardpoint(2, "")  # Empty
            .set_hardpoint(3, "sidewinderx2")
            .set_hardpoint(4, "")  # Empty
            .set_hardpoint(5, "")  # Belly empty
            .build())
    
    @staticmethod
    def av42_cas() -> List[str]:
        """AV-42C: CAS with AGMs and rockets."""
        return (EquipmentBuilder("AV-42C")
            .set_hardpoint(0, "gau-8")
            .set_hardpoint(1, "hellfirex4")
            .set_hardpoint(2, "h70-x19")
            .set_hardpoint(3, "hellfirex4")
            .set_hardpoint(4, "h70-x19")
            .set_hardpoint(5, "")
            .build())
    
    @staticmethod
    def f45_stealth_strike() -> List[str]:
        """F-45A: Stealth strike configuration."""
        return (EquipmentBuilder("F-45A")
            .set_hardpoint(0, "af_gun")
            .set_hardpoint(1, "af_gbu38x1")
            .set_hardpoint(2, "af_gbu38x1")
            .set_hardpoint(3, "af_gbu38x1")
            .set_hardpoint(4, "af_gbu38x1")
            .set_hardpoint(5, "")  # Wings empty (stealth)
            .set_hardpoint(6, "")  # Center empty
            .set_hardpoint(7, "")  # Right wing empty
            .build())
    
    @staticmethod
    def get_preset_names() -> List[str]:
        """Get list of all available preset names."""
        return [
            "fa26_air_to_air",
            "fa26_cas",
            "fa26_strike",
            "av42_transport",
            "av42_cas",
            "f45_stealth_strike"
        ]
    
    @classmethod
    def get_preset(cls, name: str) -> List[str]:
        """
        Get a preset by name.
        
        Args:
            name: Preset name (e.g., "fa26_air_to_air")
        
        Returns:
            Equipment loadout list
        
        Raises:
            ValueError: If preset name is invalid
        """
        if not hasattr(cls, name):
            available = ", ".join(cls.get_preset_names())
            raise ValueError(f"Preset '{name}' not found. Available: {available}")
        return getattr(cls, name)()


def get_available_vehicles() -> List[str]:
    """Get list of all vehicles in the equipment database."""
    return list(_EQUIP_DB.keys())


def get_playable_vehicles() -> List[str]:
    """
    Get list of only playable vehicles in the equipment database.
    
    Returns only the vehicles that are player-controllable in VTOL VR:
    - F/A-26B (Fighter/Attack)
    - AH-94 (Attack Helicopter)
    - EF-24G (Fighter)
    - F-45A (Fighter)
    - T-55 (Trainer)
    - AV-42C (VTOL)
    
    Returns:
        List of playable vehicle names that exist in the database
    
    Examples:
        >>> playable = get_playable_vehicles()
        >>> print(playable)
        ['F/A-26B', 'F-45A', 'AH-94', 'AV-42C', 'EF-24G', 'T-55']
    """
    # Whitelist of playable vehicles in VTOL VR
    playable = ['F/A-26B', 'AH-94', 'EF-24G', 'F-45A', 'T-55', 'AV-42C']
    # Return only those that exist in the database
    return [vehicle for vehicle in playable if vehicle in _EQUIP_DB]


def get_equipment_for_vehicle(vehicle: str) -> List[str]:
    """
    Get all available equipment for a specific vehicle.
    
    Args:
        vehicle: Vehicle name (e.g., "F/A-26B")
    
    Returns:
        List of equipment IDs
    
    Raises:
        KeyError: If vehicle not found in database
    """
    if vehicle not in _EQUIP_DB:
        available = ", ".join(get_available_vehicles())
        raise KeyError(f"Vehicle '{vehicle}' not in database. Available: {available}")
    return _EQUIP_DB[vehicle]


def search_equipment(search_term: str, vehicle: Optional[str] = None) -> Dict[str, List[str]]:
    """
    Search for equipment by name across all vehicles or specific vehicle.
    
    Args:
        search_term: Text to search for (case-insensitive)
        vehicle: Optional vehicle name to limit search
    
    Returns:
        Dict mapping vehicle names to matching equipment IDs
    """
    search_lower = search_term.lower()
    results = {}
    
    vehicles_to_search = [vehicle] if vehicle else _EQUIP_DB.keys()
    
    for veh in vehicles_to_search:
        if veh not in _EQUIP_DB:
            continue
        matches = [eq for eq in _EQUIP_DB[veh] if search_lower in eq.lower()]
        if matches:
            results[veh] = matches
    
    return results
