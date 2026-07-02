"""
Daily YouTube feed ingestion for Chrysalis.

Uses the YouTube Data API only for metadata, stores embeddable short videos in a
shared feed_videos table, and exposes rows in the shape the existing Chrysalis
feed ranker expects. No videos are downloaded, proxied, converted, or rehosted.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Iterable, NamedTuple

from core.database import resolve_database_path
from core.feed_captions import (
    build_display_channel,
    build_display_hashtags,
    build_display_title,
    build_short_description,
)
from core.feed_integrity import score_feed_integrity
from core.labeling.explain import build_reasons
from core.labeling.metadata_scoring import parse_duration_seconds, score_metadata
from core.labeling.schema import SCORING_VERSION
from core.preferences import normalize_language_code, normalize_region_code
from core.language_filter import is_allowed as language_allowed
from core.ranking.modes import POPULAR_MIN_SCORE, popular_passes_min_score
from core.source_reputation import reputation_tier, source_reputation_score
from core.trust_registry import (
    TrustedChannel,
    load_approved_trusted_channels,
    load_approved_trusted_channels_postgres,
    load_blocked_channel_ids,
    load_blocked_channel_ids_postgres,
)

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = resolve_database_path()
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"

class SourceQuerySpec(NamedTuple):
    source_category: str
    source_query: str


# English-only / US-oriented demo queries (see core/language_filter.py).
#
# These are a SOFT first line of defense at the YouTube *search* stage:
# relevanceLanguage=en + regionCode=US are only hints, so broad queries like
# "street food", "music culture", or a bare "fashion" still surface a lot of
# foreign-language content that then has to be thrown away by the hard filter
# (wasting API quota and reducing yield). We bias the queries themselves toward
# US / English-speaking creators and semi-popular, wholesome formats.
#
# IMPORTANT: do NOT name a foreign language/culture in a query (e.g. "Korean
# street style", "Bollywood", "Hindi motivation"). language_filter.py blocks any
# source_query containing those names, so such a query would ingest *nothing*.
# Use US/English-context phrasing instead ("American outfit ideas", etc.).
#
# Balance is deliberate: only a few buckets are wellness/study — the rest stay
# general Gen-Z (news, food, comedy, gaming, fashion, sports, music, …) so the
# feed keeps its healthy/regular mix and never collapses into all-wellness.
DEFAULT_SOURCE_BUCKETS: tuple[SourceQuerySpec, ...] = (
    SourceQuerySpec("news/current events", "US news current events explained"),
    SourceQuerySpec("opinion/commentary", "thoughtful commentary video essay"),
    SourceQuerySpec("travel", "USA travel vlog city guide"),
    SourceQuerySpec("food", "easy home cooking recipes"),
    SourceQuerySpec("cute animals", "cute animals funny pets"),
    SourceQuerySpec("fashion/aesthetic", "American outfit ideas fashion lookbook"),
    SourceQuerySpec("gaming", "cozy gaming highlights commentary"),
    SourceQuerySpec("comedy", "clean comedy sketch standup"),
    SourceQuerySpec("internet culture", "internet culture memes explained"),
    SourceQuerySpec("AI/technology", "AI technology news explained"),
    SourceQuerySpec("pop culture", "US pop culture news explained"),
    SourceQuerySpec("sports", "US sports highlights athlete story"),
    SourceQuerySpec("wellness/mental health", "mental health wellness tips"),
    # Positive / self-care / emotional-wellness lanes. Kept to a SMALL number
    # (3) and all US/English-context so the feed surfaces more uplifting,
    # confidence/gratitude/kindness/resilience content without tipping the mix
    # into all-wellness — the broad Gen-Z buckets above/below stay intact and
    # the feed builder still caps the healthy ratio at 0.4–0.6.
    SourceQuerySpec("positivity/self care", "uplifting self care positive mindset tips"),
    SourceQuerySpec("emotional wellness", "emotional wellness healthy habits advice"),
    SourceQuerySpec("mindfulness/calm", "mindfulness calm reset tips"),
    SourceQuerySpec("study/productivity", "study with me productivity tips"),
    SourceQuerySpec("lifestyle/vlogs", "day in my life lifestyle vlog"),
    SourceQuerySpec("education/explainers", "science history explained"),
    SourceQuerySpec("music/culture", "new indie pop music review"),
)

DEFAULT_QUERIES: tuple[str, ...] = tuple(spec.source_query for spec in DEFAULT_SOURCE_BUCKETS)

RELEVANCE_TERMS: tuple[str, ...] = (
    "news", "current events", "explained", "commentary", "travel", "food",
    "recipe", "animals", "pets", "fashion", "aesthetic", "gaming", "comedy",
    "internet culture", "memes", "technology", "ai", "pop culture", "sports",
    "wellness", "mental health", "study", "productivity", "lifestyle", "vlog",
    "education", "science", "history", "music", "culture", "review",
    "guide", "tips", "story", "highlights",
    # Positive / self-care / emotional-wellness vocabulary. These nudge uplifting
    # content up in relevance; the keyword score is still clamped (hits / 8.0)
    # and weighted at ~0.46, so they bias without overpowering the ranking.
    "self care", "self-care", "positivity", "positive mindset", "uplifting",
    "encouragement", "confidence", "gratitude", "kindness", "resilience",
    "mindfulness", "calm", "healthy habits", "emotional wellness", "wholesome",
    "feel good", "reset", "reflection", "self improvement", "personal growth",
)

BLOCKED_TERMS: tuple[str, ...] = (
    # Hard blocks stay narrow: explicit/adult/gambling/scam/violent unsafe terms.
    "18+", "nsfw", "porn", "sex tape", "onlyfans", "nude",
    "casino", "gambling", "betting", "parlay",
    "free robux", "gift card generator", "telegram crypto",
    "graphic violence", "gore", "beheading", "execution video",
    "blackout challenge", "choking challenge", "train surfing",
    "hate speech", "white power", "extremist propaganda",
)

SHORT_TARGET_SECONDS = 180
MAX_ALLOWED_SECONDS = 240
MIN_RELEVANCE_SCORE = 0.18
_THUMBNAIL_PREFERENCE = ("maxres", "standard", "high", "medium", "default")

# --- Popular / trending "seed lane" -----------------------------------------
# A minority of candidates come from YouTube's mostPopular chart so the feed
# feels current and familiar. These still pass the SAME safety + relevance gate
# as search candidates (see _candidate_from_video_item); popularity only adds a
# small, capped ranking nudge — it never bypasses Chrysalis safety.
#
# mostPopular is queried per videoCategoryId. We reuse a small set of broadly
# wholesome categories (ids from the YouTube Data API category list). Music (10)
# and Gaming (20) are intentionally excluded here to avoid the feed tipping into
# high-virality music/gaming clips.
MOST_POPULAR_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("popular/entertainment", "24"),   # Entertainment
    ("popular/news", "25"),            # News & Politics
    ("popular/lifestyle", "26"),       # Howto & Style
    ("popular/education", "28"),       # Science & Technology
    ("popular/sports", "17"),          # Sports
)

# Share of the final candidate pool allowed to come from the popular lane. Keeps
# extraction from ever becoming 100% mostPopular (requirement: ~20–30%).
POPULAR_TARGET_RATIO = 0.25
# Always allow at least a couple of popular picks even on a small harvest.
POPULAR_MIN_COUNT = 2

# --- Trusted-channel lane ----------------------------------------------------
# A small, human-curated slice of the feed comes from approved trusted channels
# (see core/trust_registry.py). Trusted content raises source quality but must
# NOT take over the feed — it is capped just like the popular lane, and every
# trusted video still passes the SAME _candidate_from_video_item gate (public,
# embeddable, duration, blocked terms, language filter, relevance, integrity).
TRUSTED_CHANNEL_TARGET_RATIO = 0.15
TRUSTED_CHANNEL_MIN_COUNT = 1

# Quota guard. The trusted lane spends ONE search.list (≈100 YouTube quota units)
# per approved channel PER RUN — independent of the feed-mix cap above. With 4×/day
# extraction, N approved channels cost ≈ N × 100 × 4 units/day on top of the search
# and popular lanes. So we cap how many approved channels are queried per run and
# make it overridable via the MAX_TRUSTED_CHANNELS_PER_RUN env var.
#
#   * Start small: 3–5 approved channels.
#   * Do NOT approve dozens at once — watch your YouTube Data API quota for a day
#     after the first run before scaling up.
#
# Policy: video EXTRACTION (the search lanes) takes priority over the trusted-
# creator list for the constrained daily quota. We deliberately keep this cap low
# so the creator lane spends ≤ 2 × 100 units/run, leaving headroom for extraction
# rather than pushing the day toward the 10k-unit ceiling. Raising it trades
# directly against extraction quota — see _resolve_max_trusted_channels override.
MAX_TRUSTED_CHANNELS_PER_RUN = 2


def _resolve_max_trusted_channels(explicit: int | None = None) -> int:
    """Per-run trusted-channel cap: explicit arg > env var > module default."""
    if explicit is not None:
        return max(0, int(explicit))
    raw = os.environ.get("MAX_TRUSTED_CHANNELS_PER_RUN")
    if raw is not None and str(raw).strip():
        try:
            return max(0, int(str(raw).strip()))
        except ValueError:
            pass
    return MAX_TRUSTED_CHANNELS_PER_RUN

RequestJson = Callable[[str, dict], dict | None]


class YouTubeIngestError(RuntimeError):
    """Raised when ingestion cannot be configured or executed."""


@dataclass
class FeedVideoCandidate:
    id: str
    source: str
    youtube_video_id: str
    title: str
    channel_title: str
    channel_id: str
    description: str
    short_description: str
    display_title: str
    display_channel: str
    display_hashtags: list[str]
    thumbnail_url: str
    embed_url: str
    watch_url: str
    published_at: str
    duration_seconds: int | None
    view_count: int
    tags: list[str]
    category_id: str
    topic: str
    source_category: str
    source_query: str
    integrity_score: float
    integrity_flags: dict
    production_style: str
    creator_scale: str
    score: float
    status: str
    created_at: str
    updated_at: str
    chrysalis_scores: dict
    ranking_reason: str
    safety_reason: str
    concern_reason: str | None
    label_confidence: float
    scored_at: str
    scoring_version: str
    # Provenance of this candidate: "search" (Chrysalis topic/search queries) or
    # "most_popular" (YouTube mostPopular trending lane). Defaulted so older call
    # sites and deserializers keep working.
    source_type: str = "search"
    # Capped 0–1 popularity signal (views/likes/comments/freshness) computed at
    # ingest, where like/comment counts are available. Used for a small capped
    # ranking boost so the feed feels current without becoming pure virality.
    popularity_score: float = 0.0


@dataclass
class IngestResult:
    ok: bool
    added: int
    updated: int
    skipped: int
    fetched: int
    queries: list[str]
    days_back: int
    max_results_per_query: int
    source_type_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


_CREATE_FEED_VIDEOS_SQLITE = """
CREATE TABLE IF NOT EXISTS feed_videos (
    id                  TEXT PRIMARY KEY,
    source              TEXT NOT NULL DEFAULT 'youtube',
    youtube_video_id    TEXT NOT NULL UNIQUE,
    title               TEXT,
    channel_title       TEXT,
    channel_id          TEXT,
    description         TEXT,
    short_description   TEXT,
    display_title       TEXT,
    display_channel     TEXT,
    display_hashtags    TEXT,
    thumbnail_url       TEXT,
    embed_url           TEXT,
    watch_url           TEXT,
    published_at        TEXT,
    duration_seconds    INTEGER,
    view_count          INTEGER,
    tags                TEXT,
    category_id         TEXT,
    topic               TEXT,
    source_category     TEXT,
    source_query        TEXT,
    source_type         TEXT DEFAULT 'search',
    popularity_score    REAL DEFAULT 0,
    integrity_score     REAL,
    integrity_flags     TEXT,
    production_style    TEXT,
    creator_scale       TEXT,
    score               REAL,
    created_at          TEXT,
    updated_at          TEXT,
    status              TEXT NOT NULL DEFAULT 'active',
    chrysalis_scores    TEXT,
    ranking_reason      TEXT,
    safety_reason       TEXT,
    concern_reason      TEXT,
    label_confidence    REAL,
    scored_at           TEXT,
    scoring_version     TEXT
)
"""

_CREATE_FEED_VIDEOS_POSTGRES = """
CREATE TABLE IF NOT EXISTS feed_videos (
    id                  TEXT PRIMARY KEY,
    source              TEXT NOT NULL DEFAULT 'youtube',
    youtube_video_id    TEXT NOT NULL UNIQUE,
    title               TEXT,
    channel_title       TEXT,
    channel_id          TEXT,
    description         TEXT,
    short_description   TEXT,
    display_title       TEXT,
    display_channel     TEXT,
    display_hashtags    JSONB,
    thumbnail_url       TEXT,
    embed_url           TEXT,
    watch_url           TEXT,
    published_at        TEXT,
    duration_seconds    INTEGER,
    view_count          BIGINT,
    tags                JSONB,
    category_id         TEXT,
    topic               TEXT,
    source_category     TEXT,
    source_query        TEXT,
    source_type         TEXT DEFAULT 'search',
    popularity_score    REAL DEFAULT 0,
    integrity_score     REAL,
    integrity_flags     JSONB,
    production_style    TEXT,
    creator_scale       TEXT,
    score               REAL,
    created_at          TIMESTAMPTZ,
    updated_at          TIMESTAMPTZ,
    status              TEXT NOT NULL DEFAULT 'active',
    chrysalis_scores    JSONB,
    ranking_reason      TEXT,
    safety_reason       TEXT,
    concern_reason      TEXT,
    label_confidence    REAL,
    scored_at           TIMESTAMPTZ,
    scoring_version     TEXT
)
"""


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()


def configured_queries(value: str | None = None) -> list[str]:
    return [spec.source_query for spec in configured_source_queries(value)]


def configured_source_queries(value: str | None = None) -> list[SourceQuerySpec]:
    raw = value if value is not None else os.environ.get("YOUTUBE_FEED_QUERIES", "")
    if not raw.strip():
        return list(DEFAULT_SOURCE_BUCKETS)
    return [_parse_source_query_spec(q) for q in raw.split(",") if q.strip()]


def _parse_source_query_spec(raw: str) -> SourceQuerySpec:
    value = raw.strip()
    for separator in ("::", "|", "="):
        if separator in value:
            category, _, query = value.partition(separator)
            category = category.strip() or "custom"
            query = query.strip() or category
            return SourceQuerySpec(category, query)
    return SourceQuerySpec("custom", value)


def _coerce_source_query_specs(queries: Iterable[str | SourceQuerySpec] | None) -> list[SourceQuerySpec]:
    if queries is None:
        return configured_source_queries()
    specs: list[SourceQuerySpec] = []
    for item in queries:
        if isinstance(item, SourceQuerySpec):
            specs.append(item)
        elif isinstance(item, tuple) and len(item) == 2:
            specs.append(SourceQuerySpec(str(item[0]).strip() or "custom", str(item[1]).strip()))
        else:
            specs.append(_parse_source_query_spec(str(item)))
    return [spec for spec in specs if spec.source_query]


def ensure_sqlite_feed_videos_table(conn: sqlite3.Connection) -> None:
    conn.execute(_CREATE_FEED_VIDEOS_SQLITE)
    _ensure_sqlite_feed_video_columns(conn)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_feed_videos_status_score "
        "ON feed_videos (status, score DESC, published_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_feed_videos_youtube_id "
        "ON feed_videos (youtube_video_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_feed_videos_source_category "
        "ON feed_videos (source_category)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_feed_videos_source_query "
        "ON feed_videos (source_query)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_feed_videos_integrity_score "
        "ON feed_videos (integrity_score)"
    )
    conn.commit()


def _ensure_sqlite_feed_video_columns(conn: sqlite3.Connection) -> None:
    existing = {
        row[1]
        for row in conn.execute("PRAGMA table_info(feed_videos)").fetchall()
    }
    for column, column_type in {
        "source_category": "TEXT",
        "source_query": "TEXT",
        "source_type": "TEXT DEFAULT 'search'",
        "popularity_score": "REAL DEFAULT 0",
        "short_description": "TEXT",
        "display_title": "TEXT",
        "display_channel": "TEXT",
        "display_hashtags": "TEXT",
        "integrity_score": "REAL",
        "integrity_flags": "TEXT",
        "production_style": "TEXT",
        "creator_scale": "TEXT",
    }.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE feed_videos ADD COLUMN {column} {column_type}")


def ensure_postgres_feed_videos_table(conn) -> None:
    cur = conn.cursor()
    cur.execute(_CREATE_FEED_VIDEOS_POSTGRES)
    cur.execute("ALTER TABLE feed_videos ADD COLUMN IF NOT EXISTS source_category TEXT")
    cur.execute("ALTER TABLE feed_videos ADD COLUMN IF NOT EXISTS source_query TEXT")
    cur.execute("ALTER TABLE feed_videos ADD COLUMN IF NOT EXISTS source_type TEXT DEFAULT 'search'")
    cur.execute("ALTER TABLE feed_videos ADD COLUMN IF NOT EXISTS popularity_score REAL DEFAULT 0")
    cur.execute("ALTER TABLE feed_videos ADD COLUMN IF NOT EXISTS short_description TEXT")
    cur.execute("ALTER TABLE feed_videos ADD COLUMN IF NOT EXISTS display_title TEXT")
    cur.execute("ALTER TABLE feed_videos ADD COLUMN IF NOT EXISTS display_channel TEXT")
    cur.execute("ALTER TABLE feed_videos ADD COLUMN IF NOT EXISTS display_hashtags JSONB")
    cur.execute("ALTER TABLE feed_videos ADD COLUMN IF NOT EXISTS integrity_score REAL")
    cur.execute("ALTER TABLE feed_videos ADD COLUMN IF NOT EXISTS integrity_flags JSONB")
    cur.execute("ALTER TABLE feed_videos ADD COLUMN IF NOT EXISTS production_style TEXT")
    cur.execute("ALTER TABLE feed_videos ADD COLUMN IF NOT EXISTS creator_scale TEXT")
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_feed_videos_status_score "
        "ON feed_videos (status, score DESC, published_at DESC)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_feed_videos_youtube_id "
        "ON feed_videos (youtube_video_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_feed_videos_source_category "
        "ON feed_videos (source_category)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_feed_videos_source_query "
        "ON feed_videos (source_query)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_feed_videos_integrity_score "
        "ON feed_videos (integrity_score)"
    )
    conn.commit()


def ingest_youtube_videos_sqlite(
    *,
    db_path: str | os.PathLike | None = None,
    api_key: str | None = None,
    queries: Iterable[str | SourceQuerySpec] | None = None,
    max_results_per_query: int = 10,
    days_back: int = 7,
    relevance_language: str = "en",
    region_code: str = "US",
    request_json: RequestJson | None = None,
    now: datetime | None = None,
    include_popular: bool = True,
    popular_ratio: float = POPULAR_TARGET_RATIO,
    include_trusted: bool = True,
    trusted_ratio: float = TRUSTED_CHANNEL_TARGET_RATIO,
) -> IngestResult:
    source_specs = _coerce_source_query_specs(queries)
    query_list = [spec.source_query for spec in source_specs]
    db_file = resolve_database_path(db_path)
    # Load the human-curated trust registry from the SAME db. Missing/empty tables
    # → no trusted channels and no blocklist, so the feed runs on search + popular
    # exactly as before (Part G — backward compatibility).
    reg_conn = sqlite3.connect(db_file)
    reg_conn.row_factory = sqlite3.Row
    try:
        trusted_channels = load_approved_trusted_channels(reg_conn) if include_trusted else []
        blocked_ids = load_blocked_channel_ids(reg_conn)
    finally:
        reg_conn.close()
    candidates, skipped = fetch_youtube_candidates(
        api_key=api_key,
        queries=source_specs,
        max_results_per_query=max_results_per_query,
        days_back=days_back,
        relevance_language=relevance_language,
        region_code=region_code,
        request_json=request_json,
        now=now,
        include_popular=include_popular,
        popular_ratio=popular_ratio,
        include_trusted=include_trusted,
        trusted_channels=trusted_channels,
        trusted_ratio=trusted_ratio,
        blocked_channel_ids=blocked_ids,
    )
    conn = sqlite3.connect(db_file)
    try:
        added, updated = store_candidates_sqlite(conn, candidates)
    finally:
        conn.close()
    counts: dict[str, int] = {}
    for c in candidates:
        counts[c.source_type] = counts.get(c.source_type, 0) + 1
    return IngestResult(
        ok=True,
        added=added,
        updated=updated,
        skipped=skipped,
        fetched=len(candidates),
        queries=query_list,
        days_back=days_back,
        max_results_per_query=max_results_per_query,
        source_type_counts=counts,
    )


def ingest_youtube_videos_postgres(
    conn,
    *,
    api_key: str | None = None,
    queries: Iterable[str | SourceQuerySpec] | None = None,
    max_results_per_query: int = 10,
    days_back: int = 7,
    relevance_language: str = "en",
    region_code: str = "US",
    request_json: RequestJson | None = None,
    now: datetime | None = None,
    include_popular: bool = True,
    popular_ratio: float = POPULAR_TARGET_RATIO,
    include_trusted: bool = True,
    trusted_ratio: float = TRUSTED_CHANNEL_TARGET_RATIO,
) -> IngestResult:
    source_specs = _coerce_source_query_specs(queries)
    query_list = [spec.source_query for spec in source_specs]
    # Load the human-curated trust registry from Postgres. Missing tables (before
    # migration 011 is applied) → empty registry, so ingestion runs on search +
    # popular exactly as before (Part G — backward compatibility).
    trusted_channels = load_approved_trusted_channels_postgres(conn) if include_trusted else []
    blocked_ids = load_blocked_channel_ids_postgres(conn)
    candidates, skipped = fetch_youtube_candidates(
        api_key=api_key,
        queries=source_specs,
        max_results_per_query=max_results_per_query,
        days_back=days_back,
        relevance_language=relevance_language,
        region_code=region_code,
        request_json=request_json,
        now=now,
        include_popular=include_popular,
        popular_ratio=popular_ratio,
        include_trusted=include_trusted,
        trusted_channels=trusted_channels,
        trusted_ratio=trusted_ratio,
        blocked_channel_ids=blocked_ids,
    )
    added, updated = store_candidates_postgres(conn, candidates)
    counts: dict[str, int] = {}
    for c in candidates:
        counts[c.source_type] = counts.get(c.source_type, 0) + 1
    return IngestResult(
        ok=True,
        added=added,
        updated=updated,
        skipped=skipped,
        fetched=len(candidates),
        queries=query_list,
        days_back=days_back,
        max_results_per_query=max_results_per_query,
        source_type_counts=counts,
    )


def fetch_youtube_candidates(
    *,
    api_key: str | None = None,
    queries: Iterable[str | SourceQuerySpec] | None = None,
    max_results_per_query: int = 10,
    days_back: int = 7,
    relevance_language: str = "en",
    region_code: str = "US",
    request_json: RequestJson | None = None,
    now: datetime | None = None,
    include_popular: bool = True,
    popular_ratio: float = POPULAR_TARGET_RATIO,
    include_trusted: bool = False,
    trusted_channels: Iterable[TrustedChannel] | None = None,
    trusted_ratio: float = TRUSTED_CHANNEL_TARGET_RATIO,
    max_trusted_channels: int | None = None,
    blocked_channel_ids: set[str] | None = None,
) -> tuple[list[FeedVideoCandidate], int]:
    api_key = api_key or os.environ.get("YOUTUBE_API_KEY", "")
    if not api_key and request_json is None:
        raise YouTubeIngestError("YOUTUBE_API_KEY is required for YouTube ingestion.")
    blocked_ids = set(blocked_channel_ids or ())

    max_results_per_query = max(1, min(int(max_results_per_query), 25))
    days_back = max(2, min(int(days_back), 7))
    relevance_language = normalize_language_code(relevance_language)
    region_code = normalize_region_code(region_code)
    source_specs = _coerce_source_query_specs(queries)
    now_utc = now or datetime.now(timezone.utc)
    published_after = (now_utc - timedelta(days=days_back)).replace(microsecond=0)
    published_after_str = published_after.isoformat().replace("+00:00", "Z")
    request = request_json or _youtube_request_json(api_key)

    seen: set[str] = set()
    search_hits: list[tuple[str, SourceQuerySpec]] = []
    skipped = 0

    for source_spec in source_specs:
        data = request("search", {
            "part": "snippet",
            "type": "video",
            "maxResults": str(max_results_per_query),
            "order": "date",
            "publishedAfter": published_after_str,
            "videoDuration": "short",
            "videoEmbeddable": "true",
            "safeSearch": "strict",
            "relevanceLanguage": relevance_language,
            "regionCode": region_code,
            "q": source_spec.source_query,
        }) or {}
        for item in data.get("items", []):
            video_id = ((item.get("id") or {}).get("videoId") or "").strip()
            if not video_id or video_id in seen:
                skipped += 1
                continue
            seen.add(video_id)
            search_hits.append((video_id, source_spec))

    candidates: list[FeedVideoCandidate] = []
    source_spec_by_id = {video_id: source_spec for video_id, source_spec in search_hits}

    for batch in _chunks([video_id for video_id, _ in search_hits], 50):
        data = request("videos", {
            "part": "snippet,contentDetails,statistics,status",
            "id": ",".join(batch),
            "hl": relevance_language,
            "regionCode": region_code,
        }) or {}
        for item in data.get("items", []):
            candidate = _candidate_from_video_item(
                item,
                source_spec=source_spec_by_id.get(
                    str(item.get("id")),
                    SourceQuerySpec("custom", ""),
                ),
                now=now_utc,
                days_back=days_back,
                source_type="search",
                blocked_channel_ids=blocked_ids,
            )
            if candidate is None:
                skipped += 1
                continue
            candidates.append(candidate)

    # Popular "seed lane": add a minority of mostPopular/trending videos so the
    # feed feels current, mixed in (never replacing) the search candidates.
    popular_candidates: list[FeedVideoCandidate] = []
    if include_popular:
        popular_candidates, popular_skipped = fetch_most_popular_candidates(
            request=request,
            relevance_language=relevance_language,
            region_code=region_code,
            max_results=max_results_per_query,
            now=now_utc,
            days_back=days_back,
            exclude_ids=seen,
            blocked_channel_ids=blocked_ids,
        )
        skipped += popular_skipped

    mixed = _mix_search_and_popular(
        candidates, popular_candidates, popular_ratio=popular_ratio
    )

    # Trusted-channel lane: a small, human-approved slice mixed in (and capped) on
    # top of the search + popular pool. Empty/absent channels → no-op (Part G).
    if include_trusted and trusted_channels:
        trusted_candidates, trusted_skipped = fetch_trusted_channel_candidates(
            request=request,
            channels=trusted_channels,
            relevance_language=relevance_language,
            region_code=region_code,
            max_results=max_results_per_query,
            now=now_utc,
            days_back=days_back,
            exclude_ids=seen,
            blocked_channel_ids=blocked_ids,
            max_channels=max_trusted_channels,
        )
        skipped += trusted_skipped
        mixed = _mix_trusted_candidates(mixed, trusted_candidates, trusted_ratio=trusted_ratio)

    return mixed, skipped


def fetch_most_popular_candidates(
    *,
    request: RequestJson,
    relevance_language: str = "en",
    region_code: str = "US",
    max_results: int = 10,
    now: datetime | None = None,
    days_back: int = 7,
    exclude_ids: set[str] | None = None,
    categories: Iterable[tuple[str, str]] | None = None,
    blocked_channel_ids: set[str] | None = None,
) -> tuple[list[FeedVideoCandidate], int]:
    """Fetch YouTube mostPopular (trending) videos as additional candidates.

    Uses videos.list with ``chart=mostPopular`` + ``hl`` + ``regionCode`` +
    ``videoCategoryId`` — NOT search.list / ``relevanceLanguage`` (mostPopular is
    a chart endpoint and does not accept relevanceLanguage). Every returned video
    is run through the exact same safety/relevance gate as search candidates via
    ``_candidate_from_video_item``; popularity never bypasses Chrysalis safety.
    """
    now_utc = now or datetime.now(timezone.utc)
    relevance_language = normalize_language_code(relevance_language)
    region_code = normalize_region_code(region_code)
    max_results = max(1, min(int(max_results), 25))
    cats = list(categories) if categories is not None else list(MOST_POPULAR_CATEGORIES)

    candidates: list[FeedVideoCandidate] = []
    skipped = 0
    seen: set[str] = set(exclude_ids or ())
    for source_label, category_id in cats:
        data = request("videos", {
            "part": "snippet,contentDetails,statistics,status",
            "chart": "mostPopular",
            "regionCode": region_code,
            "hl": relevance_language,
            "videoCategoryId": category_id,
            "maxResults": str(max_results),
        }) or {}
        for item in data.get("items", []):
            video_id = str(item.get("id") or "").strip()
            if not video_id or video_id in seen:
                skipped += 1
                continue
            seen.add(video_id)
            candidate = _candidate_from_video_item(
                item,
                source_spec=SourceQuerySpec(source_label, "trending"),
                now=now_utc,
                days_back=days_back,
                source_type="most_popular",
                blocked_channel_ids=set(blocked_channel_ids or ()),
            )
            if candidate is None:
                skipped += 1
                continue
            candidates.append(candidate)
    return candidates, skipped


def fetch_trusted_channel_candidates(
    *,
    request: RequestJson,
    channels: Iterable[TrustedChannel] | None,
    relevance_language: str = "en",
    region_code: str = "US",
    max_results: int = 10,
    now: datetime | None = None,
    days_back: int = 7,
    exclude_ids: set[str] | None = None,
    blocked_channel_ids: set[str] | None = None,
    max_channels: int | None = None,
) -> tuple[list[FeedVideoCandidate], int]:
    """Fetch recent videos from approved trusted channels (Part E).

    For each approved channel: search.list by ``channelId`` (ordered by date) →
    videos.list for metadata → the SAME ``_candidate_from_video_item`` gate as
    every other lane. Trusted videos are tagged ``source_type="trusted_channel"``,
    ``source_category=<source_group>``, ``source_query="trusted channel: <title>"``.
    Trust raises quality; it never bypasses safety, language, or relevance checks.
    """
    now_utc = now or datetime.now(timezone.utc)
    relevance_language = normalize_language_code(relevance_language)
    region_code = normalize_region_code(region_code)
    max_results = max(1, min(int(max_results), 25))
    days_back = max(2, min(int(days_back), 7))
    published_after = (now_utc - timedelta(days=days_back)).replace(microsecond=0)
    published_after_str = published_after.isoformat().replace("+00:00", "Z")
    blocked = set(blocked_channel_ids or ())

    candidates: list[FeedVideoCandidate] = []
    skipped = 0
    seen: set[str] = set(exclude_ids or ())

    # Quota guard: cap how many channels we actually query (each costs a search.list).
    cap = _resolve_max_trusted_channels(max_channels)
    queried = 0

    for channel in channels or ():
        channel_id = str(getattr(channel, "channel_id", "") or "").strip()
        # Never query a blocked channel, even if it is also marked approved.
        # (Skipped before the search.list call, so blocked channels cost no quota
        # and do not consume the per-run cap.)
        if not channel_id or channel_id in blocked:
            continue
        if queried >= cap:
            break  # per-run quota cap reached
        queried += 1
        source_group = getattr(channel, "source_group", "") or "trusted/culture"
        channel_title = getattr(channel, "channel_title", "") or channel_id
        source_spec = SourceQuerySpec(source_group, f"trusted channel: {channel_title}")

        data = request("search", {
            "part": "snippet",
            "type": "video",
            "channelId": channel_id,
            "order": "date",
            "maxResults": str(max_results),
            "publishedAfter": published_after_str,
            "videoDuration": "short",
            "videoEmbeddable": "true",
            "safeSearch": "strict",
            "relevanceLanguage": relevance_language,
            "regionCode": region_code,
        }) or {}
        hit_ids: list[str] = []
        for item in data.get("items", []):
            vid = ((item.get("id") or {}).get("videoId") or "").strip()
            if not vid or vid in seen:
                skipped += 1
                continue
            seen.add(vid)
            hit_ids.append(vid)

        for batch in _chunks(hit_ids, 50):
            meta = request("videos", {
                "part": "snippet,contentDetails,statistics,status",
                "id": ",".join(batch),
                "hl": relevance_language,
                "regionCode": region_code,
            }) or {}
            for item in meta.get("items", []):
                candidate = _candidate_from_video_item(
                    item,
                    source_spec=source_spec,
                    now=now_utc,
                    days_back=days_back,
                    source_type="trusted_channel",
                    blocked_channel_ids=blocked,
                )
                if candidate is None:
                    skipped += 1
                    continue
                # Attach source reputation as METADATA only (Part D). The video has
                # already passed the full safety/relevance gate above — reputation
                # never bypasses any of it; it is an explainability/ranking signal.
                rep = source_reputation_score(
                    status=getattr(channel, "status", None),
                    trust_tier=getattr(channel, "trust_tier", None),
                    source_group_match=True,
                    english_us=True,            # it passed the en/US filter to get here
                    recent_activity=True,
                    integrity_history=candidate.integrity_score,
                )
                candidate.integrity_flags = {
                    **(candidate.integrity_flags or {}),
                    "source_reputation": round(rep, 3),
                    "reputation_tier": reputation_tier(rep),
                    "trust_tier": getattr(channel, "trust_tier", None),
                    "trusted_source_group": source_group,
                }
                candidates.append(candidate)
    return candidates, skipped


def _mix_trusted_candidates(
    base: list[FeedVideoCandidate],
    trusted: list[FeedVideoCandidate],
    *,
    trusted_ratio: float = TRUSTED_CHANNEL_TARGET_RATIO,
    min_count: int = TRUSTED_CHANNEL_MIN_COUNT,
) -> list[FeedVideoCandidate]:
    """Mix trusted-channel candidates into the pool, capping their share (Part F).

    Trusted content improves quality but must not dominate — it is capped to
    ``trusted_ratio`` of the combined pool (with a small minimum), mirroring the
    popular lane. The strongest trusted candidates (by relevance) are kept.
    """
    seen_ids = {c.youtube_video_id for c in base}
    unique: list[FeedVideoCandidate] = []
    for cand in trusted:
        if cand.youtube_video_id in seen_ids:
            continue
        seen_ids.add(cand.youtube_video_id)
        unique.append(cand)
    if not unique:
        return list(base)

    ratio = min(max(float(trusted_ratio), 0.0), 0.9)
    n_base = len(base)
    if n_base == 0:
        cap = len(unique)
    else:
        cap = int(round((ratio / (1.0 - ratio)) * n_base))
        cap = max(cap, min_count)
    cap = min(cap, len(unique))

    unique.sort(key=lambda c: c.score, reverse=True)
    return list(base) + unique[:cap]


def _mix_search_and_popular(
    search: list[FeedVideoCandidate],
    popular: list[FeedVideoCandidate],
    *,
    popular_ratio: float = POPULAR_TARGET_RATIO,
) -> list[FeedVideoCandidate]:
    """Combine search + popular candidates, capping the popular share.

    The popular lane is capped to ``popular_ratio`` of the final pool (with a
    small minimum) so extraction can never become 100% mostPopular. The strongest
    popular candidates (by capped popularity, then relevance) are kept.
    """
    seen_ids = {c.youtube_video_id for c in search}
    unique_popular: list[FeedVideoCandidate] = []
    for cand in popular:
        if cand.youtube_video_id in seen_ids:
            continue
        # Drop weak trending picks before they ever reach feed_videos. Only the
        # popular lane is gated; search candidates are never filtered here.
        if not popular_passes_min_score(cand.source_type, cand.popularity_score):
            continue
        seen_ids.add(cand.youtube_video_id)
        unique_popular.append(cand)

    if not unique_popular:
        return list(search)

    ratio = min(max(float(popular_ratio), 0.0), 0.9)
    n_search = len(search)
    if n_search == 0:
        cap = len(unique_popular)  # nothing to mix against — keep what we have
    else:
        cap = int(round((ratio / (1.0 - ratio)) * n_search))
        cap = max(cap, POPULAR_MIN_COUNT)
    cap = min(cap, len(unique_popular))

    unique_popular.sort(key=lambda c: (c.popularity_score, c.score), reverse=True)
    return list(search) + unique_popular[:cap]


def store_candidates_sqlite(
    conn: sqlite3.Connection,
    candidates: Iterable[FeedVideoCandidate],
) -> tuple[int, int]:
    ensure_sqlite_feed_videos_table(conn)
    added = 0
    updated = 0
    for candidate in candidates:
        exists = conn.execute(
            "SELECT 1 FROM feed_videos WHERE youtube_video_id = ?",
            (candidate.youtube_video_id,),
        ).fetchone()
        _upsert_sqlite_candidate(conn, candidate)
        if exists:
            updated += 1
        else:
            added += 1
    conn.commit()
    return added, updated


def store_candidates_postgres(conn, candidates: Iterable[FeedVideoCandidate]) -> tuple[int, int]:
    ensure_postgres_feed_videos_table(conn)
    cur = conn.cursor()
    added = 0
    updated = 0
    for candidate in candidates:
        cur.execute(
            "SELECT 1 FROM feed_videos WHERE youtube_video_id = %s",
            (candidate.youtube_video_id,),
        )
        exists = cur.fetchone() is not None
        _upsert_postgres_candidate(cur, candidate)
        if exists:
            updated += 1
        else:
            added += 1
    conn.commit()
    return added, updated


def deactivate_weak_popular_rows_sqlite(
    conn: sqlite3.Connection,
    *,
    min_score: float = POPULAR_MIN_SCORE,
) -> int:
    """One-time admin cleanup: mark already-stored weak popular rows inactive.

    The feed-load path already filters these out at read time, so this is purely
    optional housekeeping. There is no boolean ``is_active`` column in this
    schema — rows are gated by ``status``, so we flip ``status`` away from
    ``'active'`` (the value the feed query requires). SQL-safe / parameterized
    and scoped strictly to ``most_popular`` rows below ``min_score``.
    """
    cur = conn.execute(
        """
        UPDATE feed_videos
           SET status = 'inactive'
         WHERE source_type = 'most_popular'
           AND COALESCE(popularity_score, 0) < ?
           AND status = 'active'
        """,
        (min_score,),
    )
    conn.commit()
    return cur.rowcount or 0


def deactivate_weak_popular_rows_postgres(
    conn,
    *,
    min_score: float = POPULAR_MIN_SCORE,
) -> int:
    """Postgres counterpart of :func:`deactivate_weak_popular_rows_sqlite`."""
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE feed_videos
           SET status = 'inactive'
         WHERE source_type = 'most_popular'
           AND COALESCE(popularity_score, 0) < %s
           AND status = 'active'
        """,
        (min_score,),
    )
    conn.commit()
    return cur.rowcount or 0


