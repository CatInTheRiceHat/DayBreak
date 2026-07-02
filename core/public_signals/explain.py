"""
Gentle public-signal explanations.

These strings are intentionally non-accusatory. Public signals are context for
ranking and review, not creator labels for users to judge.
"""

from __future__ import annotations

from .schema import PublicSignalRecord


def concern_bucket(record: PublicSignalRecord | None) -> str:
    if record is None:
        return "source review signals"
    concerns = " ".join(record.main_concerns).lower()
    if "comparison" in concerns or "appearance" in concerns or "shame" in concerns:
        return "comparison-heavy or shame-based framing"
    if "harassment" in concerns or "bullying" in concerns:
        return "harassment or bullying concerns"
    if "health" in concerns or "diet" in concerns or "misleading" in concerns:
        return "health-claim concerns"
    if "consumer" in concerns or "status" in concerns:
        return "status-pressure signals"
    if "rage" in concerns or "drama" in concerns:
        return "high-conflict framing"
    return "unresolved source review signals"


def public_signal_reason(effect: str, record: PublicSignalRecord | None = None) -> str | None:
    if effect == "none":
        return None
    if effect == "stricter_scoring":
        return "This video was ranked with extra care because the source has unresolved review signals."
    if effect == "downranked":
        return "This video was ranked lower because the source has unresolved review signals."
    if effect == "requires_review":
        return (
            "This source is being reviewed because repeated public signals mention "
            f"{concern_bucket(record)}."
        )
    if effect == "allowed_low_video_risk":
        return (
            "This video was allowed because its video-level scan was low-risk "
            "despite a cautious source record."
        )
    if effect == "excluded":
        return "This source has an active review hold, so it was not recommended."
    return None


def safety_record_reason(record: PublicSignalRecord | None) -> str | None:
    if record is None or record.concern_score < 0.35:
        return None
    return (
        "Source review signal: public context mentions "
        f"{concern_bucket(record)}."
    )

