from contextlib import asynccontextmanager
import json
import os
import sqlite3
from datetime import date

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
from pathlib import Path
from core.algorithm import (
    WEIGHTS,
    add_engagement,
    build_prototype_feed,
    get_mode_settings,
    rank_baseline,
    validate_and_clean,
)
from core.metrics import diversity_at_k, max_streak, prosocial_ratio
from core.database import resolve_database_path
from core.ranking.feed import build_feed_payload
from core.ranking.modes import is_valid_mode, MODES
from core.public_signals.storage import load_cached_context_sqlite, load_or_scan_context_sqlite
from integrations.youtube_service import fetch_videos_by_topic, get_youtube_id_for_video, get_all_topics_cache_status
from integrations.youtube_ingest import (
    YouTubeIngestError,
    ingest_youtube_videos_sqlite,
    load_active_feed_video_rows_sqlite,
    merge_primary_rows,
)
from core.preferences import (
    DEFAULT_LANGUAGE,
    DEFAULT_REGION,
    default_preferences,
    ensure_sqlite_preferences_table,
    get_preferences,
    upsert_preferences,
)
from migration_scheduler import create_scheduler
from core.cocoon import (
    CocoonProfile,
    calculate_this_weeks_cap,
    should_graduate,
    advance_week,
)

DB_PATH = resolve_database_path()
REFRESH_PUBLIC_SIGNALS_ON_FEED = os.getenv(
    "CHRYSALIS_REFRESH_PUBLIC_SIGNALS_ON_FEED",
    "",
).lower() in {"1", "true", "yes"}


