"""
Single source of truth for the demo's English-only, US-focused feed policy.

Scope note: this is a *demo / current-feed* decision, not a permanent global
product stance. Multilingual / international support can return later by relaxing
the constants below — every enforcement point (ingestion, feed read, cleanup
script) imports from here, so there is one place to change.

Honesty about origin (see requirement 12): the `feed_videos` schema has no
reliable language/region/country column, so we cannot perfectly identify a
creator's country. "US-focused demo eligibility" is therefore approximated with:
  • YouTube ingestion pinned to regionCode=US / relevanceLanguage=en,
  • English metadata checks (explicit language fields + script analysis),
  • source query / category checks,
  • backend feed filtering.
This reliably removes clearly-foreign content; it does not claim to verify that
every remaining creator is physically in the US.

A video is filtered when ANY of these hold:
  • an explicit language field is present and its primary subtag is not English,
  • title/description/channel/tags are substantially in a non-Latin script
    (Devanagari, Arabic, CJK, Cyrillic, Hebrew, Thai, Bengali, Gurmukhi,
    Gujarati, Tamil, Telugu, Kannada, Malayalam, Sinhala, …),
  • the text or source query clearly names/targets a non-English language,
  • a 2-letter region/country field is present and is not the allowed region.
"""

from __future__ import annotations

import re

# ── Policy constants (the one place to relax for multilingual support) ────────
LANGUAGE_POLICY = "english_only_us_demo"
ALLOWED_LANGUAGE_PREFIXES: tuple[str, ...] = ("en",)
ALLOWED_REGION = "US"
# Representative non-English codes, surfaced in debug output (the live rule is the
# allow-list above, not this list).
BLOCKED_LANGUAGE_CODES: tuple[str, ...] = (
    "hi", "ar", "zh", "ja", "ko", "ru", "he", "th", "bn", "pa", "gu",
    "ta", "te", "kn", "ml", "si", "es", "fr", "pt", "de", "ur", "fa",
)

# Fraction of letters that may be non-Latin before a field reads as non-English.
# A small foreign snippet inside otherwise-English text stays allowed (req 9).
_NON_LATIN_RATIO = 0.30
# …but a large ABSOLUTE amount of non-Latin script is non-English even when English
# brand terms / hashtags dilute the ratio (e.g. a long Hindi description that names
# "India AI Impact Summit 2026"). A genuine English video never carries this many
# foreign letters; one quoted foreign word (a few chars) stays well under it.
_NON_LATIN_ABS_MIN = 15
_NON_LATIN_ABS_RATIO = 0.12
# A long unbroken amount of non-Latin script is non-English regardless of ratio:
# a mostly-English description that still quotes a whole foreign sentence is not an
# English video. One romanized/quoted word stays well under this (a single
# Devanagari word ≈ 3–6 letters), so genuine English content is unaffected.
_NON_LATIN_HARD_MIN = 20

# Non-Latin script ranges that indicate non-English content.
_NON_LATIN_SCRIPT = re.compile(
    "["
    "ऀ-ॿ"          # Devanagari (Hindi, Marathi, …)
    "ঀ-৿"          # Bengali
    "਀-੿"          # Gurmukhi (Punjabi)
    "઀-૿"          # Gujarati
    "ఀ-౿"          # Telugu
    "ಀ-೿"          # Kannada
    "ഀ-ൿ"          # Malayalam
    "஀-௿"          # Tamil
    "඀-෿"          # Sinhala
    "ก-๿"          # Thai
    "؀-ۿ"          # Arabic
    "ݐ-ݿ"          # Arabic Supplement
    "ࢠ-ࣿ"          # Arabic Extended-A
    "ﭐ-﷿"          # Arabic Presentation Forms-A
    "ﹰ-﻿"          # Arabic Presentation Forms-B
    "֐-׿"          # Hebrew
    "Ѐ-ӿ"          # Cyrillic
    "Ⰰ-ⳏ"          # Glagolitic/Cyrillic ext (defensive)
    "一-鿿"          # CJK Unified Ideographs (Chinese/Japanese Kanji)
    "぀-ゟ"          # Hiragana (Japanese)
    "゠-ヿ"          # Katakana (Japanese)
    "가-힯"          # Hangul Syllables (Korean)
    "ᄀ-ᇿ"          # Hangul Jamo
    "]"
)

_LATIN_LETTER = re.compile("[A-Za-z]")

# Non-English language NAMES. Two tiers, because some names double as English
# culture/style adjectives ("Korean fashion", "Thai food", "Italian recipe"):
#   STRONG — names that, in a TITLE, almost always mean the content itself is in
#            that language (Indian-subcontinent + a few language-only terms). Safe
#            to match in titles + our own source query/category.
#   WEAK   — ambiguous culture adjectives. Only matched in source_query /
#            source_category (our ingestion intent), never in a title, so an
#            English "Korean fashion lookbook" is NOT blocked (req 9).
_STRONG_LANGUAGE_NAMES: tuple[str, ...] = (
    "hindi", "telugu", "tamil", "kannada", "malayalam", "bengali", "punjabi",
    "gujarati", "marathi", "urdu", "sinhala", "nepali", "sanskrit",
    "sub indo", "en espanol", "en español", "in hindi", "dubbed in",
    # Romanized (Latin-script) terms that only ever describe non-English,
    # Indian-subcontinent content — they slip past the script/code/region checks
    # because the metadata itself is in English letters. Kept high-precision:
    # each almost never appears in genuine English titles. ("status video" is
    # intentionally excluded as too generic; only "whatsapp status" qualifies.)
    "bhajan", "bhajans", "bhakti", "chalisa", "kirtan", "satsang",
    "pravachan", "qawwali", "shayari", "whatsapp status",
)
_WEAK_LANGUAGE_NAMES: tuple[str, ...] = (
    "arabic", "mandarin", "cantonese", "chinese", "japanese", "korean", "russian",
    "hebrew", "thai", "farsi", "persian", "spanish", "espanol", "español",
    "french", "francais", "français", "portuguese", "german", "italian",
    "vietnamese", "indonesian", "turkish",
)
# Kept as a union for debug / back-compat.
BLOCKED_LANGUAGE_NAMES: tuple[str, ...] = _STRONG_LANGUAGE_NAMES + _WEAK_LANGUAGE_NAMES


