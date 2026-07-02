"""
Chrysalis label schema (v1).

Every video is normalized into a `LabelSet`: 16 wellbeing/risk dimensions plus a
confidence score, all on a 0–1 scale. This is the single source of truth for what
a "Chrysalis score" means; scorers (Layer 1 metadata, later Layer 2 thumbnails…)
populate it, ranking and explanation consume it.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, fields

SCORING_VERSION = "v1"

# Positive wellbeing signals — higher is better.
POSITIVE_DIMS: tuple[str, ...] = (
    "prosocial",
    "calm",
    "educational",
    "self_love",
    "diversity",
    "novelty",
    "reflection_value",
)

# Risk signals — higher is worse. `overall_risk` is an aggregate of the others.
RISK_DIMS: tuple[str, ...] = (
    "comparison_risk",
    "appearance_focus",
    "shame_or_humiliation_risk",
    "ragebait",
    "overstimulation",
    "consumerism",
    "age_safety_risk",
    "misinformation_risk",
    "overall_risk",
)

# All 16 scored dimensions, in a stable order (confidence is meta, not scored content).
LABEL_DIMENSIONS: tuple[str, ...] = POSITIVE_DIMS + RISK_DIMS


def clamp01(value: float) -> float:
    """Clamp any numeric-ish value into the [0, 1] range, treating junk as 0."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


@dataclass
class LabelSet:
    # Positive
    prosocial: float = 0.0
    calm: float = 0.0
    educational: float = 0.0
    self_love: float = 0.0
    diversity: float = 0.0
    novelty: float = 0.0
    reflection_value: float = 0.0
    # Risk
    comparison_risk: float = 0.0
    appearance_focus: float = 0.0
    shame_or_humiliation_risk: float = 0.0
    ragebait: float = 0.0
    overstimulation: float = 0.0
    consumerism: float = 0.0
    age_safety_risk: float = 0.0
    misinformation_risk: float = 0.0
    overall_risk: float = 0.0
    # Meta
    confidence: float = 0.0

    def clamped(self) -> "LabelSet":
        """Return a copy with every field clamped to [0, 1]."""
        return LabelSet(**{f.name: clamp01(getattr(self, f.name)) for f in fields(self)})

    def to_dict(self) -> dict:
        """Plain dict of all dimensions + confidence (JSON-serializable)."""
        return {k: clamp01(v) for k, v in asdict(self).items()}

    @classmethod
    def from_dict(cls, data: dict | None) -> "LabelSet":
        """Build a LabelSet from a (possibly partial) dict, ignoring unknown keys."""
        if not data:
            return cls()
        known = {f.name for f in fields(cls)}
        return cls(**{k: clamp01(v) for k, v in data.items() if k in known})
