from __future__ import annotations

from core.feed_integrity import INTEGRITY_MIN_SCORE, score_feed_integrity


def test_safe_low_budget_amateur_video_is_valid():
    result = score_feed_integrity({
        "video_id": "awkward-pottery",
        "title": "My awkward phone vlog about tiny clay frogs",
        "description": "Low budget day in my life making a little pottery shelf at home.",
        "channel_title": "Elaine Makes Stuff",
        "tags": ["vlog", "pottery", "home video"],
        "view_count": 37,
        "duration_seconds": 54,
    })

    assert result["integrity_score"] >= INTEGRITY_MIN_SCORE
    assert result["creator_scale"] == "small"
    assert result["production_style"] in {"casual", "low_budget", "amateur"}
    assert "unsafe_or_ragebait" not in result["integrity_flags"]["negative"]
    assert "clickbait_spam" not in result["integrity_flags"]["negative"]


def test_harmless_cringe_word_is_not_filtered_by_itself():
    result = score_feed_integrity({
        "video_id": "niche-joke",
        "title": "Cringe but harmless niche pottery joke",
        "description": "A weird small creator sketch about trying to center clay.",
        "channel_title": "Tiny Kiln Club",
        "tags": ["comedy", "pottery", "sketch"],
        "view_count": 212,
        "thumbnail_url": "https://example.com/thumb.jpg",
        "duration_seconds": 31,
    })

    assert result["integrity_score"] >= INTEGRITY_MIN_SCORE
    assert "unsafe_or_ragebait" not in result["integrity_flags"]["negative"]


def test_scam_spam_falls_below_integrity_gate():
    result = score_feed_integrity({
        "video_id": "crypto-spam",
        "title": "FREE MONEY CRYPTO GIVEAWAY TELEGRAM CRYPTO!!!!",
        "description": "Guaranteed profit. Double your money with my telegram crypto bot.",
        "channel_title": "Profit Hack Alerts",
        "tags": ["crypto", "crypto", "crypto", "giveaway", "profit"],
        "view_count": 90000,
        "thumbnail_url": "https://example.com/thumb.jpg",
        "duration_seconds": 42,
    })

    assert result["integrity_score"] < INTEGRITY_MIN_SCORE
    assert "clickbait_spam" in result["integrity_flags"]["negative"]
