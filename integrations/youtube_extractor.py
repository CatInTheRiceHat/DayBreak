"""
youtube_extractor.py — Chrysalis Full Data Pipeline
======================================================
Fetches real YouTube videos and classifies them into algorithm columns
using a local Ollama LLM (qwen3.5 by default). No cloud AI cost.

Pipeline:
    YouTube Data API v3
        → Video metadata + statistics (title, description, views, likes, comments)
        ↓
    Ollama / qwen3.5  (runs locally, fully offline after first model pull)
        → Context-aware psychological scoring:
            • appearance_comparison  (0–1)
            • opinion_comparison     (0–1)
            • prosocial              (0–1)
            • risk                   (0–1)
            • creator_authenticity   (0–1)
        ↓
    Computed from raw stats:
        • active_engagement_ratio = (likes + comments) / views, scaled 0–1
        ↓
    SQLite  →  chrysalis.db  (persistent; never re-fetches what it has)
        ↓
    pandas DataFrame  →  ready for validate_and_clean() → build_prototype_feed()

Usage (as a script):
    python youtube_extractor.py
    python youtube_extractor.py --topics gaming music --max 20

Usage (as a module):
    from youtube_extractor import extract_and_classify
    df = extract_and_classify(topics=["gaming", "music"], max_per_topic=20)
"""

import os
import re
import json
import time
import sqlite3
import argparse
import sys
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.database import resolve_database_path
# Shared, safe ISO-8601 → seconds parser (also used by the scorer + Postgres cron).
from core.labeling.metadata_scoring import parse_duration_seconds
from core.preferences import normalize_language_code, normalize_region_code

# Load .env if present (same pattern as youtube_service.py)
_env_path = ROOT / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

YOUTUBE_API_KEY  = os.environ.get("YOUTUBE_API_KEY", "")
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"

OLLAMA_URL       = "http://localhost:11434"
PREFERRED_MODEL  = "qwen3.5"   # smartest available
FALLBACK_MODEL   = "qwen2.5"   # if qwen3.5 isn't listed

DB_PATH          = resolve_database_path()

# YouTube category ID ↔ Chrysalis topic mapping
# Note: some category IDs (e.g. 27-Education) are not available on the
# mostPopular chart in all regions — we gracefully skip those.
CATEGORY_TO_TOPIC: dict[str, str] = {
    "10": "music",
    "17": "sports",
    "20": "gaming",
    "24": "entertainment",
    "25": "news",
    "26": "lifestyle",
    "28": "education",   # 28=Science & Technology works; 27=Education often 404s
}
TOPIC_TO_CATEGORY: dict[str, str] = {v: k for k, v in CATEGORY_TO_TOPIC.items()}

ALL_TOPICS = list(TOPIC_TO_CATEGORY.keys())

