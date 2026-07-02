"""Tests for the trusted-channel ingestion lane (Parts E/F/G/H).

Mirrors the mostPopular "seed lane" tests: a fake YouTube transport drives the
lane through the SAME ``_candidate_from_video_item`` gate as every other lane, so
trusted sources raise quality without bypassing moderation.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from core.trust_registry import (
    TrustedChannel,
    block_channel_sqlite,
    ensure_trust_tables_sqlite,
    upsert_trusted_channel_sqlite,
)
from integrations.youtube_ingest import (
    MAX_TRUSTED_CHANNELS_PER_RUN,
    SourceQuerySpec,
    TRUSTED_CHANNEL_MIN_COUNT,
    TRUSTED_CHANNEL_TARGET_RATIO,
    fetch_trusted_channel_candidates,
    fetch_youtube_candidates,
    ingest_youtube_videos_sqlite,
    load_active_feed_video_rows_sqlite,
)

NOW = datetime(2026, 6, 14, 12, 0, tzinfo=timezone.utc)


def _video(video_id, title, channel_id, channel_title="Trusted Source", *,
           default_language="en", views="40000", likes="3000", comments="200"):
    return {
        "id": video_id,
        "snippet": {
            "title": title,
            "description": "A calm, prosocial explainer with study focus and wellbeing tips.",
            "channelId": channel_id,
            "channelTitle": channel_title,
            "categoryId": "27",
            "publishedAt": "2026-06-13T12:00:00Z",
            "tags": ["wellness", "calm", "explainer"],
            "defaultLanguage": default_language,
            "thumbnails": {"high": {"url": f"https://i.ytimg.com/vi/{video_id}/hq.jpg"}},
        },
        "contentDetails": {"duration": "PT1M10S"},
        "statistics": {"viewCount": views, "likeCount": likes, "commentCount": comments},
        "status": {"embeddable": True, "privacyStatus": "public", "uploadStatus": "processed"},
    }


def _make_fake(*, channel_videos=None, search_ids=(), popular_per_category=0):
    """Fake transport. channel_videos maps channelId -> list of _video() dicts.

    - search.list with channelId -> that channel's video ids (trusted lane)
    - search.list with q          -> search_ids (search lane)
    - videos.list chart           -> mostPopular videos
    - videos.list id              -> metadata for the requested ids
    """
    channel_videos = channel_videos or {}
    by_id = {v["id"]: v for vids in channel_videos.values() for v in vids}
    # search-lane metadata videos (generic channel)
    for sid in search_ids:
        by_id.setdefault(sid, _video(sid, "Calm study focus reset tips", f"search-ch-{sid}"))
    calls = {"search_channel": [], "search_query": [], "popular": [], "metadata": []}

    def fake(endpoint, params):
        if endpoint == "search" and params.get("channelId"):
            ch = params["channelId"]
            calls["search_channel"].append(ch)
            return {"items": [{"id": {"videoId": v["id"]}} for v in channel_videos.get(ch, [])]}
        if endpoint == "search":
            calls["search_query"].append(dict(params))
            return {"items": [{"id": {"videoId": s}} for s in search_ids]}
        if endpoint == "videos" and params.get("chart") == "mostPopular":
            calls["popular"].append(dict(params))
            cat = params["videoCategoryId"]
            return {"items": [
                _video(f"pop_{cat}_{n}", "Wholesome trending reset", f"pop-ch-{cat}",
                       views="9000000", likes="500000", comments="30000")
                for n in range(popular_per_category)
            ]}
        if endpoint == "videos":
            calls["metadata"].append(dict(params))
            ids = str(params["id"]).split(",")
            return {"items": [by_id[i] for i in ids if i in by_id]}
        raise AssertionError(f"unexpected endpoint {endpoint} {params}")

    return fake, calls


def _approved(channel_id, title, source_group="trusted/science"):
    return TrustedChannel(channel_id=channel_id, channel_title=title,
                          source_group=source_group, trust_tier="institutional",
                          status="approved")


# ── Part E: trusted-channel lane shape ───────────────────────────────────────

def test_trusted_candidates_have_trusted_source_fields():
    ch = _approved("UC_sci", "Quanta Science", "trusted/science")
    fake, _ = _make_fake(channel_videos={"UC_sci": [_video("v1", "How vaccines work", "UC_sci")]})
    candidates, _ = fetch_trusted_channel_candidates(
        request=fake, channels=[ch], now=NOW,
    )
    assert len(candidates) == 1
    c = candidates[0]
    assert c.source_type == "trusted_channel"
    assert c.source_category == "trusted/science"
    assert c.source_query == "trusted channel: Quanta Science"
    assert c.channel_id == "UC_sci"


# ── Part D: reputation attached as metadata (never a safety bypass) ──────────

def test_trusted_candidate_carries_source_reputation_metadata():
    ch = _approved("UC_inst", "Institutional Source", "trusted/education")
    fake, _ = _make_fake(channel_videos={"UC_inst": [
        _video("v", "A calm grounding reflection for focus", "UC_inst")]})
    candidates, _ = fetch_trusted_channel_candidates(request=fake, channels=[ch], now=NOW)
    flags = candidates[0].integrity_flags
    assert flags.get("source_reputation", 0) > 0.5      # approved + institutional
    assert flags.get("reputation_tier") in {"high", "medium"}
    assert flags.get("trust_tier") == "institutional"


# ── Part H #6/#7: trusted videos still pass the gate; foreign rejected ────────

def test_foreign_language_trusted_video_is_rejected():
    ch = _approved("UC_x", "Mixed Channel")
    fake, _ = _make_fake(channel_videos={"UC_x": [
        _video("good", "A calm grounding reflection for focus", "UC_x", default_language="en"),
        _video("hindi", "नमस्ते आज हम सीखेंगे ध्यान कैसे करें रोज़", "UC_x", default_language="hi"),
    ]})
    candidates, _ = fetch_trusted_channel_candidates(request=fake, channels=[ch], now=NOW)
    ids = {c.youtube_video_id for c in candidates}
    assert "good" in ids
    assert "hindi" not in ids  # trusted does not bypass the language filter


def test_unsafe_trusted_video_is_rejected_by_blocked_terms():
    ch = _approved("UC_x", "Mixed Channel")
    fake, _ = _make_fake(channel_videos={"UC_x": [
        _video("ok", "A calm grounding reflection for focus", "UC_x"),
        _video("bad", "Free robux gift card generator giveaway", "UC_x"),
    ]})
    candidates, _ = fetch_trusted_channel_candidates(request=fake, channels=[ch], now=NOW)
    ids = {c.youtube_video_id for c in candidates}
    assert ids == {"ok"}


# ── Part B: blocked channels never ingested (any lane) ───────────────────────

def test_blocked_channel_rejected_even_in_trusted_lane():
    ch = _approved("UC_block", "Compromised Source")
    fake, _ = _make_fake(channel_videos={"UC_block": [_video("v", "Calm focus tips", "UC_block")]})
    candidates, _ = fetch_trusted_channel_candidates(
        request=fake, channels=[ch], now=NOW, blocked_channel_ids={"UC_block"},
    )
    assert candidates == []


def test_blocked_channel_rejected_in_search_lane():
    # A normal search harvest whose videos belong to a blocked channel → none kept.
    fake, _ = _make_fake(search_ids=["s1", "s2"])
    # rewrite the two search videos to come from a blocked channel
    fake2, _ = _make_fake(channel_videos={}, search_ids=[])

    def transport(endpoint, params):
        if endpoint == "search" and not params.get("channelId"):
            return {"items": [{"id": {"videoId": "s1"}}, {"id": {"videoId": "s2"}}]}
        if endpoint == "videos" and params.get("chart") == "mostPopular":
            return {"items": []}
        if endpoint == "videos":
            ids = str(params["id"]).split(",")
            return {"items": [_video(i, "Calm focus tips", "UC_evil") for i in ids]}
        raise AssertionError(endpoint)

    candidates, _ = fetch_youtube_candidates(
        api_key="k", queries=[SourceQuerySpec("study/productivity", "focus")],
        request_json=transport, now=NOW, blocked_channel_ids={"UC_evil"},
    )
    assert candidates == []


# ── Part F: trusted share is capped ──────────────────────────────────────────

def test_trusted_share_is_capped():
    ch = _approved("UC_many", "Prolific Trusted")
    many = [_video(f"t{i}", f"Calm explainer number {i}", "UC_many") for i in range(10)]
    fake, _ = _make_fake(channel_videos={"UC_many": many},
                         search_ids=[f"s{i}" for i in range(12)])
    candidates, _ = fetch_youtube_candidates(
        api_key="k", queries=[SourceQuerySpec("study/productivity", "focus")],
        request_json=fake, now=NOW, include_trusted=True, trusted_channels=[ch],
    )
    n_total = len(candidates)
    n_trusted = sum(1 for c in candidates if c.source_type == "trusted_channel")
    assert n_trusted >= TRUSTED_CHANNEL_MIN_COUNT
    assert n_trusted < n_total                       # trusted never dominates
    assert n_trusted / n_total <= TRUSTED_CHANNEL_TARGET_RATIO + 0.08


# ── Quota guard: cap channels queried per run (Task 4) ───────────────────────

def test_max_trusted_channels_constant_is_small_and_safe():
    assert isinstance(MAX_TRUSTED_CHANNELS_PER_RUN, int)
    assert 1 <= MAX_TRUSTED_CHANNELS_PER_RUN <= 10


def test_trusted_lane_caps_channels_queried_per_run():
    chans = [_approved(f"UC_{i}", f"Chan {i}") for i in range(8)]
    cv = {f"UC_{i}": [_video(f"v{i}", "Calm focus explainer", f"UC_{i}")] for i in range(8)}
    fake, calls = _make_fake(channel_videos=cv)
    fetch_trusted_channel_candidates(request=fake, channels=chans, now=NOW, max_channels=3)
    # Each queried channel costs one search.list — cap limits API spend per run.
    assert len(calls["search_channel"]) == 3


def test_trusted_lane_uses_env_cap_when_no_explicit_limit(monkeypatch):
    monkeypatch.setenv("MAX_TRUSTED_CHANNELS_PER_RUN", "2")
    chans = [_approved(f"UC_{i}", f"Chan {i}") for i in range(5)]
    cv = {f"UC_{i}": [_video(f"v{i}", "Calm focus explainer", f"UC_{i}")] for i in range(5)}
    fake, calls = _make_fake(channel_videos=cv)
    fetch_trusted_channel_candidates(request=fake, channels=chans, now=NOW)
    assert len(calls["search_channel"]) == 2


def test_blocked_channels_do_not_consume_trusted_quota_budget():
    # Blocked channels are skipped BEFORE the search.list call, so they cost no
    # quota and do not eat into the per-run channel cap.
    chans = [_approved("UC_b1", "B1"), _approved("UC_b2", "B2")]
    chans += [_approved(f"UC_a{i}", f"A{i}") for i in range(3)]
    cv = {c.channel_id: [_video(f"v_{c.channel_id}", "Calm focus", c.channel_id)] for c in chans}
    fake, calls = _make_fake(channel_videos=cv)
    fetch_trusted_channel_candidates(
        request=fake, channels=chans, now=NOW, max_channels=3,
        blocked_channel_ids={"UC_b1", "UC_b2"},
    )
    assert set(calls["search_channel"]) == {"UC_a0", "UC_a1", "UC_a2"}


# ── Part G: empty registry / disabled trusted lane do not break ingestion ────

def test_empty_trusted_registry_does_not_break_ingestion():
    fake, _ = _make_fake(search_ids=["s1", "s2"], popular_per_category=2)
    candidates, _ = fetch_youtube_candidates(
        api_key="k", queries=[SourceQuerySpec("study/productivity", "focus")],
        request_json=fake, now=NOW, include_trusted=True, trusted_channels=[],
    )
    types = {c.source_type for c in candidates}
    assert "search" in types
    assert "trusted_channel" not in types


def test_existing_search_and_popular_lanes_unaffected_by_default():
    fake, _ = _make_fake(search_ids=["s1", "s2", "s3"], popular_per_category=2)
    candidates, _ = fetch_youtube_candidates(
        api_key="k", queries=[SourceQuerySpec("study/productivity", "focus")],
        request_json=fake, now=NOW,  # trusted not requested
    )
    types = {c.source_type for c in candidates}
    assert "search" in types and "most_popular" in types
    assert "trusted_channel" not in types


# ── Parts H #2/#3/#4: only approved channels reach the lane (DB integration) ──

def test_only_approved_channels_are_queried_and_ingested(tmp_path):
    db = tmp_path / "feed.db"
    seed = sqlite3.connect(db)
    ensure_trust_tables_sqlite(seed)
    upsert_trusted_channel_sqlite(seed, channel_id="UC_ok", channel_title="Approved Ed",
                                  source_group="trusted/education", trust_tier="institutional",
                                  status="approved", approved_by="elaine")
    upsert_trusted_channel_sqlite(seed, channel_id="UC_pending", channel_title="Pending",
                                  source_group="trusted/news", trust_tier="candidate",
                                  status="candidate")
    upsert_trusted_channel_sqlite(seed, channel_id="UC_no", channel_title="Rejected",
                                  source_group="trusted/news", trust_tier="experimental",
                                  status="rejected")
    seed.close()

    fake, calls = _make_fake(
        channel_videos={
            "UC_ok": [_video("okv", "Calm history explainer", "UC_ok")],
            "UC_pending": [_video("pv", "Pending video", "UC_pending")],
            "UC_no": [_video("nv", "Rejected video", "UC_no")],
        },
        search_ids=["s1", "s2"],
    )
    ingest_youtube_videos_sqlite(db_path=db, api_key="k",
                                 queries=[SourceQuerySpec("study/productivity", "focus")],
                                 request_json=fake, now=NOW)

    # Only the approved channel was ever queried by the trusted lane.
    assert calls["search_channel"] == ["UC_ok"]

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        rows = load_active_feed_video_rows_sqlite(conn)
    finally:
        conn.close()
    trusted_rows = [r for r in rows if r["source_type"] == "trusted_channel"]
    assert {r["video_id"] for r in trusted_rows} == {"okv"}
    assert all(r["video_id"] not in {"pv", "nv"} for r in rows)


def test_blocked_channel_never_ingested_end_to_end(tmp_path):
    db = tmp_path / "feed.db"
    seed = sqlite3.connect(db)
    ensure_trust_tables_sqlite(seed)
    upsert_trusted_channel_sqlite(seed, channel_id="UC_ok", channel_title="Approved Ed",
                                  source_group="trusted/education", trust_tier="institutional",
                                  status="approved")
    block_channel_sqlite(seed, channel_id="UC_ok", channel_title="Approved Ed",
                         reason="misinformation", blocked_by="elaine")
    seed.close()

    fake, _ = _make_fake(channel_videos={"UC_ok": [_video("v", "Calm explainer", "UC_ok")]},
                         search_ids=["s1"])
    ingest_youtube_videos_sqlite(db_path=db, api_key="k",
                                 queries=[SourceQuerySpec("study/productivity", "focus")],
                                 request_json=fake, now=NOW)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        rows = load_active_feed_video_rows_sqlite(conn)
    finally:
        conn.close()
    # The blocked channel's video must never be ingested even though it is approved.
    assert all(r["channel_id"] != "UC_ok" for r in rows)
    assert all(r["video_id"] != "v" for r in rows)