def load_active_feed_video_rows_sqlite(
    conn: sqlite3.Connection,
    *,
    limit: int | None = None,
) -> list[dict]:
    params: tuple = (int(limit),) if limit is not None else ()
    for options in _active_feed_video_column_attempts():
        sql = _active_feed_video_rows_sql(**options)
        if limit is not None:
            sql += " LIMIT ?"
        try:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        except sqlite3.OperationalError as exc:
            message = str(exc).lower()
            if "no such table" in message:
                return []
            if _missing_optional_feed_video_column(message):
                continue
            raise
    return []


def load_active_feed_video_rows_postgres(conn, *, limit: int | None = None) -> list[dict]:
    params: tuple = ()
    if limit is not None:
        params = (int(limit),)
    cur = conn.cursor()
    for options in _active_feed_video_column_attempts():
        sql = _active_feed_video_rows_sql(**options)
        if limit is not None:
            sql += " LIMIT %s"
        try:
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
        except Exception as exc:
            message = str(exc).lower()
            conn.rollback()
            if "feed_videos" in message and "does not exist" in message:
                return []
            if _missing_optional_feed_video_column(message):
                cur = conn.cursor()
                continue
            raise
    return []


def _active_feed_video_rows_sql(
    *,
    include_source_metadata: bool,
    include_short_description: bool,
    include_display_metadata: bool,
    include_integrity_metadata: bool,
    include_popularity_metadata: bool = True,
) -> str:
    if include_source_metadata:
        source_columns = "source_category,\n            source_query,"
    else:
        source_columns = "topic AS source_category,\n            NULL AS source_query,"

    if include_popularity_metadata:
        popularity_columns = "source_type,\n            popularity_score,"
    else:
        popularity_columns = "'search' AS source_type,\n            0 AS popularity_score,"

    if include_short_description:
        short_description_column = "short_description,"
    else:
        short_description_column = "NULL AS short_description,"

    if include_display_metadata:
        display_columns = (
            "display_title,\n"
            "            display_channel,\n"
            "            display_hashtags,"
        )
    else:
        display_columns = (
            "NULL AS display_title,\n"
            "            NULL AS display_channel,\n"
            "            NULL AS display_hashtags,"
        )

    if include_integrity_metadata:
        integrity_columns = (
            "integrity_score,\n"
            "            integrity_flags,\n"
            "            production_style,\n"
            "            creator_scale,"
        )
    else:
        integrity_columns = (
            "NULL AS integrity_score,\n"
            "            NULL AS integrity_flags,\n"
            "            NULL AS production_style,\n"
            "            NULL AS creator_scale,"
        )
    return f"""
        SELECT
            youtube_video_id AS video_id,
            title,
            description,
            channel_id,
            channel_title,
            topic,
            category_id,
            tags,
            duration_seconds,
            {source_columns}
            {popularity_columns}
            {short_description_column}
            {display_columns}
            {integrity_columns}
            thumbnail_url,
            embed_url,
            watch_url,
            view_count,
            published_at,
            score AS ingest_score,
            chrysalis_scores,
            ranking_reason,
            safety_reason,
            concern_reason,
            label_confidence,
            scoring_version
        FROM feed_videos
        WHERE status = 'active'
        ORDER BY score DESC, published_at DESC
    """