# ---------------------------------------------------------------------------
# SQLite helpers
# ---------------------------------------------------------------------------

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS videos (
    video_id              TEXT PRIMARY KEY,
    title                 TEXT,
    description           TEXT,
    channel_id            TEXT,
    channel_title         TEXT,
    topic                 TEXT,
    category_id           TEXT,
    tags                  TEXT,
    duration_seconds      INTEGER,
    thumbnail_url         TEXT,
    view_count            INTEGER,
    like_count            INTEGER,
    comment_count         INTEGER,
    published_at          TEXT,
    active_engagement_ratio  REAL,
    appearance_comparison    REAL,
    opinion_comparison       REAL,
    prosocial                REAL,
    risk                     REAL,
    creator_authenticity     REAL,
    fetched_at               REAL,
    classified_at            REAL,
    -- Chrysalis label/ranking fields (v1). Nullable; populated by scripts/score_videos.py.
    chrysalis_scores         TEXT,
    ranking_reason           TEXT,
    safety_reason            TEXT,
    concern_reason           TEXT,
    label_confidence         REAL,
    scored_at                REAL,
    scoring_version          TEXT
)
"""

# Label columns added after the original schema — kept here so existing databases
# can be upgraded idempotently (SQLite has no "ADD COLUMN IF NOT EXISTS").
_LABEL_COLUMNS = (
    ("chrysalis_scores", "TEXT"),
    ("ranking_reason", "TEXT"),
    ("safety_reason", "TEXT"),
    ("concern_reason", "TEXT"),
    ("label_confidence", "REAL"),
    ("scored_at", "REAL"),
    ("scoring_version", "TEXT"),
)

# Richer YouTube metadata columns added after the original schema. Same idempotent
# upgrade path as the label columns; all nullable so pre-existing rows stay valid.
_METADATA_COLUMNS = (
    ("tags", "TEXT"),               # JSON-encoded list of snippet.tags
    ("duration_seconds", "INTEGER"),  # contentDetails.duration normalized to seconds
    ("thumbnail_url", "TEXT"),      # best available snippet.thumbnails URL
)


def _ensure_label_columns(conn: sqlite3.Connection) -> None:
    """Add any missing Chrysalis label + richer-metadata columns to `videos`."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(videos)")}
    for name, sql_type in (*_LABEL_COLUMNS, *_METADATA_COLUMNS):
        if name not in existing:
            conn.execute(f"ALTER TABLE videos ADD COLUMN {name} {sql_type}")
    conn.commit()


