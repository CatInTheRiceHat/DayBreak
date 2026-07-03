import pytest
from core.ranking.feed import build_feed_payload
from integrations.youtube_ingest import _active_feed_video_column_attempts


def _row(vid, orientation):
    return {
        "video_id": vid,
        "title": f"Title {vid}",
        "description": "A calm, supportive clip about student wellbeing and focus.",
        "orientation": orientation,
        "aspect_ratio": 0.5625 if orientation == "portrait" else 1.7777,
        "duration_seconds": 40,
        "thumbnail_url": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
        "embed_url": f"https://www.youtube-nocookie.com/embed/{vid}",
        "watch_url": f"https://www.youtube.com/watch?v={vid}",
    }


def test_payload_exposes_orientation():
    payload = build_feed_payload(
        [_row("aaa", "portrait"), _row("bbb", "landscape")],
        "flutter-feed",
        k=12,
    )
    by_id = {it["youtube_id"]: it for it in payload["items"]}
    assert by_id["aaa"]["orientation"] == "portrait"
    assert by_id["bbb"]["orientation"] == "landscape"
    assert by_id["bbb"]["aspect_ratio"] == pytest.approx(1.7777)


def test_orientation_fallback_keeps_popularity():
    """Deploy-before-ingest window: orientation columns are new to this branch
    while popularity columns already exist in production. The first fallback
    tier that drops orientation must still request popularity, or we silently
    zero out real Popular-lane data until the next ingest migration runs."""
    attempts = _active_feed_video_column_attempts()

    first_without_orientation = next(
        a for a in attempts if not a["include_orientation_metadata"]
    )
    assert first_without_orientation["include_popularity_metadata"] is True

    # And popularity must never be dropped in a tier that still keeps orientation
    # (orientation is the strictly newer column group).
    for a in attempts:
        if a["include_popularity_metadata"] is False:
            assert a["include_orientation_metadata"] is False
