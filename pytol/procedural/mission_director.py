"""Minimal Mission Director skeleton based on the "Single-Session Dynamic Campaign" research.

Terminal schema (shared with PCG)
---------------------------------
The grammar emits terminals in the form ``CATEGORY:payload`` which are parsed
into :class:`PlanObjective` records. Downstream systems should rely on the
structured fields rather than re-parsing the raw string.

================  ===========================================================
Terminal          Meaning
================  ===========================================================
PLAYER_TASK:role:target
                  Primary player assignment. ``role`` is typically one of
                  ``strike``, ``sead``, ``cap``, ``cas``, ``recon``; ``target``
                  is an abstract label such as ``enemy_airbase``.
AI_TASK:action:target
                  Supporting AI package. ``action`` names the behaviour
                  (e.g. ``ESCORT``, ``AWACS``) and ``target`` indicates the
                  formation or area the AI should cover.
SPAWN:token       Request to materialise an enemy/allied package whose abstract
                  identifier is ``token`` (e.g. ``enemy_airbase``).
THREAT_LAYER:tag  Threat ring or defensive tier to seed (e.g. ``IADS_RING``).
SECONDARY_OBJECTIVE:type
                  Secondary objective hint (e.g. ``sam_network``, ``artillery_battery``).
                  PCG will generate appropriate secondary objectives based on spawned units.
OPTIONAL_OBJECTIVE:type
                  Optional/bonus objective hint (e.g. ``convoy``, ``bonus_targets``).
REINFORCEMENT:type Trigger to spawn reinforcements when conditions are met
                  (e.g. ``sam_reinforcement``, ``aircraft_reinforcement``).
SCHEDULE_BACKGROUND:activity
                  Background activity hint (convoys, patrols, civilian traffic).
*anything else*   Currently treated as informational note; stored verbatim.
================  ===========================================================

The :class:`MissionDirector` converts each terminal to :class:`PlanObjective`
so the PCG layer can operate on a typed structure. When updating the grammar,
extend the table above and the parsing logic in :meth:`MissionDirector.generate`.

Keep this file small and dependency-free so early integration tests are fast.
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Union
import random
from .grammar import Planner, build_default_mission_grammar


@dataclass
class MissionConfig:
    mission_duration: int = 60  # minutes
    operational_environment: str = "land"  # land | naval | littoral
    mission_archetype: str = "offensive"  # offensive | defensive | recon
    player_role: str = "strike"  # strike | cap | sead | cas | recon
    threat_level: str = "medium"  # low | medium | high | extreme
    world_liveliness: str = "moderate"  # quiet | moderate | busy
    random_seed: Optional[int] = None
    
    # Complexity tweaking (NEW)
    complexity: Dict[str, Any] = field(default_factory=lambda: {
        # If None = auto (based on threat_level), otherwise explicit value
        "num_static_structures": None,  # 0-5, None = auto
        "num_enemy_units": None,       # None = auto, or "low"/"medium"/"high"
        "num_friendly_units": None,    # None = auto, or "low"/"medium"/"high"
        "sam_density": "auto",         # "auto" | "sparse" | "medium" | "dense"
        "objective_count": "auto",     # "auto" | "few" | "many"
        "city_objectives": True,       # Include cities as objectives
        "static_structure_probability": None,  # None = auto, or 0.0-1.0
    })


@dataclass
class MissionPlan:
    """Container for the high-level narrative plan produced by MissionDirector.

    Attributes:
        briefing: Human-readable mission summary.
        objectives: Ordered list of PlanObjective items describing player/AI
            tasks, spawn directives, and threat layers. Downstream systems
            should rely on the normalized fields on PlanObjective instead of
            re-parsing terminal strings.
        metadata: Mission-wide hints (seed, duration, archetype, threat level,
            operational context, liveliness) that the PCG layer uses to
            parameterize placements and pacing.
    """

    briefing: str
    objectives: List["PlanObjective"] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanObjective:
    """Structured view over a grammar terminal.

    Fields are optional because not every terminal carries every attribute.

    Attributes:
        raw: Original formatted terminal string (e.g. 'PLAYER_TASK:sead:enemy_airbase').
        type: Normalized objective category ('player_task', 'ai_task', 'spawn',
            'threat_layer', 'note', etc.).
        description: Human readable summary of the task.
        role: Player/AI role when applicable.
        target: Target identifier or label emitted by the grammar.
        action: AI action keyword (for ai_task entries).
        layer: Threat layer identifier (IADS, CAP, etc.).
        data: Additional arbitrary metadata for downstream consumers.
    """

    raw: str
    type: str
    description: str
    role: Optional[str] = None
    target: Optional[str] = None
    action: Optional[str] = None
    layer: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Best-effort dictionary representation for legacy consumers."""
        data = asdict(self)
        return data