def _get_conn(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(_CREATE_TABLE_SQL)
    conn.commit()
    _ensure_label_columns(conn)
    try:
        from core.public_signals.storage import ensure_sqlite_public_signal_tables

        ensure_sqlite_public_signal_tables(conn)
    except Exception:
        # Public signals are optional context; extraction should still work if
        # this helper is unavailable in a standalone integration run.
        pass
    return conn


# ---------------------------------------------------------------------------
# Ollama helpers
# ---------------------------------------------------------------------------

def _detect_ollama_model() -> Optional[str]:
    """
    Returns the best available Ollama model name, or None if Ollama
    is not running or neither preferred model is installed.
    """
    try:
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/tags",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            installed = {m["name"].split(":")[0] for m in data.get("models", [])}
            for model in (PREFERRED_MODEL, FALLBACK_MODEL):
                if model.split(":")[0] in installed:
                    return model
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Classification prompt (the heart of the system)
# ---------------------------------------------------------------------------

_PROMPT_TEMPLATE = """\
You are a psychology researcher studying how social media content affects youth mental health.

Analyze this YouTube video and score it on exactly 5 dimensions, each from 0.0 to 1.0.

Title: {title}
Description: {description}
Category: {category}

Scoring guide:

appearance_comparison (0–1):
  How much does this video promote idealized bodies, beauty standards, or physical
  "before/after" transformations in ways that could cause harmful upward social comparison?
  0 = no appearance focus whatsoever
  1 = entirely about idealized looks (e.g. "Rate my transformation — I lost 40lbs in 30 days!")

opinion_comparison (0–1):
  How much does this video invite viewers to compare OPINIONS or debate IDEAS?
  This is PSYCHOLOGICALLY BENEFICIAL — healthy discourse supports identity formation.
  0 = no debate or perspective-sharing
  1 = purely about exchanging viewpoints (e.g. "Unpopular opinion: why social media is good")

prosocial (0–1):
  How much does this video promote community wellbeing, empathy, education, or positive connection?
  0 = no community/wellbeing value
  1 = highly prosocial (e.g. tutorial, mental health support, volunteering, kindness)

risk (0–1):
  How much could this video HARM youth mental health? Consider: toxic content, dangerous
  challenges, anxiety-inducing material, glorification of eating disorders or self-harm.
  0 = completely safe
  1 = highly risky (e.g. graphic content, toxic conflict, dangerous trend)

creator_authenticity (0–1):
  How genuine and consistent does this creator seem based on title/description style?
  Look for: excessive clickbait language, shock tactics, trend-chasing → lower score.
  Consistent niche, natural voice, genuine self-disclosure → higher score.
  0 = obvious clickbait / trend-chasing (e.g. "YOU WON'T BELIEVE WHAT HAPPENED!!!!")
  1 = authentic, consistent, genuine

CRITICAL — judge CONTEXT and FRAMING, not just the presence of words:
  • "How I learned to stop hating my body" → HIGH prosocial, LOW appearance_comparison
    (the FRAMING is healing/education, not comparison)
  • "My 30-day transformation: before vs. after" → HIGH appearance_comparison, moderate risk
  • "I disagree with the algorithm — here's why" → HIGH opinion_comparison (healthy!)
  • A cooking tutorial with beautiful food → NOT appearance comparison
  • "Storytime: I was in a toxic relationship" → moderate risk, potentially HIGH prosocial
    (if it educates about warning signs)

Respond with ONLY valid JSON — no explanation, no markdown, no extra text:
{{"appearance_comparison": 0.0, "opinion_comparison": 0.0, "prosocial": 0.0, "risk": 0.0, "creator_authenticity": 0.0}}
"""


def _classify_with_ollama(
    title: str,
    description: str,
    category: str,
    model: str,
) -> Optional[dict]:
    """
    Sends video metadata to the local Ollama model for psychological scoring.

    Uses /api/chat with think:false so that Qwen3/thinking models skip their
    chain-of-thought and return direct JSON instantly.  A regex safety net
    extracts the JSON object from any surrounding text the model might add.

    Returns a dict of 5 float scores, or None on failure.
    """
    prompt = _PROMPT_TEMPLATE.format(
        title=title[:300],
        description=(description or "")[:600],
        category=category,
    )

    # Use /api/chat endpoint — better for instruction-following + thinking models.
    # think:false disables the reasoning chain for Qwen3/DeepSeek-R1 family,
    # making classification ~5x faster without hurting output quality.
    payload = json.dumps({
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a JSON-only API. "
                    "Return ONLY a valid JSON object with no explanation, "
                    "no markdown, no extra text whatsoever."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "think":  False,            # disable reasoning chain (Qwen3 / R1 models)
        "format": "json",           # Ollama-level JSON enforcement
        "options": {"temperature": 0.1},
    }).encode()

    try:
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            result   = json.loads(resp.read())
            raw_text = result.get("message", {}).get("content", "")

            # --- Parse JSON from response ---
            # 1. Direct parse (happy path)
            scores = None
            try:
                scores = json.loads(raw_text)
            except json.JSONDecodeError:
                pass

            # 2. Regex extraction — handles any stray text/markdown around the JSON
            if scores is None:
                match = re.search(r"\{[^{}]*\}", raw_text, re.DOTALL)
                if match:
                    try:
                        scores = json.loads(match.group())
                    except json.JSONDecodeError:
                        pass

            if scores is None:
                print(f"[extractor] Could not parse JSON from response: {raw_text[:200]!r}")
                return None

            required = {
                "appearance_comparison", "opinion_comparison",
                "prosocial", "risk", "creator_authenticity",
            }
            if required.issubset(scores.keys()):
                return {k: float(np.clip(float(scores[k]), 0.0, 1.0)) for k in required}

            print(f"[extractor] Response missing expected keys: {set(scores.keys())}")

    except Exception as e:
        print(f"[extractor] Ollama classification error: {e}")

    return None


# ---------------------------------------------------------------------------
# Heuristic fallback (used when Ollama is unavailable)
# ---------------------------------------------------------------------------

_APPEARANCE_WORDS = [
    "transformation", "glow up", "before after", "before & after",
    "body", "weight loss", "diet", "skincare routine", "makeover",
    "rate my", "glow up", "fitness journey", "get unready with me",
    "outfits", "my look", "aesthetic", "hot or not",
]
_OPINION_WORDS = [
    "my opinion", "unpopular opinion", "i think", "let's talk",
    "honest thoughts", "controversial", "debate", "do i agree",
    "stop telling me", "why i don't", "change my mind",
]
_PROSOCIAL_WORDS = [
    "how to", "tutorial", "learn", "education", "mental health",
    "support", "together", "community", "kindness", "donate",
    "helping", "overcome", "recovery", "awareness", "study with me",
]
_RISK_WORDS = [
    "toxic", "hate", "shocking", "dangerous", "triggering",
    "you won't believe", "exposed", "drama", "gone wrong",
    "challenge gone", "extreme", "graphic", "disturbing",
]
# Negation context: if these appear near a scored word, reverse the score
_NEGATION_PREFIXES = ["overcoming", "recovering from", "stop", "no more", "healing"]


def _heuristic_score(text: str, word_list: list) -> float:
    """Score 0–1 based on keyword density, with basic negation awareness."""
    text = text.lower()
    hits = 0
    for w in word_list:
        if w in text:
            # Check if a negation prefix appears within 30 chars before the word
            idx = text.find(w)
            context = text[max(0, idx - 30): idx]
            if any(neg in context for neg in _NEGATION_PREFIXES):
                continue   # negated — skip
            hits += 1
    return float(np.clip(hits * 0.25, 0.0, 1.0))


def _classify_heuristic(title: str, description: str) -> dict:
    """
    Keyword-heuristic classifier used when Ollama is unavailable.
    Less contextually aware than the LLM but deterministic and instant.
    """
    text = (title + " " + (description or "")).lower()
    return {
        "appearance_comparison": _heuristic_score(text, _APPEARANCE_WORDS),
        "opinion_comparison":    _heuristic_score(text, _OPINION_WORDS),
        "prosocial":             _heuristic_score(text, _PROSOCIAL_WORDS),
        "risk":                  _heuristic_score(text, _RISK_WORDS),
        "creator_authenticity":  0.5,   # neutral default; LLM does better here
    }


# ---------------------------------------------------------------------------
# YouTube API helpers
# ---------------------------------------------------------------------------

def _yt_request(endpoint: str, params: dict) -> Optional[dict]:
    """Make a YouTube Data API v3 request. Returns parsed JSON or None."""
    params["key"] = YOUTUBE_API_KEY
    url = f"{YOUTUBE_API_BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url), timeout=10
        ) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"[extractor] YouTube API error: {e}")
        return None