def _active_feed_video_column_attempts() -> list[dict]:
    return [
        {
            "include_source_metadata": True,
            "include_short_description": True,
            "include_display_metadata": True,
            "include_integrity_metadata": True,
            "include_popularity_metadata": True,
        },
        # Popular-lane columns may not exist yet on a freshly deployed DB (before
        # the first ingest runs the ADD COLUMN migration). Fall back gracefully
        # while keeping every other piece of metadata.
        {
            "include_source_metadata": True,
            "include_short_description": True,
            "include_display_metadata": True,
            "include_integrity_metadata": True,
            "include_popularity_metadata": False,
        },
        {
            "include_source_metadata": True,
            "include_short_description": True,
            "include_display_metadata": False,
            "include_integrity_metadata": True,
            "include_popularity_metadata": False,
        },
        {
            "include_source_metadata": True,
            "include_short_description": True,
            "include_display_metadata": False,
            "include_integrity_metadata": False,
            "include_popularity_metadata": False,
        },
        {
            "include_source_metadata": True,
            "include_short_description": False,
            "include_display_metadata": False,
            "include_integrity_metadata": False,
            "include_popularity_metadata": False,
        },
        {
            "include_source_metadata": False,
            "include_short_description": False,
            "include_display_metadata": False,
            "include_integrity_metadata": False,
            "include_popularity_metadata": False,
        },
    ]


