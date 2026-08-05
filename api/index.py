import sys
import json
import os
from datetime import date
from pathlib import Path

import psycopg2
import pandas as pd
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.algorithm import (
    WEIGHTS,
    add_engagement,
    build_prototype_feed,
    get_mode_settings,
    rank_baseline,
    validate_and_clean,
)
from core.metrics import diversity_at_k, max_streak, prosocial_ratio
from core.ranking.feed import build_feed_payload
from core.ranking.modes import is_valid_mode, MODES
from core.public_signals.storage import load_cached_context_postgres, load_or_scan_context_postgres
from integrations.youtube_ingest import (
    YouTubeIngestError,
    ingest_youtube_videos_postgres,
    load_active_feed_video_rows_postgres,
)
from integrations.youtube_service import (
    fetch_videos_by_topic,
    get_youtube_id_for_video,
    get_all_topics_cache_status,
)
from core.preferences import (
    DEFAULT_LANGUAGE,
    DEFAULT_REGION,
    default_preferences,
    ensure_postgres_preferences_table,
    get_preferences,
    upsert_preferences,
)
from research_api import create_research_router

ROOT = Path(__file__).parent.parent
DEFAULT_DATASET = ROOT / "data" / "datasets" / "processed_dataset.csv"



def get_db():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def _load_research_feed_source(conn):
    rows = list(load_active_feed_video_rows_postgres(conn))
    try:
        context = (
            load_or_scan_context_postgres(conn, rows)
            if REFRESH_PUBLIC_SIGNALS_ON_FEED
            else load_cached_context_postgres(conn, rows)
        )
    except Exception as exc:
        print(f"[research_feed] public-signal cache unavailable: {exc}")
        context = None
    return rows, context


def _load_content_preferences(session_id: str | None, user_id: str | None) -> dict:
    """Load saved language/region preferences (English + US defaults if none).

    Never raises — if the preferences table or DB is unavailable we fall back to
    defaults so the feed keeps working.
    """
    try:
        conn = get_db()
    except Exception:
        return default_preferences(user_id=user_id, session_id=session_id)
    try:
        ensure_postgres_preferences_table(conn)
        return get_preferences(
            conn, backend="postgres", user_id=user_id, session_id=session_id
        )
    except Exception:
        conn.rollback()
        return default_preferences(user_id=user_id, session_id=session_id)
    finally:
        conn.close()


app = FastAPI()

app.include_router(create_research_router(
    get_connection=get_db,
    backend="postgres",
    load_feed_source=_load_research_feed_source,
))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REFRESH_PUBLIC_SIGNALS_ON_FEED = os.getenv(
    "CHRYSALIS_REFRESH_PUBLIC_SIGNALS_ON_FEED",
    "",
).lower() in {"1", "true", "yes"}


def _require_feed_ingest_secret(header_secret: str | None, query_secret: str | None) -> None:
    expected = os.environ.get("FEED_INGEST_SECRET", "")
    if not expected:
        raise HTTPException(
            status_code=500,
            detail="FEED_INGEST_SECRET is not configured on the backend.",
        )
    if header_secret != expected and query_secret != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


class RunLocalRequest(BaseModel):
    preset: str = Field(default="entertainment")
    night_mode: bool = Field(default=False)
    recent_window: int = Field(default=10)
    serendipity_weight: float = Field(default=None, ge=0.0, le=10.0)
    similarity_weight: float = Field(default=None, ge=0.0, le=10.0)
    dataset_path: str = Field(default=None)
    passive_streak: int = Field(default=0)
    user_trait: str = Field(default="urban")


def metrics_for_feed(feed: pd.DataFrame) -> dict:
    return {
        "diversity_at_10": int(diversity_at_k(feed, k=10, topic_col="topic")),
        "max_topic_streak": int(max_streak(feed, "topic")),
        "max_creator_streak": int(max_streak(feed, "channel")),
        "prosocial_ratio": float(prosocial_ratio(feed, prosocial_col="prosocial")),
    }


def ensure_algorithm_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    _defaults = {
        "topic": "unlabeled",
        "prosocial": 0,
        "risk": 0,
        "active_engagement_ratio": 0.0,
        "creator_authenticity": 0.5,
    }
    for col, default in _defaults.items():
        if col not in out.columns:
            out[col] = default
    return out