def _fetch_stats_batch(
    video_ids: list[str],
    relevance_language: str = "en",
    region_code: str = "US",
) -> dict[str, dict]:
    """
    Fetch snippet + statistics + contentDetails for up to 50 video IDs in one call.
    Returns {video_id: {"snippet": {...}, "statistics": {...}, "contentDetails": {...}}}.
    contentDetails carries the ISO 8601 `duration`; snippet carries `tags` and
    `thumbnails` (no extra quota cost — these parts ride the same request).

    ``hl`` localizes returned metadata to the preferred language; ``regionCode``
    is forwarded for parity with the rest of the pipeline's locale targeting.
    """
    if not video_ids or not YOUTUBE_API_KEY:
        return {}

    data = _yt_request("videos", {
        "part": "snippet,statistics,contentDetails",
        "id": ",".join(video_ids[:50]),
        "hl": normalize_language_code(relevance_language),
        "regionCode": normalize_region_code(region_code),
    })

    result: dict[str, dict] = {}
    if data and "items" in data:
        for item in data["items"]:
            vid_id = item["id"]
            result[vid_id] = {
                "snippet":        item.get("snippet", {}),
                "statistics":     item.get("statistics", {}),
                "contentDetails": item.get("contentDetails", {}),
            }
    return result


# Preference order for picking a single thumbnail URL from snippet.thumbnails.
_THUMBNAIL_PREFERENCE = ("maxres", "standard", "high", "medium", "default")


def _best_thumbnail(snippet: dict) -> str:
    """Best available thumbnail URL from a snippet's `thumbnails` map ("" if none)."""
    thumbs = snippet.get("thumbnails") or {}
    for size in _THUMBNAIL_PREFERENCE:
        url = (thumbs.get(size) or {}).get("url")
        if url:
            return url
    return ""


