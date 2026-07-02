"""
Optional public-signal ranking adjustments.

Final feed decisions still happen at the video level. Public signals can tighten
scoring or request review, but they do not become a permanent blacklist.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..labeling.schema import LabelSet
from .explain import public_signal_reason
from .schema import (
    ChannelSafetyRecord,
    PublicSignalEffect,
    PublicSignalRecord,
    ChannelSafetyStatus,
)

MEDIUM_CONCERN = 0.35
HIGH_CONCERN = 0.65
SEVERE_CONCERN = 0.85
CONFIRMED_INTERNAL_RISK = 0.5


@dataclass
class PublicSignalContext:
    channel_signals: dict[str, PublicSignalRecord] = field(default_factory=dict)
    video_signals: dict[str, PublicSignalRecord] = field(default_factory=dict)
    channel_safety: dict[str, ChannelSafetyRecord] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> "PublicSignalContext":
        return cls()


@dataclass
class PublicSignalEvaluation:
    allowed: bool = True
    score_delta: float = 0.0
    effect: PublicSignalEffect = "none"
    reason: str | None = None
    source_safety_status: ChannelSafetyStatus = "neutral"
    public_signal: PublicSignalRecord | None = None
    requires_human_review: bool = False

    def to_item_fields(self) -> dict:
        return {
            "public_signal": (
                self.public_signal.to_public_dict()
                if self.public_signal and self.public_signal.has_evidence()
                else None
            ),
            "source_safety_status": self.source_safety_status,
            "public_signal_effect": self.effect,
            "public_signal_reason": self.reason,
        }


def evaluate_public_signal(
    item: dict,
    labels: LabelSet,
    context: PublicSignalContext | None = None,
    public_signal_override: bool = False,
) -> PublicSignalEvaluation:
    if context is None:
        return PublicSignalEvaluation()

    channel_id = str(item.get("channel_id") or "")
    video_id = str(item.get("video_id") or item.get("youtube_id") or "")

    channel_signal = context.channel_signals.get(channel_id) if channel_id else None
    video_signal = context.video_signals.get(video_id) if video_id else None
    safety = context.channel_safety.get(channel_id) if channel_id else None

    selected_signal = _strongest_signal(video_signal, channel_signal)
    status = _source_status(safety, channel_signal)

    if status == "do_not_recommend" and not public_signal_override:
        effect: PublicSignalEffect = "excluded"
        return PublicSignalEvaluation(
            allowed=False,
            effect=effect,
            reason=public_signal_reason(effect, selected_signal),
            source_safety_status=status,
            public_signal=selected_signal,
            requires_human_review=True,
        )

    concern = _combined_concern(channel_signal, video_signal)
    if status == "caution":
        concern = max(concern, MEDIUM_CONCERN)

    requires_review = bool(
        (safety and safety.requires_human_review)
        or (channel_signal and channel_signal.requires_human_review)
        or (video_signal and video_signal.requires_human_review)
    )

    if concern < MEDIUM_CONCERN and not requires_review:
        return PublicSignalEvaluation(
            source_safety_status=status,
            public_signal=selected_signal,
        )

    if (
        concern >= SEVERE_CONCERN
        and _internal_risk_confirmed(labels)
        and not public_signal_override
    ):
        effect = "excluded"
        return PublicSignalEvaluation(
            allowed=False,
            effect=effect,
            reason=public_signal_reason(effect, selected_signal),
            source_safety_status=status,
            public_signal=selected_signal,
            requires_human_review=True,
        )

    internal_risk = _internal_risk_score(labels)
    if concern >= SEVERE_CONCERN and not _internal_risk_confirmed(labels):
        effect = "allowed_low_video_risk"
        score_delta = -0.08
    elif requires_review or concern >= HIGH_CONCERN:
        effect = "requires_review"
        score_delta = -(0.16 + 0.14 * internal_risk)
    else:
        effect = "stricter_scoring"
        score_delta = -(0.06 + 0.10 * internal_risk)

    return PublicSignalEvaluation(
        score_delta=score_delta,
        effect=effect,
        reason=public_signal_reason(effect, selected_signal),
        source_safety_status=status,
        public_signal=selected_signal,
        requires_human_review=requires_review,
    )


def _combined_concern(*records: PublicSignalRecord | None) -> float:
    concern = 0.0
    for record in records:
        if record is not None:
            concern = max(concern, record.concern_score * record.confidence)
    return concern


def _strongest_signal(
    *records: PublicSignalRecord | None,
) -> PublicSignalRecord | None:
    evidence = [r for r in records if r is not None and r.has_evidence()]
    if not evidence:
        return None
    return max(
        evidence,
        key=lambda r: (
            r.concern_score * r.confidence,
            r.support_score * r.confidence,
            r.evidence_count,
        ),
    )


def _source_status(
    safety: ChannelSafetyRecord | None,
    channel_signal: PublicSignalRecord | None,
) -> ChannelSafetyStatus:
    if safety is not None:
        return safety.status
    if channel_signal is None:
        return "neutral"
    if channel_signal.support_score >= 0.65 and channel_signal.concern_score < 0.25:
        return "trusted"
    if channel_signal.concern_score >= MEDIUM_CONCERN or channel_signal.requires_human_review:
        return "caution"
    return "neutral"


def _internal_risk_score(labels: LabelSet) -> float:
    return max(
        labels.overall_risk,
        labels.comparison_risk,
        labels.appearance_focus,
        labels.shame_or_humiliation_risk,
        labels.ragebait,
        labels.misinformation_risk,
    )


def _internal_risk_confirmed(labels: LabelSet) -> bool:
    return _internal_risk_score(labels) >= CONFIRMED_INTERNAL_RISK