def _require_feed_ingest_secret(
    header_secret: str | None,
    query_secret: str | None,
) -> None:
    expected = os.environ.get("FEED_INGEST_SECRET", "")
    if not expected:
        raise HTTPException(
            status_code=500,
            detail="FEED_INGEST_SECRET is not configured on the backend.",
        )
    if header_secret != expected and query_secret != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _load_content_preferences(session_id: str | None, user_id: str | None) -> dict:
    """Load saved language/region preferences (English + US defaults if none).

    Preference lookup should never block the feed: if the local DB is missing or
    locked, callers still get safe defaults.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
    except Exception:
        return default_preferences(user_id=user_id, session_id=session_id)
    try:
        ensure_sqlite_preferences_table(conn)
        return get_preferences(
            conn, backend="sqlite", user_id=user_id, session_id=session_id
        )
    except Exception:
        return default_preferences(user_id=user_id, session_id=session_id)
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = create_scheduler()
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=json.loads(os.getenv(
        "CORS_ORIGINS",
        json.dumps([
            "http://localhost:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
            "http://localhost:8001",
            "http://localhost:3000",
            "null",
        ]),
    )),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT = Path(__file__).parent
DEFAULT_DATASET = ROOT / "datasets" / "processed_dataset.csv"

from pydantic import BaseModel, Field


class RunLocalRequest(BaseModel):
    preset: str = Field(default="entertainment", description="Algorithm preset template to load.", example="entertainment")
    night_mode: bool = Field(default=False, description="Toggle algorithm night mode parameters.")
    recent_window: int = Field(default=10, description="The maximum rolling window size for consecutive streak monitoring.")
    serendipity_weight: float = Field(default=None, description="Direct slider override for 'Serendipity / Diversity' ranking. Forces a Gini-coefficient evaluation.", ge=0.0, le=10.0, example=2.0)
    similarity_weight: float = Field(default=None, description="Internal algorithm modifier. Controls how harshly to penalize upward appearance comparison. Handled on backend inherently.", ge=0.0, le=10.0, example=5.0)
    dataset_path: str = Field(default=None, description="Internal path route. Leave null to read default dataset.")
    passive_streak: int = Field(default=0, description="Integer representing how many videos the user has consumed without engaging. Degrades baseline engagement score via Decay Function.")
    user_trait: str = Field(default="urban", description="Current mock user demographic trait. (urban, rural, suburban, international)", example="urban")

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

    weights, k = get_mode_settings(
        preset=request.preset, night_mode=request.night_mode, k_default=100)
    
    # Apply direct UCRS overrides
    if request.serendipity_weight is not None:
        weights["d"] = request.serendipity_weight
    if request.similarity_weight is not None:
        weights["r"] = request.similarity_weight
        
    user_profile = {
        "user_trait": request.user_trait,
        "passive_streak": request.passive_streak
    }
    
    improved = build_prototype_feed(
        df, weights=weights, user_profile=user_profile, k=k, recent_window=request.recent_window
    ).reset_index(drop=True)
    
    baseline = rank_baseline(df, k=k).reset_index(drop=True)

    cols = [
        c for c in [
            "video_id", "title", "topic", "channel", 
            "prosocial", "risk", "engagement", "diversity", 
            "score", "appearance_comparison", "creator_trait"
        ] if c in improved.columns
    ]

    feed_records = improved[cols].head(min(k, 50)).to_dict(orient="records")

    # Inject live YouTube video IDs into each feed item
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
        "improved_feed": feed_records
    }

@app.get("/api/youtube/videos/{topic}")
def youtube_videos(
    topic: str,
    max_results: int = 12,
    session_id: str | None = None,
    user_id: str | None = None,
):
    """Standalone endpoint to fetch live YouTube video IDs by topic.

    Honors the caller's saved language/region preferences (defaults en/US).
    """
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
    """Debug endpoint to inspect YouTube cache status."""
    return get_all_topics_cache_status()


@app.post("/api/admin/ingest/youtube")
def admin_ingest_youtube(
    secret: str | None = None,
    x_feed_ingest_secret: str | None = Header(default=None, alias="X-Feed-Ingest-Secret"),
    max_results_per_query: int = 10,
    days_back: int = 7,
    relevance_language: str = DEFAULT_LANGUAGE,
    region_code: str = DEFAULT_REGION,
):
    """
    Run the daily YouTube Data API ingestion.

    Auth: pass FEED_INGEST_SECRET either as `X-Feed-Ingest-Secret` or as a
    `?secret=` query parameter. This endpoint stores metadata only.

    `relevance_language` / `region_code` target ingestion globally (defaults
    en/US). Per-user preferences live in user_content_preferences and shape the
    live topic-fetch and feed responses, not this global batch.
    """
    _require_feed_ingest_secret(x_feed_ingest_secret, secret)
    try:
        result = ingest_youtube_videos_sqlite(
            db_path=DB_PATH,
            max_results_per_query=max_results_per_query,
            days_back=days_back,
            relevance_language=relevance_language,
            region_code=region_code,
        )
    except YouTubeIngestError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result.to_dict()


def _parse_exclude_ids(raw: str | None, *, limit: int = 500) -> list[str]:
    """Parse a comma-separated ``exclude_ids`` query value into a clean id list."""
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

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    public_signal_context = None
    try:
        feed_rows = load_active_feed_video_rows_sqlite(conn)
        try:
            legacy_rows = [dict(r) for r in conn.execute("SELECT * FROM videos").fetchall()]
        except sqlite3.OperationalError:
            legacy_rows = []
        rows = merge_primary_rows(feed_rows, legacy_rows)
        try:
            # Feed reads are read-only by default. Set
            # CHRYSALIS_REFRESH_PUBLIC_SIGNALS_ON_FEED=1 only when you explicitly
            # want GET /api/feed/* to populate the no-network stub cache.
            if REFRESH_PUBLIC_SIGNALS_ON_FEED:
                public_signal_context = load_or_scan_context_sqlite(conn, rows)
            else:
                public_signal_context = load_cached_context_sqlite(conn, rows)
        except Exception as exc:
            print(f"[public_signals] scanner cache unavailable: {exc}")
    except sqlite3.OperationalError:
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
    conn = sqlite3.connect(DB_PATH)
    try:
        ensure_sqlite_preferences_table(conn)
        return upsert_preferences(
            conn,
            backend="sqlite",
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


# ---------------------------------------------------------------------------
# Migration Mode
# ---------------------------------------------------------------------------

@app.get("/api/migration/today")
def migration_today():
    """
    Return today's Migration Mode drops (morning at 07:00, evening at 19:00).
    Each drop is the same 10-15 posts for every user — non-personalized.

    - 200: at least one drop has run; absent drop is null in the response.
    - 404: no drops have been written for today yet.
    """
    today = date.today().isoformat()
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            """
            SELECT mode, scheduled_at, feed_json, item_count
            FROM migration_drops
            WHERE drop_date = ?
            """,
            (today,),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No Migration Mode drops have run yet for {today}. "
                "Morning drop is scheduled for 07:00, evening drop for 19:00."
            ),
        )

    drops: dict = {}
    for mode, scheduled_at, feed_json, item_count in rows:
        drops[mode] = {
            "mode": mode,
            "scheduled_at": scheduled_at,
            "item_count": item_count,
            "feed": json.loads(feed_json),
        }

    return {
        "date": today,
        "morning": drops.get("morning"),   # None if not yet run
        "evening": drops.get("evening"),   # None if not yet run
    }


class CocoonEnrollRequest(BaseModel):
    user_id: str
    current_daily_minutes: int = Field(..., gt=0)


@app.post("/api/cocoon/enroll")
def cocoon_enroll(request: CocoonEnrollRequest):
    today = date.today().isoformat()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO cocoon_profiles
                (user_id, start_minutes, current_week, start_date, graduated)
            VALUES (?, ?, 0, ?, 0)
            """,
            (request.user_id, request.current_daily_minutes, today),
        )
        conn.commit()
        row = conn.execute(
            "SELECT start_minutes, current_week FROM cocoon_profiles WHERE user_id = ?",
            (request.user_id,),
        ).fetchone()
    finally:
        conn.close()

    profile = CocoonProfile(
        user_id=request.user_id,
        start_minutes=row[0],
        current_week=row[1],
        start_date=date.fromisoformat(today),
    )
    daily_cap = calculate_this_weeks_cap(profile)
    return {
        "user_id": profile.user_id,
        "start_minutes": profile.start_minutes,
        "current_week": profile.current_week,
        "daily_cap": daily_cap,
        "should_graduate": should_graduate(profile),
    }


