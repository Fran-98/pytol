"""A small, extensible grammar-based planner for mission generation.

Design goals:
- Simple rule format (Python dict) so grammars are easy to author and extend.
- Deterministic given a seed (rng injection).
- Terminals are simple format strings and expand into structured tokens.

Usage example:
    g = Grammar()
    g.add_rule('MISSION', ['OFFENSIVE_MISSION', 'DEFENSIVE_MISSION'], weights=[0.7, 0.3])
    g.add_rule('OFFENSIVE_MISSION', ['PLAYER_FLIGHT', 'SUPPORT_FLIGHTS', 'PRIMARY_TARGET_PACKAGE'])
    planner = Planner(g, rng=random.Random(seed))
    terminals = planner.expand('MISSION', context={...})
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import random


@dataclass
class Production:
    expansion: List[str]
    weight: float = 1.0


class Grammar:
    """Container for production rules.

    Each nonterminal maps to a list of Production objects. Expansions are
    lists of tokens (either other nonterminals or terminal format strings).
    """

    def __init__(self) -> None:
        self.rules: Dict[str, List[Production]] = {}

    def add_rule(self, nonterminal: str, expansions: List[List[str]] | List[str], weights: Optional[List[float]] = None) -> None:
        """Add one or more productions for a nonterminal.

        expansions can be a single list-of-tokens (one production) or a list of
        such lists. weights, if provided, must match the number of productions.
        """
        prods: List[Production] = []
        if expansions and isinstance(expansions[0], str):
            expansions = [expansions]  # type: ignore

        if weights is None:
            weights = [1.0] * len(expansions)  # type: ignore

        for exp, w in zip(expansions, weights):
            prods.append(Production(list(exp), float(w)))

        if nonterminal in self.rules:
            self.rules[nonterminal].extend(prods)
        else:
            self.rules[nonterminal] = prods

    def is_nonterminal(self, symbol: str) -> bool:
        return symbol in self.rules


class Planner:
    """Recursively expand a nonterminal into terminal tokens using the grammar.

    Terminals are plain strings. They may contain Python-format placeholders
    which will be replaced using the provided context mapping when finalizing
    terminal tokens.
    """

    def __init__(self, grammar: Grammar, rng: Optional[random.Random] = None) -> None:
        self.grammar = grammar
        self.rng = rng if rng is not None else random.Random()

    def _choose_production(self, nonterminal: str) -> Production:
        prods = self.grammar.rules.get(nonterminal, [])
        if not prods:
            raise KeyError(f"No productions for nonterminal: {nonterminal}")
        weights = [p.weight for p in prods]
        total = sum(weights)
        if total <= 0:
            # fallback to uniform
            return self.rng.choice(prods)
        pick = self.rng.random() * total
        upto = 0.0
        for p in prods:
            upto += p.weight
            if pick <= upto:
                return p
        return prods[-1]

    def expand(self, start: str, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Expand start symbol to a flat list of terminal token dicts.

        Returns a list of dicts representing terminal tokens. Each dict has a
        `symbol` field (the terminal formatted string) and `parts` array parsed
        from that string (split by ':').
        """
        context = context or {}
        results: List[Dict[str, Any]] = []

        def recurse(symbol: str) -> None:
            if self.grammar.is_nonterminal(symbol):
                prod = self._choose_production(symbol)
                for tok in prod.expansion:
                    recurse(tok)
            else:
                # Terminal: format it using context then parse
                try:
                    formatted = symbol.format(**context)
                except Exception:
                    formatted = symbol

                parts = [p for p in formatted.split(":") if p != ""]
                token = {"symbol": formatted, "parts": parts}
                results.append(token)

        recurse(start)
        return results