def _missing_optional_feed_video_column(message: str) -> bool:
    return (
        "source_category" in message
        or "source_query" in message
        or "source_type" in message
        or "popularity_score" in message
        or "short_description" in message
        or "display_title" in message
        or "display_channel" in message
        or "display_hashtags" in message
        or "integrity_score" in message
        or "integrity_flags" in message
        or "production_style" in message
        or "creator_scale" in message
    )


def merge_primary_rows(primary: list[dict], fallback: list[dict]) -> list[dict]:
    """Return primary rows first, then fallback rows that are not duplicate videos."""
    seen = {
        str(row.get("video_id") or row.get("youtube_id") or "").strip()
        for row in primary
    }
    merged = list(primary)
    for row in fallback:
        video_id = str(row.get("video_id") or row.get("youtube_id") or "").strip()
        if not video_id or video_id in seen:
            continue
        seen.add(video_id)
        merged.append(row)
    return merged


def _youtube_request_json(api_key: str) -> RequestJson:
    def request(endpoint: str, params: dict) -> dict | None:
        params = dict(params)
        params["key"] = api_key
        url = f"{YOUTUBE_API_BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=12) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
            print(f"[youtube_ingest] YouTube API error on {endpoint}: {exc}")
            return None
    return request


def _candidate_from_video_item(
    item: dict,
    *,
    source_spec: SourceQuerySpec,
    now: datetime,
    days_back: int,
    source_type: str = "search",
    blocked_channel_ids: set[str] | None = None,
) -> FeedVideoCandidate | None:
    video_id = str(item.get("id") or "").strip()
    if not video_id:
        return None

    # Hard denylist: a blocked channel is never ingested or served, even if the
    # video passes every other filter and even from the trusted lane (Part B).
    if blocked_channel_ids:
        channel_id = str((item.get("snippet") or {}).get("channelId") or "").strip()
        if channel_id and channel_id in blocked_channel_ids:
            return None

    status = item.get("status") or {}
    if status.get("embeddable") is not True:
        return None
    if status.get("privacyStatus") and status.get("privacyStatus") != "public":
        return None
    if status.get("uploadStatus") and status.get("uploadStatus") != "processed":
        return None

    snippet = item.get("snippet") or {}
    details = item.get("contentDetails") or {}
    stats = item.get("statistics") or {}
    title = str(snippet.get("title") or "").strip()
    description = str(snippet.get("description") or "").strip()
    tags = [str(tag) for tag in (snippet.get("tags") or [])]
    duration_seconds = parse_duration_seconds(details.get("duration"))
    if duration_seconds is None or duration_seconds > MAX_ALLOWED_SECONDS:
        return None
    if duration_seconds > SHORT_TARGET_SECONDS:
        # "Keep under 180 seconds if possible": allow up to YouTube's short
        # window only when the rest of the metadata is very relevant.
        soft_duration_penalty = True
    else:
        soft_duration_penalty = False

    text = " ".join([title, description, " ".join(tags), snippet.get("channelTitle") or ""])
    if _contains_blocked_term(text):
        return None

    # Demo US/English-only policy: never ingest Hindi/Arabic (or non-US) videos.
    if not language_allowed({
        "title": title,
        "description": description,
        "tags": tags,
        "channel_title": snippet.get("channelTitle") or "",
        "default_language": snippet.get("defaultLanguage"),
        "default_audio_language": snippet.get("defaultAudioLanguage"),
    }):
        return None

    published_at = str(snippet.get("publishedAt") or "")
    view_count = _safe_int(stats.get("viewCount"))
    like_count = _safe_int(stats.get("likeCount"))
    comment_count = _safe_int(stats.get("commentCount"))
    popularity_score = _popularity_score(
        view_count=view_count,
        like_count=like_count,
        comment_count=comment_count,
        published_at=published_at,
        now=now,
    )
    source_category = source_spec.source_category or "custom"
    source_query = source_spec.source_query
    topic = source_category
    thumbnail_url = _best_thumbnail(snippet)
    short_description = build_short_description(description)
    channel_title = str(snippet.get("channelTitle") or "")
    display_title = build_display_title(title)
    display_channel = build_display_channel(channel_title)
    display_hashtags = build_display_hashtags(title, description)

    row_for_scoring = {
        "title": title,
        "description": description,
        "short_description": short_description,
        "tags": tags,
        "channel_title": channel_title,
        "video_id": video_id,
        "category": source_category,
        "topic": source_category,
        "source_category": source_category,
        "source_query": source_query,
        "category_id": snippet.get("categoryId") or "",
        "duration_seconds": duration_seconds,
        "thumbnail_url": thumbnail_url,
        "embed_url": f"https://www.youtube-nocookie.com/embed/{video_id}",
        "watch_url": f"https://www.youtube.com/watch?v={video_id}",
        "view_count": view_count,
        "like_count": _safe_int(stats.get("likeCount")),
        "comment_count": _safe_int(stats.get("commentCount")),
    }
    labels = score_metadata(row_for_scoring)
    integrity = score_feed_integrity(row_for_scoring, labels=labels.to_dict())
    relevance = _relevance_score(
        title=title,
        description=description,
        tags=tags,
        query=source_query,
        source_category=source_category,
        published_at=published_at,
        duration_seconds=duration_seconds,
        view_count=view_count,
        labels=labels.to_dict(),
        now=now,
        days_back=days_back,
    )
    if soft_duration_penalty:
        relevance *= 0.78
    if relevance < MIN_RELEVANCE_SCORE:
        return None

    reasons = build_reasons(labels, "flutter-feed")
    timestamp = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return FeedVideoCandidate(
        id=video_id,
        source="youtube",
        youtube_video_id=video_id,
        title=title,
        channel_title=channel_title,
        channel_id=str(snippet.get("channelId") or ""),
        description=description,
        short_description=short_description,
        display_title=display_title,
        display_channel=display_channel,
        display_hashtags=display_hashtags,
        thumbnail_url=thumbnail_url,
        embed_url=f"https://www.youtube-nocookie.com/embed/{video_id}",
        watch_url=f"https://www.youtube.com/watch?v={video_id}",
        published_at=published_at,
        duration_seconds=duration_seconds,
        view_count=view_count,
        tags=tags,
        category_id=str(snippet.get("categoryId") or ""),
        topic=topic,
        source_category=source_category,
        source_query=source_query,
        integrity_score=integrity["integrity_score"],
        integrity_flags=integrity["integrity_flags"],
        production_style=integrity["production_style"],
        creator_scale=integrity["creator_scale"],
        score=round(relevance, 4),
        status="active",
        created_at=timestamp,
        updated_at=timestamp,
        chrysalis_scores=labels.to_dict(),
        ranking_reason=reasons["ranking_reason"],
        safety_reason=reasons["safety_reason"],
        concern_reason=reasons["concern_reason"],
        label_confidence=labels.confidence,
        scored_at=timestamp,
        scoring_version=SCORING_VERSION,
        source_type=source_type,
        popularity_score=popularity_score,
    )


