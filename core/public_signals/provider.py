"""
Public signal provider abstraction and v1 stub.

v1 intentionally does not scrape the web or call an unapproved public-search
source. The stub provider supplies neutral cache records for unknown targets and
fictional sample records for tests/demo wiring.
"""

from __future__ import annotations

from typing import Protocol

from .schema import PublicSignalRecord, expiry_iso, iso_utc


class PublicSignalProvider(Protocol):
    name: str

    def scan_channel(self, channel_id: str, channel_title: str = "") -> PublicSignalRecord:
        ...

    def scan_video(self, video_id: str, metadata: dict | None = None) -> PublicSignalRecord:
        ...


class StubPublicSignalProvider:
    """Deterministic no-network provider with fictional sample targets only."""

    name = "stub-public-signal-provider"

    _CHANNEL_SAMPLES = {
        "fictional-trusted-channel": {
            "concern_score": 0.02,
            "support_score": 0.82,
            "confidence": 0.72,
            "supportive_signals": ["consistent educational framing", "community support"],
            "evidence_count": 5,
            "source_quality": "strong",
            "recency": "recent",
            "summary": "Fictional sample: public context is consistently supportive.",
        },
        "fictional-comparison-lab": {
            "concern_score": 0.48,
            "support_score": 0.18,
            "confidence": 0.66,
            "main_concerns": ["appearance comparison", "consumerism/status pressure"],
            "evidence_count": 3,
            "source_quality": "mixed",
            "recency": "mixed",
            "summary": "Fictional sample: repeated public signals mention comparison-heavy framing.",
        },
        "fictional-review-needed": {
            "concern_score": 0.72,
            "support_score": 0.08,
            "confidence": 0.74,
            "main_concerns": ["humiliation framing", "drama farming"],
            "evidence_count": 6,
            "source_quality": "mixed",
            "recency": "recent",
            "requires_human_review": True,
            "summary": "Fictional sample: unresolved review signals need human context.",
        },
        "fictional-severe-channel": {
            "concern_score": 0.92,
            "support_score": 0.04,
            "confidence": 0.82,
            "main_concerns": ["harassment", "shame-based framing"],
            "evidence_count": 8,
            "source_quality": "strong",
            "recency": "recent",
            "requires_human_review": True,
            "summary": "Fictional sample: severe public concern signals require review.",
        },
    }

    _VIDEO_SAMPLES = {
        "fictional-video-review": {
            "concern_score": 0.7,
            "support_score": 0.05,
            "confidence": 0.7,
            "main_concerns": ["misleading health advice", "unsafe dieting"],
            "evidence_count": 4,
            "source_quality": "mixed",
            "recency": "recent",
            "requires_human_review": True,
            "summary": "Fictional sample: video-level public context requires review.",
        },
    }

    def scan_channel(self, channel_id: str, channel_title: str = "") -> PublicSignalRecord:
        sample = self._CHANNEL_SAMPLES.get(channel_id)
        if sample is None:
            return PublicSignalRecord.neutral("channel", channel_id)
        return self._record("channel", channel_id, sample)

    def scan_video(self, video_id: str, metadata: dict | None = None) -> PublicSignalRecord:
        sample = self._VIDEO_SAMPLES.get(video_id)
        if sample is None:
            return PublicSignalRecord.neutral("video", video_id)
        return self._record("video", video_id, sample)

    @staticmethod
    def _record(target_type: str, target_id: str, data: dict) -> PublicSignalRecord:
        requires_review = bool(data.get("requires_human_review", False))
        return PublicSignalRecord(
            target_type=target_type,
            target_id=target_id,
            concern_score=data.get("concern_score", 0.0),
            support_score=data.get("support_score", 0.0),
            confidence=data.get("confidence", 0.0),
            main_concerns=list(data.get("main_concerns", [])),
            supportive_signals=list(data.get("supportive_signals", [])),
            evidence_count=data.get("evidence_count", 0),
            source_quality=data.get("source_quality", "weak"),
            recency=data.get("recency", "old"),
            requires_human_review=requires_review,
            summary=data.get("summary", ""),
            last_checked=iso_utc(),
            expires_at=expiry_iso(requires_review),
        )

