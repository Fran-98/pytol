# pytol/classes/mission_objects.py
from dataclasses import dataclass, field, fields
from typing import List, Optional, Union, Dict, Any, Literal, Tuple
from pytol.classes.conditionals import Conditional
# --- Event/Action Objects ---
@dataclass
class ParamInfo:
    """Represents a parameter for an EventTarget."""
    name: str
    type: str  # e.g., "string", "bool", "float", "int"
    value: Any
    attr_info: Optional[Dict[str, Any]] = None

@dataclass
class EventTarget:
    """Represents a target for a Trigger Event."""
    target_type: str  # e.g., "Unit", "Global"
    target_id: str
    event_name: str
    method_name: Optional[str] = None
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

@dataclass
class TimedEventInfo:
    """Represents a specific event occurring at a certain time within a TimedEventGroup."""
    event_name: str # An arbitrary name for the event info block
    time: float     # Time in seconds relative to group start when events should fire
    event_targets: List[EventTarget] = field(default_factory=list)

@dataclass
class TimedEventGroup:
    """Represents a group of timed events in the VTS file."""
    group_name: str         # Name of the group
    group_id: int           # Unique integer ID for the group
    begin_immediately: bool = True # Whether the timer starts at mission start
    initial_delay: float = 0.0     # Delay in seconds before the timer starts (if not begin_immediately)
    events: List[TimedEventInfo] = field(default_factory=list) # List of events in this group

@dataclass
class GlobalValue:
    """Represents a global variable for mission logic."""
    name: str                 # Unique name/ID for the global value
    initial_value: Union[int, float] # Starting value

@dataclass
class ConditionalAction:
    """Represents an action triggered when a Conditional is met."""
    id: int                   # Unique integer ID for this action block
    name: str                 # Name for the action block
    conditional_id: str       # String ID of the Conditional that triggers this
    actions: List[EventTarget] = field(default_factory=list) # Actions to execute

@dataclass
class SequenceEvent:
    """Represents a single step (EVENT) within an EventSequence."""
    node_name: str = "New Node"      # Name shown in editor (optional for generation?)
    delay: float = 0.0              # Delay in seconds before firing actions (after condition met)
    conditional: Optional[Union[Conditional, str]] = None # Optional Conditional object or string ID to wait for
    actions: List[EventTarget] = field(default_factory=list) # Actions to execute in this step

@dataclass
class EventSequence:
    """Represents an Event Sequence (SEQUENCE) in the VTS file."""
    id: int                   # Unique integer ID for the sequence
    sequence_name: str        # Name of the sequence
    start_immediately: bool = False # Whether the sequence starts automatically at mission start
    while_loop: bool = False      # Whether the sequence loops back to the start after finishing
    while_conditional: Optional[Union[Conditional, str]] = None # Optional conditional to evaluate each loop iteration
    events: List[SequenceEvent] = field(default_factory=list) # Ordered list of steps

@dataclass
class RandomEventAction:
    """Represents a potential action (ACTION block) within a RandomEvent."""
    id: int                     # Unique ID for this action within the RandomEvent
    action_name: str = ""       # Optional name for the action
    fixed_weight: int = 100     # Probability weight (base chance)
    use_gv_weight: bool = False # Whether to use a GlobalValue for weight
    gv_weight_name: Optional[str] = None # Name of the GlobalValue if useGvWeight is True
    conditional: Optional[Union[Conditional, str]] = None # Optional conditional object or ID for this specific action
    actions: List[EventTarget] = field(default_factory=list) # EventTargets to execute if chosen

@dataclass
class RandomEvent:
    """Represents a Random Event container (RANDOM_EVENT block) in the VTS file."""
    id: int                       # Unique integer ID for the random event group
    name: str                     # Used as the 'note' field in the VTS
    action_options: List[RandomEventAction] = field(default_factory=list) # List of possible actions

# --- Weather Preset Dataclass ---
@dataclass(unsafe_hash=True)
class WeatherPreset(BasePytolObject):
    """
    Represents a custom WEATHER_PRESETS::PRESET entry for VTOL VR missions.

    The 'data' field in VTS is a semicolon-separated list with the following order:
      1) presetName (str)
      2) cloudPlaneAltitude (float, meters)
      3) cloudiness (float 0-1)
      4) macroCloudiness (float 0-1)
      5) cirrus (float 0-2)
      6) stratocumulus (float 0-2)
      7) precipitation (float 0-1)
      8) lightningChance (float 0-1)
      9) fogDensity (float 0-1)
     10) fogColor (tuple rgba, 0-1 each)
     11) fogHeight (float 0-4, fraction of cloud height)
     12) fogFalloff (float meters, 0-10000)
     13) cloudDensity (float 0-8)

    Notes:
    - Preset IDs must start at 8 to avoid colliding with built-in presets (0-7).
    - 'defaultWeather' at the mission root references a preset id (built-in or custom).
    """
    id: int
    preset_name: str
    cloud_plane_altitude: float
    cloudiness: float
    macro_cloudiness: float
    cirrus: float
    stratocumulus: float
    precipitation: float
    lightning_chance: float
    fog_density: float
    fog_color: Tuple[float, float, float, float]
    fog_height: float
    fog_falloff: float
    cloud_density: float

    def to_vts_data_line(self) -> str:
        """
        Builds the semicolon-separated 'data =' line content for the PRESET block.

        Returns:
            A string like: "Name;1500;0.3;...;(r, g, b, a);1;1000;0;"
        """
        r, g, b, a = self.fog_color
        # Ensure standard formatting with spaces after commas to match editor export style
        color_str = f"({r}, {g}, {b}, {a})"
        parts = [
            self.preset_name,
            str(self.cloud_plane_altitude),
            str(self.cloudiness),
            str(self.macro_cloudiness),
            str(self.cirrus),
            str(self.stratocumulus),
            str(self.precipitation),
            str(self.lightning_chance),
            str(self.fog_density),
            color_str,
            str(self.fog_height),
            str(self.fog_falloff),
            str(self.cloud_density),
        ]
        # Join with semicolons and include trailing semicolon
        return ";".join(parts) + ";"