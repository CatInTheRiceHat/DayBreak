"""Tests for the English-only / US-focused demo feed policy + cleanup script."""

import sqlite3
import tempfile

from core.language_filter import (
    ALLOWED_LANGUAGE_PREFIXES,
    ALLOWED_REGION,
    LANGUAGE_POLICY,
    detect_block_reason,
    is_allowed,
    is_blocked_language_code,
    is_region_blocked,
    verdict,
)
from core.ranking.feed import build_feed_payload
from integrations.youtube_ingest import ensure_sqlite_feed_videos_table
from scripts.block_non_english_videos import run as cleanup_run


# ── policy constants ──────────────────────────────────────────────────────────

def test_policy_constants():
    assert LANGUAGE_POLICY == "english_only_us_demo"
    assert list(ALLOWED_LANGUAGE_PREFIXES) == ["en"]
    assert ALLOWED_REGION == "US"


def test_language_code_allowlist():
    assert not is_blocked_language_code("en")
    assert not is_blocked_language_code("en-US")
    assert not is_blocked_language_code("")          # absent is not "blocked"
    for code in ("hi", "ar", "zh", "ja", "ko", "ru", "es-419", "fr"):
        assert is_blocked_language_code(code), code


# ── allowed English / US-focused content ─────────────────────────────────────

def test_plain_english_allowed():
    assert is_allowed({"title": "A calm 5-minute morning walk", "description": "fresh air reset"})


def test_english_with_country_emoji_or_one_foreign_word_not_overblocked():
    assert is_allowed({"title": "What mornings look like in Japan and India"})  # country mention
    assert is_allowed({"title": "Sunny day vibes ☀️🦋 lets go"})               # emojis
    assert is_allowed({"title": "My recipe — gracias for watching!"})           # one latin foreign word
    assert is_allowed({"title": "Daily gratitude (आभार) practice", "description": "a long english description follows here for context"})


def test_english_audio_code_allowed():
    assert is_allowed({"title": "Morning yoga", "default_audio_language": "en-US"})


# ── transliterated (Latin-script) non-English content blocked ────────────────
# These slip past code/script/region checks because the metadata is romanized,
# but the terms themselves only ever describe non-English (Indian-subcontinent)
# content. See the "Hindi videos still leaking" investigation.

def test_transliterated_terms_in_title_blocked():
    for title in (
        "Hanuman Chalisa | Powerful Bhajan",
        "Best Bhakti Songs Jukebox",
        "Heart touching Shayari",
        "Morning Kirtan live",
        "New WhatsApp Status 2026",
    ):
        assert not is_allowed({"title": title}), title
        assert detect_block_reason({"title": title}) == "language_name", title


def test_long_non_latin_run_blocked_even_at_low_ratio():
    # A mostly-English description with a full foreign-script sentence (>= the hard
    # absolute cap) is non-English even though English text dilutes the ratio.
    row = {
        "title": "Amazing video you must watch today nice wow great",
        "description": "Please subscribe for more " + ("video " * 80)
        + " सुबह की सैर और ध्यान करें रोज सुबह जल्दी उठकर टहलें",
    }
    assert not is_allowed(row)
    assert detect_block_reason(row) == "script"


def test_new_rules_do_not_overblock_english():
    # Wellness vocabulary and generic phrasing that merely *contains* a substring
    # must stay allowed (no false positives from the strengthened rules).
    assert is_allowed({"title": "Morning mantra for a calm mind"})
    assert is_allowed({"title": "5 minute guided meditation for sleep"})
    assert is_allowed({"title": "Weekly project status video update"})  # not "whatsapp status"
    assert is_allowed({"title": "Aarav's productive morning routine"})  # a name, not a term


# ── blocked non-English scripts ──────────────────────────────────────────────

def test_non_english_scripts_blocked():
    samples = {
        "hindi": "सुबह की सैर और ध्यान",
        "arabic": "تمارين الصباح للاسترخاء",
        "chinese": "每天早晨的放松冥想练习",
        "japanese": "朝の瞑想ルーティン",
        "korean": "아침 명상 루틴 따라하기",
        "cyrillic": "утренняя медитация для спокойствия",
        "hebrew": "מדיטציה בוקר להרגעה",
        "thai": "การทำสมาธิยามเช้า",
        "tamil": "காலை நடைப்பயிற்சி தியானம்",
        "bengali": "সকালের ধ্যান অনুশীলন",
    }
    for name, title in samples.items():
        assert detect_block_reason({"title": title}) == "script", name


def test_non_english_code_and_name_blocked():
    assert detect_block_reason({"title": "Morning yoga", "default_audio_language": "es"}) == "language_code"
    assert detect_block_reason({"title": "Top songs", "source_query": "best hindi songs"}) == "language_name"
    assert detect_block_reason({"title": "Learn Spanish fast", "source_query": "spanish lessons"}) == "language_name"


def test_non_us_region_blocked():
    assert is_region_blocked({"region_code": "IN"})
    assert not is_region_blocked({"region_code": "US"})
    assert not is_region_blocked({})


def test_verdict_shape():
    assert verdict({"title": "Morning", "default_audio_language": "hi"}) == {
        "allowed": False, "language_reason": "language_code", "region_blocked": False,
    }


# ── feed-level enforcement ───────────────────────────────────────────────────

def _en_row(i, *, category, title, description, tags):
    return {
        "video_id": f"en-{category}-{i}", "title": title, "description": description,
        "channel_title": f"Channel {i}", "source_category": category,
        "source_query": f"{category} seed", "duration_seconds": 72,
        "view_count": 12000, "tags": tags, "integrity_score": 0.78,
    }


