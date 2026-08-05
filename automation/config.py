"""Passive configuration definitions for recurring DayBreak automation.

Nothing in this module starts a job, opens a database connection, or performs a
network request. Phase 1 does not wire these definitions into production entry
points; the values document the current ingestion boundaries for a later,
behavior-preserving migration.

General application configuration, database credentials, recommendation
settings, and frontend settings deliberately remain outside this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Iterable, Mapping


# Environment-variable names used specifically to invoke or tune automation.
# Values are read only by explicit helper calls; importing this module does not
# inspect the environment.
YOUTUBE_API_KEY_ENV = "YOUTUBE_API_KEY"
FEED_INGEST_SECRET_ENV = "FEED_INGEST_SECRET"
VERCEL_CRON_SECRET_ENV = "CRON_SECRET"
GITHUB_API_BASE_URL_ENV = "CHRYSALIS_API_BASE_URL"
YOUTUBE_QUERY_OVERRIDE_ENV = "YOUTUBE_FEED_QUERIES"
MAX_TRUSTED_CHANNELS_ENV = "MAX_TRUSTED_CHANNELS_PER_RUN"


@dataclass(frozen=True, slots=True)
class YouTubeIngestJobLimits:
    """Current per-run ingestion boundaries, recorded without changing callers."""

    admin_results_per_query: int = 10
    cron_extract_results_per_query: int = 15
    days_back: int = 7
    minimum_results_per_query: int = 1
    maximum_results_per_query: int = 25
    minimum_days_back: int = 2
    maximum_days_back: int = 7
    youtube_request_timeout_seconds: int = 12
    default_trusted_channels_per_run: int = 2


YOUTUBE_INGEST_JOB_LIMITS = YouTubeIngestJobLimits()


@dataclass(frozen=True, slots=True)
class SchedulerAuthConfig:
    """Scheduler credentials loaded from environment variables on demand.

    Secret fields are excluded from ``repr`` so routine debug output cannot
    accidentally print their values.
    """

    feed_ingest_secret: str | None = field(default=None, repr=False)
    vercel_cron_secret: str | None = field(default=None, repr=False)


def load_scheduler_auth(
    environment: Mapping[str, str] | None = None,
) -> SchedulerAuthConfig:
    """Load scheduler secrets without supplying defaults or logging values."""

    source = os.environ if environment is None else environment
    return SchedulerAuthConfig(
        feed_ingest_secret=_nonempty(source.get(FEED_INGEST_SECRET_ENV)),
        vercel_cron_secret=_nonempty(source.get(VERCEL_CRON_SECRET_ENV)),
    )


def missing_automation_environment(
    required_names: Iterable[str],
    environment: Mapping[str, str] | None = None,
) -> tuple[str, ...]:
    """Return required automation variables that are absent or blank."""

    source = os.environ if environment is None else environment
    return tuple(name for name in required_names if not _nonempty(source.get(name)))


def _nonempty(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
