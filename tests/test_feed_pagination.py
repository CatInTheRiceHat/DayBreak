"""Pagination / infinite-scroll contract for build_feed_payload.

The feed is paginated with ``exclude_ids``: each page is independently ranked
and balanced over the not-yet-seen pool, so pages never repeat a video and the
client can keep scrolling until the eligible pool is exhausted.
"""

from core.ranking.feed import build_feed_payload


def _row(video_id: str, *, category: str = "wellness", **overrides) -> dict:
    row = {
        "video_id": video_id,
        "title": f"Calm helpful guide {video_id}",
        "description": (
            "A gentle low-risk short with useful context, a kind reminder to "
            "stretch, breathe, journal, and notice one good thing today."
        ),
        "channel_title": f"Channel {video_id}",
        "source_category": category,
        "source_query": f"{category} seed",
        "source_type": "search",
        "duration_seconds": 72,
        "view_count": 12000,
        "tags": ["calm", "useful", "shorts"],
        "integrity_score": 0.78,
        "integrity_flags": {"negative": [], "positive": ["useful_context"]},
    }
    row.update(overrides)
    return row


def _eligible_rows(n: int) -> list[dict]:
    # Vary categories so content-mix balancing always has a healthy + regular mix.
    cats = ["wellness", "comedy", "music", "perspectives", "sports"]
    return [_row(f"vid-{i}", category=cats[i % len(cats)]) for i in range(n)]


def _page(rows, *, exclude_ids=None, k=12):
    return build_feed_payload(
        rows,
        "flutter-feed",
        k=k,
        shuffle_seed="page-test",
        exclude_ids=exclude_ids,
    )


def test_first_page_reports_pagination_metadata():
    rows = _eligible_rows(30)
    page = _page(rows, k=12)

    assert page["returned_count"] == len(page["items"]) == 12
    assert page["eligible_pool_count"] == 30
    assert page["has_more"] is True
    assert page["next_offset"] == 12


def test_pages_never_duplicate_and_cover_the_whole_pool():
    rows = _eligible_rows(30)
    seen: list[str] = []
    pages = 0
    has_more = True
    while has_more and pages < 20:
        page = _page(rows, exclude_ids=seen, k=12)
        ids = [item["youtube_id"] for item in page["items"]]
        # No id is ever repeated across pages.
        assert not (set(ids) & set(seen)), f"duplicate across pages: {set(ids) & set(seen)}"
        # No id repeats within a page.
        assert len(ids) == len(set(ids))
        seen.extend(ids)
        has_more = page["has_more"]
        pages += 1

    assert has_more is False
    assert len(seen) == 30
    assert len(set(seen)) == 30


def test_last_page_sets_has_more_false():
    rows = _eligible_rows(8)
    first = _page(rows, k=12)
    assert first["returned_count"] == 8
    assert first["has_more"] is False
    assert first["eligible_pool_count"] == 8


def test_empty_pool_is_graceful():
    page = _page([], k=12)
    assert page["items"] == []
    assert page["returned_count"] == 0
    assert page["eligible_pool_count"] == 0
    assert page["has_more"] is False


def test_blocked_and_non_english_never_counted_or_served():
    rows = _eligible_rows(10)
    rows.append(_row("blocked-1", status="blocked"))
    rows.append(_row("spanish-1", language="es"))
    rows.append(_row("region-1", region_code="JP"))

    seen: list[str] = []
    has_more = True
    while has_more:
        page = _page(rows, exclude_ids=seen, k=12)
        seen.extend(item["youtube_id"] for item in page["items"])
        has_more = page["has_more"]

    assert "blocked-1" not in seen
    assert "spanish-1" not in seen
    assert "region-1" not in seen
    # Only the 10 clean rows are eligible.
    assert set(seen) == {f"vid-{i}" for i in range(10)}


def test_default_call_is_unchanged_without_exclude_ids():
    # Back-compat: existing callers that omit exclude_ids/offset still work and
    # still get a balanced page of items.
    rows = _eligible_rows(20)
    page = build_feed_payload(rows, "flutter-feed", k=12, shuffle_seed="page-test")
    assert len(page["items"]) == 12
    assert page["has_more"] is True