@app.post("/api/run/local")
def run_local(request: RunLocalRequest):
    dataset_path = Path(request.dataset_path) if request.dataset_path else DEFAULT_DATASET
    if not dataset_path.exists():
        raise HTTPException(status_code=400, detail=f"Dataset not found: {dataset_path}")

    df = pd.read_csv(dataset_path)
    df = ensure_algorithm_columns(df)
    df = validate_and_clean(df)
    df, _ = add_engagement(df)

    weights, k = get_mode_settings(preset=request.preset, night_mode=request.night_mode, k_default=100)

    if request.serendipity_weight is not None:
        weights["d"] = request.serendipity_weight
    if request.similarity_weight is not None:
        weights["r"] = request.similarity_weight

    user_profile = {"user_trait": request.user_trait, "passive_streak": request.passive_streak}

    improved = build_prototype_feed(
        df, weights=weights, user_profile=user_profile, k=k, recent_window=request.recent_window
    ).reset_index(drop=True)
    baseline = rank_baseline(df, k=k).reset_index(drop=True)

    cols = [
        c for c in [
            "video_id", "title", "topic", "channel",
            "prosocial", "risk", "engagement", "diversity",
            "score", "appearance_comparison", "creator_trait",
        ] if c in improved.columns
    ]

    feed_records = improved[cols].head(min(k, 50)).to_dict(orient="records")

    for item in feed_records:
        topic = item.get("topic", "entertainment")
        seed = item.get("video_id", "fallback")
        item["youtube_id"] = get_youtube_id_for_video(topic, seed)

    return {
        "preset": request.preset,
        "night_mode": request.night_mode,
        "k": k,
        "weights": weights,
        "improved_metrics": metrics_for_feed(improved),
        "baseline_metrics": metrics_for_feed(baseline),
        "improved_feed": feed_records,
    }


@app.get("/api/youtube/videos/{topic}")
def youtube_videos(
    topic: str,
    max_results: int = 12,
    session_id: str | None = None,
    user_id: str | None = None,
):
    prefs = _load_content_preferences(session_id, user_id)
    ids = fetch_videos_by_topic(
        topic,
        max_results=max_results,
        relevance_language=prefs["preferred_language"],
        region_code=prefs["region_code"],
    )
    return {
        "topic": topic,
        "video_ids": ids,
        "count": len(ids),
        "relevance_language": prefs["preferred_language"],
        "region_code": prefs["region_code"],
    }


@app.get("/api/youtube/cache")
def youtube_cache():
    return get_all_topics_cache_status()


@app.post("/api/admin/ingest/youtube")
def admin_ingest_youtube(
    secret: str | None = None,
    x_feed_ingest_secret: str | None = Header(None, alias="X-Feed-Ingest-Secret"),
    max_results_per_query: int = 10,
    days_back: int = 7,
    relevance_language: str = DEFAULT_LANGUAGE,
    region_code: str = DEFAULT_REGION,
):
    _require_feed_ingest_secret(x_feed_ingest_secret, secret)
    conn = get_db()
    try:
        result = ingest_youtube_videos_postgres(
            conn,
            max_results_per_query=max_results_per_query,
            days_back=days_back,
            relevance_language=relevance_language,
            region_code=region_code,
        )
    except YouTubeIngestError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        conn.close()
    return result.to_dict()


def _parse_exclude_ids(raw: str | None, *, limit: int = 500) -> list[str]:
    """Parse a comma-separated ``exclude_ids`` query value into a clean id list.

    Bounded so a runaway client cannot send an unbounded URL; dedupes while
    preserving order.
    """
    if not raw:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for piece in str(raw).split(","):
        vid = piece.strip()
        if not vid or vid in seen:
            continue
        seen.add(vid)
        out.append(vid)
        if len(out) >= limit:
            break
    return out