def _fetch_ids_by_topic(
    topic: str,
    max_results: int = 15,
    relevance_language: str = "en",
    region_code: str = "US",
) -> list[str]:
    """Fetch most-popular video IDs for a given topic category.

    ``region_code`` targets the regional chart. ``relevance_language`` is used
    as ``hl`` so returned metadata can be localized when YouTube has it.
    """
    if not YOUTUBE_API_KEY:
        print(f"[extractor] No YOUTUBE_API_KEY — cannot fetch IDs for '{topic}'")
        return []

    cat_id = TOPIC_TO_CATEGORY.get(topic, "24")
    data = _yt_request("videos", {
        "part": "id",
        "chart": "mostPopular",
        "videoCategoryId": cat_id,
        "hl": normalize_language_code(relevance_language),
        "regionCode": normalize_region_code(region_code),
        "maxResults": str(max_results),
    })

    if data and "items" in data:
        ids = [item["id"] for item in data["items"]]
        print(f"[extractor] Fetched {len(ids)} IDs for topic '{topic}' (category {cat_id})")
        return ids

    print(f"[extractor] No results for topic '{topic}'")
    return []


def _compute_active_ratio(stats: dict) -> float:
    """
    Normalized active engagement ratio.
    (likes + comments) / views, scaled so that a typical active ratio (~0.03-0.10)
    maps to mid-range 0.3-1.0 on our 0–1 scale.
    """
    views    = int(stats.get("viewCount",    0) or 0)
    likes    = int(stats.get("likeCount",    0) or 0)
    comments = int(stats.get("commentCount", 0) or 0)
    if views == 0:
        return 0.0
    raw = (likes + comments) / views   # typically 0.01 – 0.15
    return float(np.clip(raw * 10, 0.0, 1.0))   # scale ×10, cap at 1


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def extract_and_classify(
    topics: Optional[list[str]] = None,
    video_ids: Optional[list[str]] = None,
    max_per_topic: int = 15,
    db_path: Path = DB_PATH,
) -> pd.DataFrame:
    """
    Full pipeline entry point.

    Parameters
    ----------
    topics       : List of Chrysalis topic names to fetch from YouTube's
                   mostPopular chart (e.g. ["gaming", "music"]).
    video_ids    : Specific YouTube video IDs to fetch and classify.
    max_per_topic: Max videos to fetch per topic (default 15, max 50).
    db_path      : Path to the SQLite database (created if not exists).

    Returns
    -------
    pandas DataFrame with all algorithm-required columns, ready for
    validate_and_clean() and build_prototype_feed().
    """
    conn = _get_conn(db_path)

    # --- Detect Ollama ---
    model = _detect_ollama_model()
    if model:
        print(f"[extractor] Ollama model: {model}  (context-aware AI scoring)")
    else:
        print("[extractor] Ollama unavailable — using keyword heuristics fallback")

    # --- Collect all target video IDs ---
    ids_to_process: list[str] = list(video_ids or [])
    topics_requested = bool(topics)   # track whether caller explicitly asked for topics

    if topics:
        for topic in topics:
            ids_to_process += _fetch_ids_by_topic(topic, max_per_topic)

    if not ids_to_process and not topics_requested:
        # No topics or IDs at all — default: fetch across all topics
        print("[extractor] No topics or IDs specified — fetching all topics")
        for topic in ALL_TOPICS:
            ids_to_process += _fetch_ids_by_topic(topic, max_per_topic)
    elif not ids_to_process and topics_requested:
        # Topics were given but all returned empty (e.g. category not available)
        print("[extractor] No videos found for requested topic(s). Exiting.")
        conn.close()
        return pd.DataFrame()

    # Deduplicate while preserving order
    seen: set[str] = set()
    ids_to_process = [i for i in ids_to_process if not (i in seen or seen.add(i))]

    # --- Check SQLite cache ---
    cached_ids: set[str] = set()
    if ids_to_process:
        placeholders = ",".join("?" * len(ids_to_process))
        rows = conn.execute(
            f"SELECT video_id FROM videos WHERE video_id IN ({placeholders})",
            ids_to_process,
        ).fetchall()
        cached_ids = {r["video_id"] for r in rows}

    new_ids = [i for i in ids_to_process if i not in cached_ids]
    print(
        f"[extractor] {len(cached_ids)} already cached · "
        f"{len(new_ids)} new to fetch+classify"
    )

    # --- Fetch + classify new videos in batches of 50 ---
    BATCH_SIZE = 50
    for batch_start in range(0, len(new_ids), BATCH_SIZE):
        batch     = new_ids[batch_start : batch_start + BATCH_SIZE]
        stats_map = _fetch_stats_batch(batch)

        for vid_id in batch:
            info = stats_map.get(vid_id)
            if not info:
                print(f"  ✗ {vid_id} — no data returned from YouTube API")
                continue

            snip   = info["snippet"]
            stats  = info["statistics"]
            details = info.get("contentDetails", {})

            title        = snip.get("title", "")
            description  = snip.get("description", "")
            channel_id   = snip.get("channelId", "")
            channel_title= snip.get("channelTitle", "")
            category_id  = snip.get("categoryId", "24")
            published_at = snip.get("publishedAt", "")
            topic        = CATEGORY_TO_TOPIC.get(category_id, "entertainment")

            tags             = snip.get("tags", []) or []
            thumbnail_url    = _best_thumbnail(snip)
            duration_seconds = parse_duration_seconds(details.get("duration"))

            view_count    = int(stats.get("viewCount",    0) or 0)
            like_count    = int(stats.get("likeCount",    0) or 0)
            comment_count = int(stats.get("commentCount", 0) or 0)
            active_ratio  = _compute_active_ratio(stats)

            # Classify with Ollama (best) or heuristics (fallback)
            if model:
                scores = _classify_with_ollama(title, description, topic, model)
                if scores is None:
                    print(f"  ⚠ Ollama failed for '{title[:50]}' — using heuristics")
                    scores = _classify_heuristic(title, description)
            else:
                scores = _classify_heuristic(title, description)

            conn.execute(
                """
                INSERT OR REPLACE INTO videos (
                    video_id, title, description, channel_id, channel_title,
                    topic, category_id, tags, duration_seconds, thumbnail_url,
                    view_count, like_count, comment_count,
                    published_at, active_engagement_ratio,
                    appearance_comparison, opinion_comparison, prosocial, risk,
                    creator_authenticity, fetched_at, classified_at
                ) VALUES (
                    ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                )
                """,
                (
                    vid_id, title, description,
                    channel_id, channel_title,
                    topic, category_id,
                    json.dumps(tags), duration_seconds, thumbnail_url,
                    view_count, like_count, comment_count,
                    published_at,
                    active_ratio,
                    scores["appearance_comparison"],
                    scores["opinion_comparison"],
                    scores["prosocial"],
                    scores["risk"],
                    scores["creator_authenticity"],
                    time.time(), time.time(),
                ),
            )
            print(f"  ✓ [{topic:13}] {title[:65]}")

        conn.commit()

    # --- Load all requested videos from DB into a DataFrame ---
    if ids_to_process:
        placeholders = ",".join("?" * len(ids_to_process))
        rows = conn.execute(
            f"SELECT * FROM videos WHERE video_id IN ({placeholders})",
            ids_to_process,
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM videos").fetchall()

    conn.close()

    if not rows:
        print("[extractor] No videos in database.")
        return pd.DataFrame()

    df = pd.DataFrame([dict(r) for r in rows])

    # --- Rename / add columns to match algorithm schema ---
    df = df.rename(columns={"channel_id": "channel"})

    # creator_trait: YouTube doesn't expose demographics, so we derive a
    # plausible trait from channel_title heuristics (can be overridden by UCRS)
    df["creator_trait"] = df["channel_title"].apply(_infer_creator_trait)

    print(f"\n[extractor] Done — {len(df)} videos ready for the algorithm.")
    return df


def _infer_creator_trait(channel_title: str) -> str:
    """
    Heuristic guess of creator_trait for UCRS affinity matching.
    In production this would come from channel analytics or user preference.
    """
    title = (channel_title or "").lower()
    if any(w in title for w in ["news", "global", "world", "international"]):
        return "international"
    if any(w in title for w in ["city", "urban", "street", "nyc", "la", "london"]):
        return "urban"
    if any(w in title for w in ["country", "farm", "rural", "homestead", "outdoor"]):
        return "rural"
    return "casual"   # default


# ---------------------------------------------------------------------------
# Database utilities
# ---------------------------------------------------------------------------

def db_summary(db_path: Path = DB_PATH) -> None:
    """Print a quick summary of the current database contents."""
    if not db_path.exists():
        print("No database found yet.")
        return
    conn = _get_conn(db_path)
    total = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
    print(f"\n{'='*50}")
    print(f"  chrysalis.db  —  {total} videos total")
    print(f"{'='*50}")
    rows = conn.execute(
        "SELECT topic, COUNT(*) as n FROM videos GROUP BY topic ORDER BY n DESC"
    ).fetchall()
    for r in rows:
        print(f"  {r['topic']:15} {r['n']:>5} videos")
    avg = conn.execute(
        "SELECT AVG(active_engagement_ratio), AVG(prosocial), "
        "AVG(risk), AVG(appearance_comparison), AVG(creator_authenticity) "
        "FROM videos"
    ).fetchone()
    print(f"\n  Avg active_engagement_ratio : {avg[0]:.3f}")
    print(f"  Avg prosocial               : {avg[1]:.3f}")
    print(f"  Avg risk                    : {avg[2]:.3f}")
    print(f"  Avg appearance_comparison   : {avg[3]:.3f}")
    print(f"  Avg creator_authenticity    : {avg[4]:.3f}")
    print(f"{'='*50}\n")
    conn.close()


def load_from_db(
    topics: Optional[list[str]] = None,
    db_path: Path = DB_PATH,
) -> pd.DataFrame:
    """
    Load already-classified videos from the SQLite database without
    hitting any APIs. Useful for offline testing / demos.
    """
    if not db_path.exists():
        print("[extractor] Database not found. Run extract_and_classify() first.")
        return pd.DataFrame()

    conn = _get_conn(db_path)
    if topics:
        placeholders = ",".join("?" * len(topics))
        rows = conn.execute(
            f"SELECT * FROM videos WHERE topic IN ({placeholders})", topics
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM videos").fetchall()
    conn.close()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame([dict(r) for r in rows])
    df = df.rename(columns={"channel_id": "channel"})
    df["creator_trait"] = df["channel_title"].apply(_infer_creator_trait)
    return df


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Chrysalis YouTube Extractor — fetch and AI-classify videos"
    )
    parser.add_argument(
        "--topics", nargs="+", default=None,
        help=f"Topics to fetch. Available: {ALL_TOPICS}"
    )
    parser.add_argument(
        "--ids", nargs="+", default=None,
        help="Specific YouTube video IDs to classify"
    )
    parser.add_argument(
        "--max", type=int, default=15,
        help="Max videos per topic (default 15, max 50)"
    )
    parser.add_argument(
        "--summary", action="store_true",
        help="Print database summary and exit"
    )
    args = parser.parse_args()

    if args.summary:
        db_summary()
    else:
        df = extract_and_classify(
            topics=args.topics,
            video_ids=args.ids,
            max_per_topic=args.max,
        )
        if not df.empty:
            db_summary()
            print("Sample output (first 3 rows):")
            print(df[[
                "title", "topic", "active_engagement_ratio",
                "prosocial", "risk", "appearance_comparison",
                "opinion_comparison", "creator_authenticity"
            ]].head(3).to_string(index=False))
