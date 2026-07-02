"""Tests for the content taxonomy (core/labeling/taxonomy.py)."""

import json
from pathlib import Path

from core.labeling.metadata_scoring import score_metadata
from core.labeling.schema import LabelSet
from core.labeling.taxonomy import (
    CONTENT_CATEGORIES,
    HEALTHY_CATEGORIES,
    classify_content,
    is_healthy_category,
)

ROOT = Path(__file__).resolve().parent.parent
SEED_FILE = ROOT / "datasets" / "seed_videos.json"


def classify_meta(meta: dict):
    """Classify a raw row through the real scorer + taxonomy (end to end)."""
    return classify_content(score_metadata(meta), meta)


# derived scores / structure

def test_to_dict_has_all_taxonomy_fields():
    tax = classify_content(LabelSet(), {})
    keys = set(tax.to_dict())
    assert keys == {
        "content_category",
        "wellness_score",
        "positivity_score",
        "conflict_score",
        "safety_risk",
        "perspective_topic",
    }


def test_category_is_always_known():
    tax = classify_meta({"title": "", "description": ""})
    assert tax.content_category in CONTENT_CATEGORIES


def test_scores_are_clamped_unit_interval():
    tax = classify_meta({
        "title": "calm kindness walk journal gratitude friends",
        "description": "self love calm reflection walking touch grass drink water",
    })
    for value in (tax.wellness_score, tax.positivity_score, tax.conflict_score, tax.safety_risk):
        assert 0.0 <= value <= 1.0


# healthy / wellness

def test_calming_advice_is_healthy():
    tax = classify_meta({
        "title": "A calm reminder: you are enough, just as you are",
        "description": "A gentle affirmation and self compassion reminder to breathe and be kind to yourself.",
        "tags": ["self love", "affirmation", "calm"],
    })
    assert tax.content_category == "healthy"
    assert tax.wellness_score >= 0.45


def test_offline_activity_prompt_is_healthy():
    tax = classify_meta({
        "title": "Your reminder to drink water and stretch right now",
        "description": "Grab some water, stretch, take a break, and go for a short walk outside.",
        "tags": ["hydrate", "walk", "stretch"],
    })
    assert tax.content_category == "healthy"


def test_journaling_prompt_is_healthy():
    tax = classify_meta({
        "title": "5-minute journaling prompt to reset your evening",
        "description": "A reflective journaling exercise. Notice one thing you're grateful for.",
        "tags": ["journal", "gratitude"],
    })
    assert tax.content_category == "healthy"


# positive general

def test_wholesome_good_news_is_positive_or_healthy():
    tax = classify_meta({
        "title": "Strangers come together to surprise a local hero",
        "description": "A heartwarming, wholesome moment of people coming together to say thank you. Uplifting good news.",
        "tags": ["wholesome", "good news", "uplifting"],
    })
    assert tax.content_category in {"positive", "healthy"}
    assert is_healthy_category(tax.content_category)


# regular entertainment

def test_plain_comedy_is_regular():
    tax = classify_meta({
        "title": "Trying the viral try-not-to-laugh challenge",
        "description": "Me and my friends attempt the funniest trending comedy clips.",
        "tags": ["comedy", "funny", "trend"],
    })
    assert tax.content_category == "regular"
    assert not is_healthy_category(tax.content_category)


def test_pop_music_video_is_regular():
    tax = classify_meta({
        "title": "New pop song of the summer - official music video",
        "description": "The official music video for the upbeat pop single everyone is playing.",
        "topic": "music",
        "tags": ["pop", "music"],
    })
    assert tax.content_category == "regular"


# perspective

def test_diverse_perspective_is_perspective_with_topic():
    tax = classify_meta({
        "title": "Two friends share different perspectives on the same city",
        "description": "A calm, respectful conversation where two people see it differently and find common ground. Both sides, open-minded.",
        "tags": ["perspective", "respectful"],
    })
    assert tax.content_category == "perspective"
    assert tax.perspective_topic is not None


def test_perspective_topic_only_set_for_perspective_category():
    tax = classify_meta({
        "title": "Top 10 goals from this weekend's matches",
        "description": "A roundup of the best football highlights.",
        "topic": "sports",
    })
    assert tax.content_category != "perspective"
    assert tax.perspective_topic is None


# reduced

def test_ragebait_is_reduced():
    tax = classify_meta({
        "title": "You won't believe this RANT - she got DESTROYED and exposed",
        "description": "Drama, beef, and outrage. This will make you angry. Controversial clapback.",
        "tags": ["drama", "rant", "exposed"],
    })
    assert tax.content_category == "reduced"
    assert tax.conflict_score >= 0.45


def test_comparison_heavy_is_reduced():
    tax = classify_meta({
        "title": "Rating people out of 10 - who is prettier?",
        "description": "Hot or not tier list, am i pretty, rate my look compared to everyone.",
        "tags": ["rate me", "hot or not"],
    })
    assert tax.content_category in {"reduced", "blocked"}


# blocked (harmful)

def test_self_harm_content_is_blocked():
    tax = classify_meta({
        "title": "graphic self harm and suicide vlog",
        "description": "disturbing footage, self-harm and suicidal content.",
    })
    assert tax.content_category == "blocked"
    assert tax.safety_risk >= 0.7


def test_eating_disorder_promo_is_blocked():
    tax = classify_meta({
        "title": "pro ana thinspo: how to starve yourself",
        "description": "anorexia tips and bonespo.",
    })
    assert tax.content_category == "blocked"


def test_supportive_recovery_content_is_not_blocked():
    # Same harmful keywords, but clearly supportive/preventative context.
    tax = classify_meta({
        "title": "Eating disorder recovery: you are not alone",
        "description": "A supportive, gentle awareness video about recovering from an eating disorder. Reach out for support.",
        "tags": ["recovery", "support", "awareness"],
    })
    assert tax.content_category != "blocked"


# seed dataset integrity

def test_seed_file_classifies_to_expected_categories():
    data = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    mismatches = []
    for seed in data["videos"]:
        expected = seed.get("expected_category")
        if not expected:
            continue
        tax = classify_meta(seed)
        if tax.content_category != expected:
            mismatches.append((seed["youtube_video_id"], expected, tax.content_category))
    assert not mismatches, f"seed category mismatches: {mismatches}"


def test_seed_file_has_no_harmful_seeds():
    data = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    for seed in data["videos"]:
        tax = classify_meta(seed)
        assert tax.content_category not in {"blocked", "reduced"}, seed["youtube_video_id"]


def test_healthy_categories_subset_of_all_categories():
    assert HEALTHY_CATEGORIES.issubset(set(CONTENT_CATEGORIES))