def _upsert_sqlite_candidate(conn: sqlite3.Connection, candidate: FeedVideoCandidate) -> None:
    placeholders = ",".join(["?"] * 39)
    conn.execute(
        f"""
        INSERT INTO feed_videos (
            id, source, youtube_video_id, title, channel_title, channel_id,
            description, short_description, display_title, display_channel,
            display_hashtags, thumbnail_url, embed_url, watch_url, published_at,
            duration_seconds, view_count, tags, category_id, topic,
            source_category, source_query, integrity_score, integrity_flags,
            production_style, creator_scale, score, created_at, updated_at, status,
            chrysalis_scores, ranking_reason, safety_reason, concern_reason,
            label_confidence, scored_at, scoring_version,
            source_type, popularity_score
        ) VALUES (
            {placeholders}
        )
        ON CONFLICT(youtube_video_id) DO UPDATE SET
            source_type = excluded.source_type,
            popularity_score = excluded.popularity_score,
            title = excluded.title,
            channel_title = excluded.channel_title,
            channel_id = excluded.channel_id,
            description = excluded.description,
            short_description = excluded.short_description,
            display_title = excluded.display_title,
            display_channel = excluded.display_channel,
            display_hashtags = excluded.display_hashtags,
            thumbnail_url = excluded.thumbnail_url,
            embed_url = excluded.embed_url,
            watch_url = excluded.watch_url,
            published_at = excluded.published_at,
            duration_seconds = excluded.duration_seconds,
            view_count = excluded.view_count,
            tags = excluded.tags,
            category_id = excluded.category_id,
            topic = excluded.topic,
            source_category = excluded.source_category,
            source_query = excluded.source_query,
            integrity_score = excluded.integrity_score,
            integrity_flags = excluded.integrity_flags,
            production_style = excluded.production_style,
            creator_scale = excluded.creator_scale,
            score = excluded.score,
            updated_at = excluded.updated_at,
            status = excluded.status,
            chrysalis_scores = excluded.chrysalis_scores,
            ranking_reason = excluded.ranking_reason,
            safety_reason = excluded.safety_reason,
            concern_reason = excluded.concern_reason,
            label_confidence = excluded.label_confidence,
            scored_at = excluded.scored_at,
            scoring_version = excluded.scoring_version
        """,
        _candidate_sqlite_values(candidate),
    )