@app.get("/api/feed/{mode}")
def chrysalis_feed(
    mode: str,
    k: int = 12,
    seed: str | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    offset: int = 0,
    exclude_ids: str | None = None,
):
    """
    Shared real-video feed for a reels mode (daily-dew, metamorphosis,
    flutter-feed). Modes change explanation/reflection copy, not the source pool.
    Returns an empty list when there are no scored candidates — the frontend then
    falls back to its built-in sample cards.

    Language/region preferences are loaded and echoed back, but the served pool
    is pre-ingested and not re-queried per request (see migration 009 notes).
    """
    if not is_valid_mode(mode):
        raise HTTPException(status_code=400, detail=f"mode must be one of {list(MODES)}")

    prefs = _load_content_preferences(session_id, user_id)

    rows: list[dict] = []
    public_signal_context = None
    conn = get_db()
    try:
        cur = conn.cursor()
        feed_rows = load_active_feed_video_rows_postgres(conn)
        rows = list(feed_rows)
        try:
            # Feed reads are read-only by default. Set
            # CHRYSALIS_REFRESH_PUBLIC_SIGNALS_ON_FEED=1 only when you explicitly
            # want GET /api/feed/* to populate the no-network stub cache.
            if REFRESH_PUBLIC_SIGNALS_ON_FEED:
                public_signal_context = load_or_scan_context_postgres(conn, rows)
            else:
                public_signal_context = load_cached_context_postgres(conn, rows)
        except Exception as exc:
            print(f"[public_signals] scanner cache unavailable: {exc}")
    except Exception:
        rows = []
    finally:
        conn.close()

    payload = build_feed_payload(
        rows,
        mode,
        k=k,
        public_signal_context=public_signal_context,
        shuffle_seed=seed,
        offset=offset,
        exclude_ids=_parse_exclude_ids(exclude_ids),
    )
    return {
        "mode": mode,
        "relevance_language": prefs["preferred_language"],
        "region_code": prefs["region_code"],
        **payload,
    }


# ---------------------------------------------------------------------------
# Content preferences (language + region targeting)
# ---------------------------------------------------------------------------

class ContentPreferencesRequest(BaseModel):
    user_id: str | None = None
    session_id: str | None = None
    preferred_language: str | None = None
    region_code: str | None = None
    use_approx_location: bool | None = None
    location_city: str | None = None
    location_country: str | None = None
    has_completed_language_setup: bool | None = None


@app.get("/api/preferences")
def get_content_preferences(session_id: str | None = None, user_id: str | None = None):
    """Return current content preferences (English + US defaults if none saved)."""
    return _load_content_preferences(session_id, user_id)


@app.post("/api/preferences")
def save_content_preferences(request: ContentPreferencesRequest):
    """Create or update content preferences for the current user/session."""
    if not request.user_id and not request.session_id:
        raise HTTPException(status_code=400, detail="user_id or session_id is required.")
    conn = get_db()
    try:
        ensure_postgres_preferences_table(conn)
        return upsert_preferences(
            conn,
            backend="postgres",
            user_id=request.user_id,
            session_id=request.session_id,
            preferred_language=request.preferred_language,
            region_code=request.region_code,
            use_approx_location=request.use_approx_location,
            location_city=request.location_city,
            location_country=request.location_country,
            has_completed_language_setup=request.has_completed_language_setup,
        )
    finally:
        conn.close()


@app.get("/api/cron/extract")
def cron_extract(
    authorization: str = Header(None),
    relevance_language: str = DEFAULT_LANGUAGE,
    region_code: str = DEFAULT_REGION,
    max_results_per_query: int = 15,
    days_back: int = 7,
):
    """Daily YouTube ingestion cron.

    Delegates to the canonical ``ingest_youtube_videos_postgres`` path so the
    cron writes into ``feed_videos`` — the exact table ``GET /api/feed/{mode}``
    reads from via ``load_active_feed_video_rows_postgres``.

    Locale targeting is preserved end-to-end by the ingest path: search.list
    uses ``relevanceLanguage`` + ``regionCode`` and videos.list uses ``hl`` +
    ``regionCode``, defaulting to en / US.
    """
    cron_secret = os.environ.get("CRON_SECRET", "")
    if cron_secret and authorization != f"Bearer {cron_secret}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    conn = get_db()
    try:
        result = ingest_youtube_videos_postgres(
            conn,
            max_results_per_query=max_results_per_query,
            days_back=days_back,
            relevance_language=relevance_language,
            region_code=region_code,
        )
    except YouTubeIngestError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        conn.close()

    payload = result.to_dict()
    payload["table"] = "feed_videos"
    return payload
