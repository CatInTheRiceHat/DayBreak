-- Migration 009 - User content preferences (language + region targeting)
--
-- Lightweight, privacy-respecting per-user/session preferences that let the
-- backend target YouTube searches by language and approximate region. We only
-- store a coarse region/language, never exact GPS coordinates. Anonymous users
-- are tracked via a frontend-generated session_id; logged-in users via user_id.
--
-- Idempotent: safe to run repeatedly.

CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- provides gen_random_uuid()

CREATE TABLE IF NOT EXISTS user_content_preferences (
    id                           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                      UUID,
    session_id                   TEXT,
    preferred_language           TEXT        NOT NULL DEFAULT 'en',
    region_code                  TEXT        NOT NULL DEFAULT 'US',
    use_approx_location          BOOLEAN     NOT NULL DEFAULT FALSE,
    location_city                TEXT,
    location_country             TEXT,
    has_completed_language_setup BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at                   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One preferences row per identity. Partial unique indexes allow exactly one of
-- user_id / session_id to be set while still supporting ON CONFLICT upserts.
CREATE UNIQUE INDEX IF NOT EXISTS uniq_ucp_user_id
    ON user_content_preferences (user_id)
    WHERE user_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uniq_ucp_session_id
    ON user_content_preferences (session_id)
    WHERE session_id IS NOT NULL;

-- Keep updated_at fresh on every UPDATE. No existing trigger pattern in the
-- project, so we define a small reusable function here.
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ucp_updated_at ON user_content_preferences;
CREATE TRIGGER trg_ucp_updated_at
    BEFORE UPDATE ON user_content_preferences
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();