def _upsert_postgres_candidate(cur, candidate: FeedVideoCandidate) -> None:
    values = _candidate_postgres_values(candidate)
    placeholders = ["%s"] * 39
    for index in (10, 17, 23, 30):
        placeholders[index] = "%s::jsonb"
    cur.execute(
        f"""
        INSERT INTO feed_videos (
            id, source, youtube_video_id, title, channel_title, channel_id,
            description, short_description, display_title, display_channel,
            display_hashtags, thumbnail_url, embed_url, watch_url, published_at,
            duration_seconds, view_count, tags, category_id, topic,
            source_category, source_query, integrity_score, integrity_flags,
            production_style, creator_scale, score, created_at, updated_at, status,
            chrysalis_scores, ranking_reason, safety_reason, concern_reason,
            label_confidence, scored_at, scoring_version,
            source_type, popularity_score
        ) VALUES (
            {",".join(placeholders)}
        )
        ON CONFLICT(youtube_video_id) DO UPDATE SET
            source_type = excluded.source_type,
            popularity_score = excluded.popularity_score,
            title = excluded.title,
            channel_title = excluded.channel_title,
            channel_id = excluded.channel_id,
            description = excluded.description,
            short_description = excluded.short_description,
            display_title = excluded.display_title,
            display_channel = excluded.display_channel,
            display_hashtags = excluded.display_hashtags,
            thumbnail_url = excluded.thumbnail_url,
            embed_url = excluded.embed_url,
            watch_url = excluded.watch_url,
            published_at = excluded.published_at,
            duration_seconds = excluded.duration_seconds,
            view_count = excluded.view_count,
            tags = excluded.tags,
            category_id = excluded.category_id,
            topic = excluded.topic,
            source_category = excluded.source_category,
            source_query = excluded.source_query,
            integrity_score = excluded.integrity_score,
            integrity_flags = excluded.integrity_flags,
            production_style = excluded.production_style,
            creator_scale = excluded.creator_scale,
            score = excluded.score,
            updated_at = excluded.updated_at,
            status = excluded.status,
            chrysalis_scores = excluded.chrysalis_scores,
            ranking_reason = excluded.ranking_reason,
            safety_reason = excluded.safety_reason,
            concern_reason = excluded.concern_reason,
            label_confidence = excluded.label_confidence,
            scored_at = excluded.scored_at,
            scoring_version = excluded.scoring_version
        """,
        values,
    )