@app.get("/api/cocoon/status/{user_id}")
def cocoon_status(user_id: str):
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT start_minutes, current_week, start_date, graduated FROM cocoon_profiles WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail=f"No Cocoon profile found for user '{user_id}'.")

    profile = CocoonProfile(
        user_id=user_id,
        start_minutes=row[0],
        current_week=row[1],
        start_date=date.fromisoformat(row[2]),
    )
    daily_cap = calculate_this_weeks_cap(profile)
    return {
        "user_id": user_id,
        "current_week": profile.current_week,
        "daily_cap": daily_cap,
        "minutes_remaining_today": daily_cap,
        "should_graduate": should_graduate(profile),
    }


@app.post("/api/cocoon/advance/{user_id}")
def cocoon_advance(user_id: str):
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT start_minutes, current_week, start_date FROM cocoon_profiles WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"No Cocoon profile found for user '{user_id}'.")

        profile = CocoonProfile(
            user_id=user_id,
            start_minutes=row[0],
            current_week=row[1],
            start_date=date.fromisoformat(row[2]),
        )
        next_profile = advance_week(profile)
        graduating = should_graduate(next_profile)
        conn.execute(
            "UPDATE cocoon_profiles SET current_week = ?, graduated = ? WHERE user_id = ?",
            (next_profile.current_week, int(graduating), user_id),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "user_id": user_id,
        "current_week": next_profile.current_week,
        "daily_cap": calculate_this_weeks_cap(next_profile),
        "graduated": graduating,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
