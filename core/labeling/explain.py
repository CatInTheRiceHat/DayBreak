"""
Layer 7 — explainability (v1).

Turns a `LabelSet` into short, user-facing strings:
  ranking_reason  — why this video is being shown (always present)
  safety_reason   — brief reassurance about low-risk signals (when applicable)
  concern_reason  — surfaced ONLY when a risk dimension is notably high

Tone is positive/neutral and user-facing. It never exposes internal creator-risk
phrasing or raw debug numbers.
"""

from __future__ import annotations

from .schema import LabelSet, POSITIVE_DIMS, RISK_DIMS

# Threshold above which a risk dimension is worth mentioning to the user.
CONCERN_THRESHOLD = 0.5
# Threshold above which a positive dimension is "high" enough to cite.
HIGHLIGHT_THRESHOLD = 0.3

_MODE_LABEL = {
    "daily-dew": "your Daily Dew intention",
    "metamorphosis": "Metamorphosis Mode",
    "flutter-feed": "your Flutter Feed",
}

# Friendly phrasing for positive dimensions in `ranking_reason`.
_POSITIVE_PHRASE = {
    "calm": "calm, gentle language",
    "prosocial": "kind, community-minded content",
    "educational": "something to learn",
    "self_love": "self-compassion",
    "reflection_value": "room to reflect",
    "novelty": "a fresh perspective",
    "diversity": "topic variety",
}

# Friendly phrasing for risk dimensions in `concern_reason`.
_RISK_PHRASE = {
    "comparison_risk": "social comparison",
    "appearance_focus": "appearance pressure",
    "shame_or_humiliation_risk": "shame or humiliation",
    "ragebait": "outrage-bait",
    "overstimulation": "high-intensity stimulation",
    "consumerism": "status or consumerism",
    "age_safety_risk": "content that may not suit younger viewers",
    "misinformation_risk": "claims worth double-checking",
    "overall_risk": "elevated wellbeing risk",
}


def _top_positive(labels: LabelSet, n: int = 2) -> list[str]:
    ranked = sorted(
        ((d, getattr(labels, d)) for d in POSITIVE_DIMS),
        key=lambda kv: kv[1],
        reverse=True,
    )
    return [d for d, v in ranked if v >= HIGHLIGHT_THRESHOLD][:n]


def _top_risk(labels: LabelSet) -> tuple[str, float] | None:
    # Ignore the aggregate `overall_risk` when picking a specific concern to name.
    specific = [d for d in RISK_DIMS if d != "overall_risk"]
    ranked = sorted(((d, getattr(labels, d)) for d in specific),
                    key=lambda kv: kv[1], reverse=True)
    if ranked and ranked[0][1] >= CONCERN_THRESHOLD:
        return ranked[0]
    if labels.overall_risk >= CONCERN_THRESHOLD:
        return ("overall_risk", labels.overall_risk)
    return None


def _join(parts: list[str]) -> str:
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def build_reasons(labels: LabelSet, mode: str) -> dict:
    """Return {ranking_reason, safety_reason, concern_reason} for a labeled video."""
    mode_label = _MODE_LABEL.get(mode, "your feed")

    # ── ranking_reason ──
    positives = [_POSITIVE_PHRASE[d] for d in _top_positive(labels) if d in _POSITIVE_PHRASE]
    low_risk = labels.overall_risk < CONCERN_THRESHOLD

    pieces: list[str] = []
    if positives:
        pieces.append(_join(positives))
    if low_risk:
        pieces.append("low comparison risk")
    if pieces:
        ranking_reason = f"Shown because it has {_join(pieces)}, and matches {mode_label}."
    else:
        ranking_reason = f"Shown as a gentle option for {mode_label}."

    # ── safety_reason ──
    if low_risk:
        safety_reason = "Screened by Chrysalis: low comparison, shame, and overstimulation signals."
    else:
        safety_reason = "Included with care — Chrysalis flagged some signals to watch."

    # ── concern_reason (only when warranted) ──
    concern_reason = None
    top_risk = _top_risk(labels)
    if top_risk is not None:
        dim, _ = top_risk
        concern_reason = f"Heads up: this leans toward {_RISK_PHRASE.get(dim, 'some risk')}."

    return {
        "ranking_reason": ranking_reason,
        "safety_reason": safety_reason,
        "concern_reason": concern_reason,
    }