def _candidate_sqlite_values(candidate: FeedVideoCandidate) -> tuple:
    return (
        candidate.id,
        candidate.source,
        candidate.youtube_video_id,
        candidate.title,
        candidate.channel_title,
        candidate.channel_id,
        candidate.description,
        candidate.short_description,
        candidate.display_title,
        candidate.display_channel,
        json.dumps(candidate.display_hashtags),
        candidate.thumbnail_url,
        candidate.embed_url,
        candidate.watch_url,
        candidate.published_at,
        candidate.duration_seconds,
        candidate.view_count,
        json.dumps(candidate.tags),
        candidate.category_id,
        candidate.topic,
        candidate.source_category,
        candidate.source_query,
        candidate.integrity_score,
        json.dumps(candidate.integrity_flags),
        candidate.production_style,
        candidate.creator_scale,
        candidate.score,
        candidate.created_at,
        candidate.updated_at,
        candidate.status,
        json.dumps(candidate.chrysalis_scores),
        candidate.ranking_reason,
        candidate.safety_reason,
        candidate.concern_reason,
        candidate.label_confidence,
        candidate.scored_at,
        candidate.scoring_version,
        candidate.source_type,
        candidate.popularity_score,
    )


def _candidate_postgres_values(candidate: FeedVideoCandidate) -> tuple:
    values = list(_candidate_sqlite_values(candidate))
    # display_hashtags, tags, integrity_flags, and chrysalis_scores are JSONB in Postgres.
    return tuple(values)