def _name_re(names):
    return re.compile(r"(?<![a-z])(" + "|".join(re.escape(n) for n in names) + r")(?![a-z])", re.IGNORECASE)


_STRONG_NAME_RE = _name_re(_STRONG_LANGUAGE_NAMES)
_INTENT_NAME_RE = _name_re(BLOCKED_LANGUAGE_NAMES)  # strong + weak, for source query/category

_LANGUAGE_FIELDS = (
    "default_audio_language", "default_language", "defaultAudioLanguage",
    "defaultLanguage", "language", "audio_language", "relevance_language",
    "caption_language", "transcript_language",
)
_REGION_FIELDS = ("region_code", "regionCode", "country", "country_code")
_TEXT_FIELDS = ("title", "description", "short_description", "channel_title", "channel", "display_title", "display_channel")
_QUERY_FIELDS = ("source_query", "source_category", "display_hashtags")


def _norm(value) -> str:
    return str(value or "").strip().lower()


def _is_english_code(value) -> bool:
    code = _norm(value)
    if not code:
        return False
    primary = code.replace("_", "-").split("-")[0]
    return primary in ALLOWED_LANGUAGE_PREFIXES


def is_blocked_language_code(value) -> bool:
    """True if a present language code is non-English (e.g. hi, ar, zh, es, fr)."""
    code = _norm(value)
    if not code:
        return False
    return not _is_english_code(code)


def _text_of(row: dict, fields) -> str:
    parts = []
    for field in fields:
        value = row.get(field)
        if isinstance(value, (list, tuple)):
            parts.append(" ".join(str(v) for v in value))
        elif value:
            parts.append(str(value))
    tags = row.get("tags")
    if "tags" in fields or fields is _TEXT_FIELDS:
        if isinstance(tags, (list, tuple)):
            parts.append(" ".join(str(t) for t in tags))
        elif tags:
            parts.append(str(tags))
    return " ".join(parts)


def _non_latin_ratio(text: str) -> float:
    foreign = len(_NON_LATIN_SCRIPT.findall(text))
    latin = len(_LATIN_LETTER.findall(text))
    total = foreign + latin
    return foreign / total if total else 0.0


def _script_heavy(text: str) -> bool:
    """True if the text is substantially non-Latin (by ratio, or by a large
    absolute amount of non-Latin script that English brand terms have diluted)."""
    foreign = len(_NON_LATIN_SCRIPT.findall(text))
    latin = len(_LATIN_LETTER.findall(text))
    total = foreign + latin
    if not total:
        return False
    ratio = foreign / total
    return (
        foreign >= _NON_LATIN_HARD_MIN
        or ratio >= _NON_LATIN_RATIO
        or (foreign >= _NON_LATIN_ABS_MIN and ratio >= _NON_LATIN_ABS_RATIO)
    )


def detect_block_reason(row: dict) -> str | None:
    """Return a non-English block reason, or None if the row reads as English."""
    # 1) explicit language field that isn't English
    for field in _LANGUAGE_FIELDS:
        if row.get(field) and is_blocked_language_code(row.get(field)):
            return "language_code"

    # 2) substantial non-Latin script in the title, or across the metadata
    title = str(row.get("title") or row.get("display_title") or "")
    combined = _text_of(row, _TEXT_FIELDS)
    if _script_heavy(title) or _script_heavy(combined):
        return "script"

    # 3) language-name targeting. Strong names (e.g. "explained in Telugu") block
    #    from the title; ambiguous culture adjectives (Korean/Thai/Italian…) only
    #    block from our own source query/category, never the title — so an English
    #    "Korean fashion lookbook" or a news clip tagged "#russian" stays (req 9).
    title_text = " ".join([str(row.get("title") or ""), str(row.get("display_title") or "")])
    intent_text = " ".join([str(row.get("source_query") or ""), str(row.get("source_category") or "")])
    if _STRONG_NAME_RE.search(title_text) or _INTENT_NAME_RE.search(intent_text):
        return "language_name"

    return None


def is_region_blocked(row: dict) -> bool:
    """True if a 2-letter region/country field is present and is not the allowed region."""
    for field in _REGION_FIELDS:
        value = _norm(row.get(field))
        if len(value) == 2 and value.upper() != ALLOWED_REGION:
            return True
    return False


def verdict(row: dict) -> dict:
    """Full decision for one row: {allowed, language_reason, region_blocked}."""
    language_reason = detect_block_reason(row)
    region_blocked = is_region_blocked(row)
    return {
        "allowed": language_reason is None and not region_blocked,
        "language_reason": language_reason,
        "region_blocked": region_blocked,
    }


def is_allowed(row: dict) -> bool:
    """True if the row passes the English-only / US-focused demo policy."""
    return verdict(row)["allowed"]