class MissionDirector:
    """Generate a MissionPlan from a MissionConfig.

    This is a deliberately tiny and deterministic implementation to use as
    a working baseline. The full implementation will replace the internals
    with grammar-based expansion and dynamic weighting.
    """

    def __init__(self, seed: Optional[int] = None):
        self.seed = seed
        self.rng = random.Random(seed)

    def generate(self, config: MissionConfig) -> MissionPlan:
        """Create a MissionPlan using a grammar-based planner.

        The grammar is intentionally small and extensible. The method builds a
        context from the config, expands the default grammar using a seeded
        planner, and translates the resulting terminal tokens into a list of
        abstract objectives.
        """
        seed_note = config.random_seed if config.random_seed is not None else self.seed
        rng = random.Random(seed_note)

        # Build context used to format terminal strings in the grammar
        primary_target = "enemy_airbase" if config.operational_environment == "land" else "enemy_fleet"
        context = {
            "player_role": config.player_role,
            "primary_target": primary_target,
            "threat_level": config.threat_level,
            "liveliness": config.world_liveliness,
            "duration_min": config.mission_duration,
        }

        # Build grammar and planner
        grammar = build_default_mission_grammar(
            {
                "mission_archetype": config.mission_archetype,
                "player_role": config.player_role,
                "threat_level": config.threat_level,
                "world_liveliness": config.world_liveliness,
                "operational_environment": config.operational_environment,
                "primary_target": primary_target,
            }
        )
        planner = Planner(grammar, rng=rng)
        terminals = planner.expand("MISSION", context=context)

        # Convert terminals to objective dicts
        objectives: List[PlanObjective] = []
        for idx, tok in enumerate(terminals):
            parts = tok.get("parts", [])
            if not parts:
                objectives.append(
                    PlanObjective(
                        raw=tok.get("symbol", ""),
                        type="note",
                        description=tok.get("symbol", ""),
                        data={"parts": parts},
                    )
                )
                continue

            symbol_type = parts[0]
            # Simple parsing rules for terminals: SYMBOL:ACTION:TARGET
            raw_symbol = tok.get("symbol", "")
            obj_kwargs: Dict[str, Any] = {
                "raw": raw_symbol,
                "description": raw_symbol,
                "data": {"parts": parts},
            }
            if symbol_type == "PLAYER_TASK":
                role = parts[1] if len(parts) > 1 else config.player_role
                target = parts[2] if len(parts) > 2 else primary_target
                obj = PlanObjective(
                    type="player_task",
                    raw=raw_symbol,
                    role=role,
                    target=target,
                    description=f"Player task: {role} -> {target}",
                    data={"parts": parts},
                )
                objectives.append(obj)
                continue
            elif symbol_type == "AI_TASK":
                action = parts[1] if len(parts) > 1 else None
                target = parts[2] if len(parts) > 2 else None
                obj = PlanObjective(
                    type="ai_task",
                    raw=raw_symbol,
                    action=action,
                    target=target,
                    description=raw_symbol,
                    data={"parts": parts},
                )
                objectives.append(obj)
                continue
            elif symbol_type == "SPAWN":
                target = parts[1] if len(parts) > 1 else None
                obj = PlanObjective(
                    type="spawn",
                    raw=raw_symbol,
                    target=target,
                    description=f"Spawn target: {target}",
                    data={"parts": parts},
                )
                objectives.append(obj)
                continue
            elif symbol_type == "THREAT_LAYER":
                layer = parts[1] if len(parts) > 1 else None
                obj = PlanObjective(
                    type="threat_layer",
                    raw=raw_symbol,
                    layer=layer,
                    description=f"Threat layer: {layer}",
                    data={"parts": parts},
                )
                objectives.append(obj)
                continue
            elif symbol_type == "SCHEDULE_BACKGROUND":
                activity = parts[1] if len(parts) > 1 else None
                obj = PlanObjective(
                    type="schedule_background",
                    raw=raw_symbol,
                    target=activity,
                    description=f"Background activity: {activity}",
                    data={"parts": parts},
                )
                objectives.append(obj)
                continue
            elif symbol_type == "SECONDARY_OBJECTIVE":
                obj_type = parts[1] if len(parts) > 1 else None
                obj = PlanObjective(
                    type="secondary_objective",
                    raw=raw_symbol,
                    target=obj_type,
                    description=f"Secondary objective: {obj_type}",
                    data={"parts": parts},
                )
                objectives.append(obj)
                continue
            elif symbol_type == "OPTIONAL_OBJECTIVE":
                obj_type = parts[1] if len(parts) > 1 else None
                obj = PlanObjective(
                    type="optional_objective",
                    raw=raw_symbol,
                    target=obj_type,
                    description=f"Optional objective: {obj_type}",
                    data={"parts": parts},
                )
                objectives.append(obj)
                continue
            elif symbol_type == "REINFORCEMENT":
                reinf_type = parts[1] if len(parts) > 1 else None
                obj = PlanObjective(
                    type="reinforcement",
                    raw=raw_symbol,
                    target=reinf_type,
                    description=f"Reinforcement trigger: {reinf_type}",
                    data={"parts": parts},
                )
                objectives.append(obj)
                continue

            # Fallback: treat as note
            obj_kwargs["type"] = "note"
            objectives.append(PlanObjective(**obj_kwargs))

        briefing = (
            f"Grammar-generated {config.mission_archetype} mission in {config.operational_environment}. "
            f"Player role: {config.player_role}. Threat: {config.threat_level}."
        )

        # Process complexity settings (support preset strings or dicts)
        complexity_settings = _process_complexity_config(config.complexity)
        
        metadata = {
            "seed": seed_note,
            "duration_min": config.mission_duration,
            # Propagate higher-level config hints so PCG can make choices
            "player_role": config.player_role,
            "mission_archetype": config.mission_archetype,
            "threat_level": config.threat_level,
            "operational_environment": config.operational_environment,
            "world_liveliness": config.world_liveliness,
            "primary_target": primary_target,
            # Add complexity settings for PCG
            "complexity": complexity_settings,
        }
        return MissionPlan(briefing=briefing, objectives=objectives, metadata=metadata)


