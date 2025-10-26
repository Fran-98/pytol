from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class EnvironmentController:
    """
    Translates high-level environment choices to Mission fields.
    
    Placeholder only—implementation deferred until late-stage polish.
    """
    time_of_day: Optional[str] = None  # day|dusk|night
    weather: Optional[str] = None      # clear|windy|stormy|custom

    def apply_to(self, mission) -> None:
        """Apply environment settings to a Mission. Placeholder does nothing."""
        _ = mission
        pass
