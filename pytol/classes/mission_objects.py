# pytol/classes/mission_objects.py
from dataclasses import dataclass, field, fields
from typing import List, Optional, Union, Dict, Any, cast, Literal

# --- Event/Action Objects ---
@dataclass
class ParamInfo:
    """Represents a parameter for an EventTarget."""
    name: str
    type: str  # e.g., "string", "bool", "float", "int"
    value: Any

@dataclass
class EventTarget:
    """Represents a target for a Trigger Event."""
    target_type: str  # e.g., "Unit", "Global"
    target_id: str
    event_name: str
    params: List[ParamInfo] = field(default_factory=list)

# --- Base and Trigger Objects ---
@dataclass
class BasePytolObject:
    """Base class for simple mission objects."""
    def to_dict(self) -> Dict[str, Any]:
        """Converts the object to a dictionary for the mission builder."""
        return {k: v for k, v in self.__dict__.items() if v is not None}

@dataclass(unsafe_hash=True)
class Path(BasePytolObject):
    """Dataclass for a VTS Path."""
    name: str
    id: Optional[int] = None
    points: List[List[float]] = field(default_factory=list)
    loop: Optional[bool] = False
    path_mode: Optional[Literal["Smooth", "Linear", "Bezier"]] = "Smooth"

    # --- Internal/Unused fields ---
    uniformly_partition: Optional[bool] = field(default=None, compare=False)
    scenario_path_i_d: Optional[int] = field(default=None, compare=False)
    unity_action: Optional[str] = field(default=None, compare=False)
    get_closest_time_world: Optional[float] = field(default=None, compare=False)
    get_follow_point: Optional[str] = field(default=None, compare=False)
    get_closest_time: Optional[float] = field(default=None, compare=False)


@dataclass(unsafe_hash=True)
class Trigger(BasePytolObject):
    """Dataclass for a VTS TriggerEvent."""
    id: int
    name: str
    trigger_type: str
    event_targets: List[EventTarget] = field(default_factory=list)
    enabled: Optional[bool] = True

    # --- Properties (become **kwargs in the VTS) ---
    waypoint: Optional[str] = None
    radius: Optional[float] = None
    spherical_radius: Optional[bool] = None
    trigger_mode: Optional[str] = None
    unit: Optional[str] = None
    proxy_mode: Optional[str] = None
    conditional: Optional[str] = None

    # --- Internal/Unused fields ---
    void: Optional[str] = field(default=None, compare=False)
    string: Optional[str] = field(default=None, compare=False)
    list_folder_data: Optional[str] = field(default=None, compare=False)
    event_fired_delegate: Optional[str] = field(default=None, compare=False)

    def get_props_dict(self) -> Dict[str, Any]:
        """Gets the dictionary of properties for the VTS 'props' block."""
        core_fields = ['id', 'name', 'trigger_type', 'event_targets', 'enabled']
        props = {}
        # Use the imported 'fields' function here
        for f in fields(self):
            # Only include fields meant for VTS (compare=True)
            if f.name not in core_fields and f.compare:
                val = getattr(self, f.name)
                if val is not None:
                    props[f.name] = val
        return props

# --- Waypoint Dataclass ---
@dataclass(unsafe_hash=True)
class Waypoint(BasePytolObject):
    """Dataclass for a VTS Waypoint."""
    name: str
    global_point: List[float]
    id: Optional[int] = None

# --- StaticObject Dataclass ---
@dataclass(unsafe_hash=True)
class StaticObject(BasePytolObject):
    """Dataclass for a VTS StaticObject."""
    prefab_id: str
    global_pos: List[float]
    rotation: List[float]

# --- Base Dataclass ---
@dataclass(unsafe_hash=True)
class Base(BasePytolObject):
    """Dataclass for a VTS BaseInfo."""
    id: int
    team: str  # "Allied" or "Enemy"
    name: Optional[str] = ""

# --- BriefingNote Dataclass ---
@dataclass(unsafe_hash=True)
class BriefingNote(BasePytolObject):
    """Dataclass for a VTS Briefing Note."""
    text: str
    image_path: Optional[str] = None
    audio_clip_path: Optional[str] = None