def _relevance_score(
    *,
    title: str,
    description: str,
    tags: list[str],
    query: str,
    source_category: str,
    published_at: str,
    duration_seconds: int | None,
    view_count: int,
    labels: dict,
    now: datetime,
    days_back: int,
) -> float:
    title_l = title.lower()
    blob = " ".join([title, description, " ".join(tags)]).lower()
    query_terms = [
        term
        for term in f"{source_category} {query}".lower().replace("/", " ").split()
        if len(term) > 2
    ]
    keyword_hits = 0.0
    for term in (*RELEVANCE_TERMS, *query_terms):
        if term in title_l:
            keyword_hits += 1.7
        elif term in blob:
            keyword_hits += 1.0
    keyword_score = _clamp01(keyword_hits / 8.0)

    recency_score = _recency_score(published_at, now, days_back)
    duration_score = 1.0 if duration_seconds and duration_seconds <= SHORT_TARGET_SECONDS else 0.45
    engagement_boost = _clamp01(math.log10(max(view_count, 0) + 1) / 6.0)
    metadata_signal_score = max(
        float(labels.get("calm", 0.0)),
        float(labels.get("educational", 0.0)),
        float(labels.get("self_love", 0.0)),
        float(labels.get("reflection_value", 0.0)),
        float(labels.get("prosocial", 0.0)),
        float(labels.get("novelty", 0.0)),
    )
    risk_penalty = float(labels.get("overall_risk", 0.0)) * 0.42

    return _clamp01(
        keyword_score * 0.46
        + recency_score * 0.22
        + duration_score * 0.17
        + metadata_signal_score * 0.11
        + engagement_boost * 0.04
        - risk_penalty
    )


def _popularity_score(
    *,
    view_count: int,
    like_count: int,
    comment_count: int,
    published_at: str,
    now: datetime,
) -> float:
    """Capped 0–1 popularity signal from engagement + freshness.

    Each raw count is log-compressed so a 50M-view viral clip is not orders of
    magnitude above a solid 200k-view video — that compression, plus the small
    weight this score carries at ranking time, is what stops one viral/music/
    gaming hit from dominating the feed. Freshness keeps the "popular" lane
    feeling current rather than resurfacing old evergreen virality.
    """
    views = _clamp01(math.log10(max(view_count, 0) + 1) / 7.0)   # ~1.0 at 10M views
    likes = _clamp01(math.log10(max(like_count, 0) + 1) / 6.0)    # ~1.0 at 1M likes
    comments = _clamp01(math.log10(max(comment_count, 0) + 1) / 5.0)  # ~1.0 at 100k
    freshness = _recency_score(published_at, now, days_back=14)
    return _clamp01(
        0.50 * views
        + 0.25 * likes
        + 0.15 * comments
        + 0.10 * freshness
    )


def _recency_score(published_at: str, now: datetime, days_back: int) -> float:
    try:
        published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return 0.0
    age_days = max(0.0, (now - published).total_seconds() / 86400)
    return _clamp01(1.0 - (age_days / max(days_back, 1)))


def _contains_blocked_term(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in BLOCKED_TERMS)


def _best_thumbnail(snippet: dict) -> str:
    thumbs = snippet.get("thumbnails") or {}
    for size in _THUMBNAIL_PREFERENCE:
        url = (thumbs.get(size) or {}).get("url")
        if url:
            return url
    return ""


def _safe_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _chunks(items: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(items), size):
        yield items[index:index + size]


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