def build_default_mission_grammar(config: Optional[Dict[str, Any]] = None) -> Grammar:
    """Create the default narrative grammar with light-weight configurability.

    Args:
        config: Optional mapping containing mission knobs such as
            ``mission_archetype``, ``player_role``, ``threat_level``,
            ``world_liveliness`` and ``operational_environment``. Missing keys
            fall back to conservative defaults.
    """
    cfg = config or {}
    archetype = cfg.get("mission_archetype", "offensive").lower()
    player_role = cfg.get("player_role", "strike").lower()
    threat_level = cfg.get("threat_level", "medium").lower()
    liveliness = cfg.get("world_liveliness", "moderate").lower()
    environment = cfg.get("operational_environment", "land").lower()

    g = Grammar()

    # ------------------------------------------------------------------
    # Mission framing
    # ------------------------------------------------------------------
    g.add_rule("MISSION", [["PLAYER_PACKAGE", "PRIMARY_OBJECTIVES", "SECONDARY_OBJECTIVES", "SUPPORT_ELEMENTS", "BACKGROUND_ACTIVITY", "REINFORCEMENT_TRIGGERS"]])

    # Player task based on role
    player_target = cfg.get("primary_target")
    if not player_target:
        player_target = "enemy_fleet" if environment in {"naval", "littoral"} else "enemy_airbase"
    if player_role in {"cap", "intercept"}:
        player_desc = "defend_friendly_airspace"
    elif player_role in {"recon"}:
        player_desc = "recon_sector"
    else:
        player_desc = player_target
    g.add_rule("PLAYER_PACKAGE", [["PLAYER_TASK:{player_role}:" + player_desc]])

    # Primary objectives vary by archetype
    primary_expansions: List[List[str]] = []
    primary_weights: List[float] = []

    if archetype in {"offensive", "strike"}:
        primary_expansions.extend([
            ["SPAWN:sam_site", "SPAWN:radar", "THREAT_LAYER:IADS_RING"],
            ["SPAWN:enemy_artillery_battery", "THREAT_LAYER:IADS_CORE"],
        ])
        primary_weights.extend([0.6, 0.4])
    if archetype in {"offensive", "sead"}:
        primary_expansions.append(["SPAWN:sam_site", "SPAWN:sam_site", "THREAT_LAYER:IADS_CORE"])
        primary_weights.append(0.5 if threat_level in {"high", "extreme"} else 0.3)
    if archetype in {"defensive", "intercept"}:
        primary_expansions.append(["SPAWN:enemy_cap_flight", "THREAT_LAYER:CAP_RING"])
        primary_weights.append(0.5)
    if archetype in {"defensive", "escort"}:
        primary_expansions.append(["SPAWN:enemy_convoy_screen", "THREAT_LAYER:CAP_SUPPORT"])
        primary_weights.append(0.3)

    if not primary_expansions:
        primary_expansions = [["SPAWN:enemy_unit", "THREAT_LAYER:IADS_RING"]]
        primary_weights = [1.0]
    g.add_rule("PRIMARY_OBJECTIVES", primary_expansions, weights=primary_weights)

    # Secondary objectives vary by archetype and threat level
    secondary_expansions: List[List[str]] = [[]]
    secondary_weights: List[float] = [0.3]  # 30% chance of no secondary objectives
    
    if archetype in {"offensive", "strike", "sead"}:
        secondary_expansions.extend([
            ["SECONDARY_OBJECTIVE:sam_network"],
            ["SECONDARY_OBJECTIVE:suppress_air_defenses"],
        ])
        secondary_weights.extend([0.4 if threat_level in {"high", "extreme"} else 0.3, 0.3])
    
    if archetype in {"cas"}:
        secondary_expansions.extend([
            ["SECONDARY_OBJECTIVE:artillery_battery"],
            ["SECONDARY_OBJECTIVE:clear_route"],
        ])
        secondary_weights.extend([0.4, 0.3])
    
    if archetype in {"defensive", "intercept"}:
        secondary_expansions.extend([
            ["SECONDARY_OBJECTIVE:defend_base"],
            ["SECONDARY_OBJECTIVE:escort_package"],
        ])
        secondary_weights.extend([0.4, 0.3])
    
    # Optional objectives (bonus targets)
    if threat_level in {"high", "extreme"}:
        secondary_expansions.extend([
            ["OPTIONAL_OBJECTIVE:convoy"],
            ["OPTIONAL_OBJECTIVE:bonus_targets"],
        ])
        secondary_weights.extend([0.2, 0.15])
    
    g.add_rule("SECONDARY_OBJECTIVES", secondary_expansions, weights=secondary_weights)

    # Support packages
    if archetype in {"defensive"} or player_role in {"cap"}:
        g.add_rule("SUPPORT_ELEMENTS", [["AI_TASK:CAP:frontline", "SUPPORT_OPTIONAL"]])
        g.add_rule(
            "SUPPORT_OPTIONAL",
            [
                [],
                ["AI_TASK:AWACS:theater"],
                ["AI_TASK:TANKER:player_area"],
                ["AI_TASK:ESCORT:primary_package"],
            ],
            weights=[0.4, 0.25, 0.2, 0.15],
        )
    else:
        support_expansions: List[List[str]] = [[]]
        support_weights: List[float] = [0.2]
        support_expansions.extend([
            ["AI_TASK:ESCORT:primary_package"],
            ["AI_TASK:TANKER:player_area"],
            ["AI_TASK:AWACS:theater"],
        ])
        support_weights.extend([0.4, 0.3, 0.3])
        if (player_role in {"sead", "strike"} or threat_level in {"high", "extreme"}):
            support_expansions.append(["AI_TASK:CAP:frontline"])
            support_weights.append(0.35)
        g.add_rule("SUPPORT_ELEMENTS", support_expansions, weights=support_weights)

    # Background liveliness
    background_expansions: List[List[str]] = [[]]
    background_weights: List[float] = [0.5 if liveliness == "quiet" else 0.1]
    if liveliness in {"moderate", "busy"}:
        background_expansions.append(["SCHEDULE_BACKGROUND:enemy_convoy"])
        background_weights.append(0.4 if liveliness == "moderate" else 0.6)
        background_expansions.append(["SCHEDULE_BACKGROUND:civilian_traffic"])
        background_weights.append(0.3 if liveliness == "moderate" else 0.5)
    if liveliness == "busy":
        background_expansions.append(["SCHEDULE_BACKGROUND:enemy_patrols"])
        background_weights.append(0.5)
    g.add_rule("BACKGROUND_ACTIVITY", background_expansions, weights=background_weights)

    # Reinforcement triggers (higher threat = more reinforcements)
    reinforcement_prob = {"low": 0.1, "medium": 0.3, "high": 0.5, "extreme": 0.7}.get(threat_level, 0.3)
    if reinforcement_prob > 0:
        # Add reinforcement rule based on threat level
        reinforcement_expansions: List[List[str]] = [[]]
        reinforcement_weights: List[float] = [1.0 - reinforcement_prob]
        if archetype in {"offensive", "strike", "sead"}:
            reinforcement_expansions.append(["REINFORCEMENT:sam_reinforcement"])
            reinforcement_weights.append(reinforcement_prob * 0.6)
        if archetype in {"offensive", "strike"}:
            reinforcement_expansions.append(["REINFORCEMENT:aircraft_reinforcement"])
            reinforcement_weights.append(reinforcement_prob * 0.4)
        g.add_rule("REINFORCEMENT_TRIGGERS", reinforcement_expansions, weights=reinforcement_weights)
    else:
        g.add_rule("REINFORCEMENT_TRIGGERS", [[]])

    return g


__all__ = ["Grammar", "Planner", "build_default_mission_grammar"]
