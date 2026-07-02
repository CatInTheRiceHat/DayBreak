"""
YouTube Data API v3 Service for Chrysalis
Fetches real, embeddable video IDs by topic category.
Uses in-memory caching to minimize quota usage.
"""

import os
import json
import time
import urllib.request
import urllib.error
from pathlib import Path

from core.preferences import normalize_language_code, normalize_region_code

# Load .env file manually (zero dependencies)
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"

# Map Chrysalis topics to YouTube video category IDs
# See: https://developers.google.com/youtube/v3/docs/videoCategories/list
TOPIC_TO_CATEGORY_ID = {
    "entertainment": "24",  # Entertainment
    "education": "27",      # Education
    "lifestyle": "26",      # Howto & Style
    "news": "25",           # News & Politics
    "gaming": "20",         # Gaming
    "music": "10",          # Music
    "sports": "17",         # Sports
}

# Placeholder fallback IDs used when the API is unavailable
_FALLBACK_IDS = ["dQw4w9WgXcQ", "9bZkp7q19f0", "kJQP7kiw5Fk"]
FALLBACK_IDS = {topic: _FALLBACK_IDS for topic in (
    "entertainment", "education", "lifestyle", "news", "gaming", "music", "sports"
)}

# In-memory cache: { (topic, language, region): { "ids": [...], "fetched_at": timestamp } }
_cache = {}
CACHE_TTL_SECONDS = 4 * 60 * 60  # 4 hours


def _api_request(endpoint: str, params: dict) -> dict | None:
    """Make a YouTube Data API request. Returns parsed JSON or None on error."""
    params["key"] = YOUTUBE_API_KEY
    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{YOUTUBE_API_BASE}/{endpoint}?{query_string}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
        print(f"[youtube_service] API error: {e}")
        return None


def fetch_videos_by_topic(
    topic: str,
    max_results: int = 12,
    relevance_language: str = "en",
    region_code: str = "US",
) -> list[str]:
    """
    Fetch real YouTube video IDs for a given Chrysalis topic.
    Uses mostPopular chart filtered by category (costs 1 quota unit).
    Results are cached for CACHE_TTL_SECONDS, keyed by topic + language + region.

    ``region_code`` targets the regional chart. ``relevance_language`` is used
    as ``hl`` so returned metadata can be localized when YouTube has it.

    Returns a list of video ID strings.
    """
    topic = topic.lower()
    relevance_language = normalize_language_code(relevance_language)
    region_code = normalize_region_code(region_code)
    cache_key = (topic, relevance_language, region_code)

    # Check cache
    if cache_key in _cache:
        entry = _cache[cache_key]
        age = time.time() - entry["fetched_at"]
        if age < CACHE_TTL_SECONDS and entry["ids"]:
            return entry["ids"]

    # No API key? Use fallbacks
    if not YOUTUBE_API_KEY:
        print("[youtube_service] No YOUTUBE_API_KEY set. Using fallback IDs.")
        return FALLBACK_IDS.get(topic, FALLBACK_IDS["entertainment"])

    category_id = TOPIC_TO_CATEGORY_ID.get(topic, "24")  # default to entertainment

    data = _api_request("videos", {
        "part": "id,snippet",
        "chart": "mostPopular",
        "videoCategoryId": category_id,
        "hl": relevance_language,
        "regionCode": region_code,
        "maxResults": str(max_results),
    })

    if data and "items" in data:
        ids = [item["id"] for item in data["items"]]
        # Cache the results
        _cache[cache_key] = {
            "ids": ids,
            "fetched_at": time.time(),
        }
        print(f"[youtube_service] Fetched {len(ids)} videos for '{topic}' (category {category_id}, lang {relevance_language}, region {region_code})")
        return ids

    # API failed — use fallbacks
    print(f"[youtube_service] API call failed for topic '{topic}'. Using fallbacks.")
    return FALLBACK_IDS.get(topic, FALLBACK_IDS["entertainment"])


def get_youtube_id_for_video(topic: str, seed: str) -> str:
    """
    Get a single YouTube video ID for a given topic.
    Uses the seed string (e.g., the algorithm's video_id) to deterministically 
    pick from the cached list, so re-renders are consistent.
    """
    ids = fetch_videos_by_topic(topic)
    if not ids:
        return "dQw4w9WgXcQ"  # ultimate fallback
    
    # Deterministic selection based on seed
    hash_val = 0
    for ch in str(seed):
        hash_val = ord(ch) + ((hash_val << 5) - hash_val)
    
    return ids[abs(hash_val) % len(ids)]


def get_all_topics_cache_status() -> dict:
    """Return info about what's currently cached (for debugging).

    Default en/US entries keep the old topic-only shape; other locale entries
    are surfaced as "topic@lang/region" so the same topic can appear per locale.
    """
    status = {
        topic: {"count": 0, "age_minutes": None, "fresh": False}
        for topic in TOPIC_TO_CATEGORY_ID
    }
    for cache_key, entry in _cache.items():
        topic, language, region = cache_key
        age = time.time() - entry["fetched_at"]
        label = topic if (language, region) == ("en", "US") else f"{topic}@{language}/{region}"
        status[label] = {
            "count": len(entry["ids"]),
            "age_minutes": round(age / 60, 1),
            "fresh": age < CACHE_TTL_SECONDS,
        }
    return status
