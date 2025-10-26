from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class EventNode:
    """Lightweight event node placeholder (trigger+actions)."""
    name: str
    delay: float = 0.0
    actions: List[object] = field(default_factory=list)  # Will map to EventTarget later


@dataclass
class EventGraph:
    """Container for a linearized event sequence for now (DAG later)."""
    nodes: List[EventNode] = field(default_factory=list)

    def add(self, node: EventNode) -> None:
        self.nodes.append(node)
