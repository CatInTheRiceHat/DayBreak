"""Chrysalis video labeling (v1) — cheap metadata scan into a normalized LabelSet."""

from .schema import LabelSet, LABEL_DIMENSIONS, POSITIVE_DIMS, RISK_DIMS, SCORING_VERSION
from .metadata_scoring import score_metadata
from .explain import build_reasons

__all__ = [
    "LabelSet",
    "LABEL_DIMENSIONS",
    "POSITIVE_DIMS",
    "RISK_DIMS",
    "SCORING_VERSION",
    "score_metadata",
    "build_reasons",
]