def create_complexity_preset(name: str) -> Dict[str, Any]:
    """
    Create complexity presets for easy mission tweaking.
    
    Presets:
    - "minimal": Few units, 0-1 structures, sparse SAMs (for quick missions)
    - "standard": Default balanced (auto-based on threat level)
    - "intense": Many units, 3-4 structures, dense SAMs (maximum challenge)
    - "custom": Empty dict (user provides all values)
    
    Args:
        name: Preset name ("minimal", "standard", "intense", "custom")
        
    Returns:
        Dict with complexity settings
    """
    presets = {
        "minimal": {
            "num_static_structures": 0,
            "num_enemy_units": "low",
            "sam_density": "sparse",
            "objective_count": "few",
            "city_objectives": False,
        },
        "standard": {
            # Auto/defaults - use threat level
        },
        "intense": {
            "num_static_structures": 4,
            "num_enemy_units": "high",
            "sam_density": "dense",
            "objective_count": "many",
            "city_objectives": True,
            "static_structure_probability": 0.9,
        },
        "custom": {},  # Empty - user provides all
    }
    return presets.get(name.lower(), {})


def _process_complexity_config(complexity: Any) -> Dict[str, Any]:
    """
    Process complexity config: handle preset strings or dicts.
    
    Args:
        complexity: Can be:
            - str: Preset name ("minimal", "standard", "intense")
            - dict: Explicit complexity settings
            - None: Use defaults
            
    Returns:
        Processed complexity dict
    """
    if complexity is None:
        return {}
    
    if isinstance(complexity, str):
        # Preset string
        preset = create_complexity_preset(complexity)
        return preset
    
    if isinstance(complexity, dict):
        # If it's a preset name key, expand it
        if len(complexity) == 1 and "preset" in complexity:
            preset_name = complexity["preset"]
            preset = create_complexity_preset(preset_name)
            # Merge with any overrides
            overrides = {k: v for k, v in complexity.items() if k != "preset"}
            return {**preset, **overrides}
        
        # Otherwise, it's explicit settings
        return complexity
    
    return {}


__all__ = ["MissionConfig", "MissionPlan", "MissionDirector", "PlanObjective", "create_complexity_preset"]
