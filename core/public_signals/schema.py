"""
Structured public-signal records for Chrysalis v1.

This layer stores review/context signals about a source or video without making
permanent creator judgments. Records expire, carry confidence/source quality, and
are phrased for downstream ranking/explanation rather than accusation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import json
from typing import Literal

from ..labeling.schema import clamp01

PUBLIC_SIGNAL_VERSION = "public-signals-v1"

TargetType = Literal["channel", "video"]
SourceQuality = Literal["weak", "mixed", "strong"]
Recency = Literal["old", "mixed", "recent"]
ChannelSafetyStatus = Literal["trusted", "neutral", "caution", "do_not_recommend"]
PublicSignalEffect = Literal[
    "none",
    "stricter_scoring",
    "downranked",
    "requires_review",
    "excluded",
    "allowed_low_video_risk",
]

TARGET_TYPES = ("channel", "video")
SOURCE_QUALITIES = ("weak", "mixed", "strong")
RECENCY_VALUES = ("old", "mixed", "recent")
CHANNEL_SAFETY_STATUSES = ("trusted", "neutral", "caution", "do_not_recommend")

DEFAULT_EXPIRY_DAYS = 14
REVIEW_EXPIRY_DAYS = 7


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: datetime | None = None) -> str:
    dt = value or utc_now()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    try:
        normalized = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def expiry_iso(requires_review: bool = False, now: datetime | None = None) -> str:
    base = now or utc_now()
    days = REVIEW_EXPIRY_DAYS if requires_review else DEFAULT_EXPIRY_DAYS
    return iso_utc(base + timedelta(days=days))


def coerce_iso(value, fallback: str | None = None) -> str:
    dt = parse_iso(value)
    if dt is not None:
        return iso_utc(dt)
    return fallback or iso_utc()


def _coerce_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return [value] if value else []
        value = parsed
    if not isinstance(value, list):
        return []
    return [str(v) for v in value if str(v).strip()]


def _coerce_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value in (1, "1", "true", "True", "TRUE"):
        return True
    return False


def _enum(value: str | None, allowed: tuple[str, ...], fallback: str) -> str:
    return value if value in allowed else fallback


@dataclass
class PublicSignalRecord:
    target_type: TargetType
    target_id: str
    concern_score: float = 0.0
    support_score: float = 0.0
    confidence: float = 0.0
    main_concerns: list[str] = field(default_factory=list)
    supportive_signals: list[str] = field(default_factory=list)
    evidence_count: int = 0
    source_quality: SourceQuality = "weak"
    recency: Recency = "old"
    requires_human_review: bool = False
    summary: str = ""
    last_checked: str = field(default_factory=iso_utc)
    expires_at: str = field(default_factory=expiry_iso)

    def __post_init__(self) -> None:
        self.target_type = _enum(self.target_type, TARGET_TYPES, "channel")  # type: ignore[assignment]
        self.target_id = str(self.target_id)
        self.concern_score = clamp01(self.concern_score)
        self.support_score = clamp01(self.support_score)
        self.confidence = clamp01(self.confidence)
        self.main_concerns = _coerce_list(self.main_concerns)
        self.supportive_signals = _coerce_list(self.supportive_signals)
        self.evidence_count = max(0, int(self.evidence_count or 0))
        self.source_quality = _enum(self.source_quality, SOURCE_QUALITIES, "weak")  # type: ignore[assignment]
        self.recency = _enum(self.recency, RECENCY_VALUES, "old")  # type: ignore[assignment]
        self.requires_human_review = bool(self.requires_human_review)
        self.summary = str(self.summary or "")
        self.last_checked = coerce_iso(self.last_checked)
        self.expires_at = coerce_iso(self.expires_at, expiry_iso(self.requires_human_review))

    @classmethod
    def neutral(cls, target_type: TargetType, target_id: str) -> "PublicSignalRecord":
        return cls(
            target_type=target_type,
            target_id=target_id,
            source_quality="weak",
            recency="old",
            summary="No current public concern signal is cached for this target.",
        )

    @classmethod
    def from_row(cls, row: dict | None) -> "PublicSignalRecord | None":
        if not row:
            return None
        return cls(
            target_type=row.get("target_type", "channel"),
            target_id=row.get("target_id", ""),
            concern_score=row.get("concern_score", 0.0),
            support_score=row.get("support_score", 0.0),
            confidence=row.get("confidence", 0.0),
            main_concerns=_coerce_list(row.get("main_concerns")),
            supportive_signals=_coerce_list(row.get("supportive_signals")),
            evidence_count=row.get("evidence_count", 0),
            source_quality=row.get("source_quality", "weak"),
            recency=row.get("recency", "old"),
            requires_human_review=_coerce_bool(row.get("requires_human_review")),
            summary=row.get("summary", ""),
            last_checked=row.get("last_checked") or iso_utc(),
            expires_at=row.get("expires_at") or expiry_iso(),
        )

    def is_expired(self, now: datetime | None = None) -> bool:
        expires = parse_iso(self.expires_at)
        if expires is None:
            return True
        return expires <= (now or utc_now())

    def has_evidence(self) -> bool:
        return (
            self.evidence_count > 0
            or self.concern_score > 0.0
            or self.support_score > 0.0
            or bool(self.main_concerns)
            or bool(self.supportive_signals)
        )

    def to_public_dict(self) -> dict:
        return {
            "target_type": self.target_type,
            "target_id": self.target_id,
            "concern_score": clamp01(self.concern_score),
            "support_score": clamp01(self.support_score),
            "confidence": clamp01(self.confidence),
            "main_concerns": list(self.main_concerns),
            "supportive_signals": list(self.supportive_signals),
            "evidence_count": max(0, int(self.evidence_count)),
            "source_quality": self.source_quality,
            "recency": self.recency,
            "requires_human_review": bool(self.requires_human_review),
            "summary": self.summary,
            "last_checked": self.last_checked,
            "expires_at": self.expires_at,
        }


@dataclass
class ChannelSafetyRecord:
    channel_id: str
    channel_title: str = ""
    status: ChannelSafetyStatus = "neutral"
    requires_human_review: bool = False
    reason: str | None = None
    signal_target_type: TargetType | None = None
    signal_target_id: str | None = None
    last_checked: str = field(default_factory=iso_utc)
    review_after: str = field(default_factory=expiry_iso)
    expires_at: str = field(default_factory=expiry_iso)

    def __post_init__(self) -> None:
        self.channel_id = str(self.channel_id)
        self.channel_title = str(self.channel_title or "")
        self.status = _enum(self.status, CHANNEL_SAFETY_STATUSES, "neutral")  # type: ignore[assignment]
        self.requires_human_review = bool(self.requires_human_review)
        self.reason = str(self.reason) if self.reason else None
        self.last_checked = coerce_iso(self.last_checked)
        self.review_after = coerce_iso(self.review_after, expiry_iso(self.requires_human_review))
        self.expires_at = coerce_iso(self.expires_at, expiry_iso(self.requires_human_review))

    @classmethod
    def neutral(cls, channel_id: str, channel_title: str = "") -> "ChannelSafetyRecord":
        return cls(channel_id=channel_id, channel_title=channel_title)

    @classmethod
    def from_row(cls, row: dict | None) -> "ChannelSafetyRecord | None":
        if not row:
            return None
        return cls(
            channel_id=row.get("channel_id", ""),
            channel_title=row.get("channel_title", ""),
            status=row.get("status", "neutral"),
            requires_human_review=_coerce_bool(row.get("requires_human_review")),
            reason=row.get("reason"),
            signal_target_type=row.get("signal_target_type"),
            signal_target_id=row.get("signal_target_id"),
            last_checked=row.get("last_checked") or iso_utc(),
            review_after=row.get("review_after") or expiry_iso(),
            expires_at=row.get("expires_at") or expiry_iso(),
        )

    def is_expired(self, now: datetime | None = None) -> bool:
        expires = parse_iso(self.expires_at)
        if expires is None:
            return True
        return expires <= (now or utc_now())

    def to_dict(self) -> dict:
        return {
            "channel_id": self.channel_id,
            "channel_title": self.channel_title,
            "status": self.status,
            "requires_human_review": bool(self.requires_human_review),
            "reason": self.reason,
            "signal_target_type": self.signal_target_type,
            "signal_target_id": self.signal_target_id,
            "last_checked": self.last_checked,
            "review_after": self.review_after,
            "expires_at": self.expires_at,
        }
