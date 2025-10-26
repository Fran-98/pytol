from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AltitudePolicy:
    """Chooses a default AGL based on mission type and threat density."""
    mission_type: str = "strike"

    def choose_agl(self, threat_level: float) -> float:
        """
        Return a suggested AGL (meters AGL). Placeholder heuristic:
        - Higher threat_level -> lower AGL for terrain masking in attack roles.
        """
        t = max(0.0, min(1.0, threat_level))
        if self.mission_type in {"strike", "cas", "sead"}:
            return 120 + (1.0 - t) * 380  # 120–500m AGL
        if self.mission_type in {"intercept"}:
            return 1500 + (1.0 - t) * 1500  # 1.5–3km AGL
        if self.mission_type in {"transport"}:
            return 50 + (1.0 - t) * 250  # 50–300m AGL
        return 400
