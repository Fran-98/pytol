from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class RadioCommsHelper:
    """
    Generates radio line suggestions aligned to mission beats.
    
    Placeholder only—implementation deferred until late-stage polish.
    """

    def opening_calls(self, mission_type: str) -> List[str]:
        """Return suggested opening radio lines. Placeholder returns empty list."""
        _ = mission_type
        return []