def _mixed_rows():
    rows = []
    for i in range(8):
        rows.append(_en_row(i, category="wellness",
                            title=f"Calm journaling walk reset {i}",
                            description="A gentle self care reminder to journal, drink water, stretch, and walk outside.",
                            tags=["journal", "walk", "calm"]))
    for i in range(6):
        rows.append(_en_row(i, category="comedy",
                            title=f"Funny harmless short {i}",
                            description="A normal low-risk comedy clip with ordinary jokes and trends.",
                            tags=["comedy", "fun"]))
    for i in range(3):
        rows.append(_en_row(i, category="perspectives",
                            title=f"Two people share different perspectives {i}",
                            description="A calm respectful conversation, open mind, common ground.",
                            tags=["different perspectives", "open minded"]))
    # non-English rows (script, code, name) + non-US region + a pre-blocked row
    rows.append({"video_id": "hi-1", "title": "सुबह की सैर", "source_category": "wellness"})
    rows.append({"video_id": "zh-1", "title": "每天早晨的冥想", "source_category": "wellness"})
    rows.append({"video_id": "ar-1", "title": "تمارين الصباح", "source_category": "wellness"})
    rows.append({"video_id": "es-1", "title": "Rutina de la mañana", "default_audio_language": "es", "source_category": "wellness"})
    rows.append({"video_id": "in-1", "title": "Calm walk", "region_code": "IN", "source_category": "wellness"})
    rows.append({"video_id": "blk-1", "title": "Calm walk", "status": "blocked", "source_category": "wellness"})
    return rows


def test_feed_excludes_all_non_english_and_blocked_rows():
    payload = build_feed_payload(_mixed_rows(), "flutter-feed", k=12, shuffle_seed="lang-qa")
    ids = {item["youtube_id"] for item in payload["items"]}
    assert not (ids & {"hi-1", "zh-1", "ar-1", "es-1", "in-1", "blk-1"})


def test_feed_still_fills_after_filtering():
    payload = build_feed_payload(_mixed_rows(), "flutter-feed", k=12, shuffle_seed="lang-qa")
    assert payload["count"] == 12


def test_feed_debug_language_fields():
    debug = build_feed_payload(_mixed_rows(), "flutter-feed", k=12, shuffle_seed="lang-qa")["debug"]
    assert debug["language_policy"] == "english_only_us_demo"
    assert debug["allowed_language_prefixes"] == ["en"]
    assert debug["allowed_region"] == "US"
    assert debug["language_filtered_count"] >= 4         # hi, zh, ar, es
    assert debug["region_or_origin_filtered_count"] >= 1  # in-1
    assert debug["blocked_or_deleted_count"] >= 1         # blk-1 (status='blocked')


def test_healthy_ratio_still_holds():
    payload = build_feed_payload(_mixed_rows(), "flutter-feed", k=12, shuffle_seed="lang-qa")
    assert 0.4 <= payload["healthy_content_ratio"] <= 0.6


# ── cleanup script (sqlite) ──────────────────────────────────────────────────

def _seed_cleanup_db():
    db = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(db)
    ensure_sqlite_feed_videos_table(conn)
    conn.execute(
        "INSERT INTO feed_videos (id, youtube_video_id, title, status) VALUES "
        "('a','en-ok','A calm English walk','active'),"
        "('b','hi-bad','सुबह की सैर','active'),"
        "('c','zh-bad','每天早晨的冥想','active')"
    )
    conn.commit()
    conn.close()
    return db


def test_cleanup_dry_run_changes_nothing():
    db = _seed_cleanup_db()
    result = cleanup_run(backend="sqlite", db_path=db, database_url=None, delete=False, dry_run=True)
    assert result["matched"] == 2 and result["blocked"] == 0 and result["deleted"] == 0
    conn = sqlite3.connect(db)
    active = conn.execute("SELECT COUNT(*) FROM feed_videos WHERE status='active'").fetchone()[0]
    conn.close()
    assert active == 3  # untouched


def test_cleanup_block_mode_marks_rows():
    db = _seed_cleanup_db()
    result = cleanup_run(backend="sqlite", db_path=db, database_url=None, delete=False, dry_run=False)
    assert result["blocked"] == 2 and result["deleted"] == 0
    conn = sqlite3.connect(db)
    blocked = conn.execute("SELECT youtube_video_id, safety_reason FROM feed_videos WHERE status='blocked'").fetchall()
    rows_left = conn.execute("SELECT COUNT(*) FROM feed_videos").fetchone()[0]
    conn.close()
    assert {b[0] for b in blocked} == {"hi-bad", "zh-bad"}
    assert all("english_only_us_demo" in (b[1] or "") for b in blocked)
    assert rows_left == 3  # blocked, not deleted


def test_cleanup_delete_mode_backs_up_and_deletes():
    db = _seed_cleanup_db()
    result = cleanup_run(backend="sqlite", db_path=db, database_url=None, delete=True, dry_run=False)
    assert result["deleted"] == 2 and result["backup_table"] and result["rollback_sql"]
    conn = sqlite3.connect(db)
    remaining = {r[0] for r in conn.execute("SELECT youtube_video_id FROM feed_videos").fetchall()}
    backup_count = conn.execute(f"SELECT COUNT(*) FROM {result['backup_table']}").fetchone()[0]
    conn.close()
    assert remaining == {"en-ok"}      # bad rows gone
    assert backup_count == 2           # backed up before delete


def test_cleanup_default_never_deletes():
    # Without delete=True nothing is hard-deleted (block mode keeps the rows).
    db = _seed_cleanup_db()
    cleanup_run(backend="sqlite", db_path=db, database_url=None, delete=False, dry_run=False)
    conn = sqlite3.connect(db)
    total = conn.execute("SELECT COUNT(*) FROM feed_videos").fetchone()[0]
    conn.close()
    assert total == 3
