import pytest
from core.ranking.feed import build_feed_payload


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
