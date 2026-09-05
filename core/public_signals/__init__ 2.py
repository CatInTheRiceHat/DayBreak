"""Public signal scanner v1: schema, stub provider, storage, ranking hooks."""

from .provider import PublicSignalProvider, StubPublicSignalProvider
from .ranking import PublicSignalContext, PublicSignalEvaluation, evaluate_public_signal
from .schema import (
    ChannelSafetyRecord,
    PublicSignalRecord,
    PUBLIC_SIGNAL_VERSION,
)
from .storage import (
    derive_channel_safety,
    ensure_postgres_public_signal_tables,
    ensure_sqlite_public_signal_tables,
    load_cached_context_postgres,
    load_cached_context_sqlite,
    load_or_scan_context_postgres,
    load_or_scan_context_sqlite,
)

__all__ = [
    "ChannelSafetyRecord",
    "PUBLIC_SIGNAL_VERSION",
    "PublicSignalContext",
    "PublicSignalEvaluation",
    "PublicSignalProvider",
    "PublicSignalRecord",
    "StubPublicSignalProvider",
    "derive_channel_safety",
    "ensure_postgres_public_signal_tables",
    "ensure_sqlite_public_signal_tables",
    "evaluate_public_signal",
    "load_cached_context_postgres",
    "load_cached_context_sqlite",
    "load_or_scan_context_postgres",
    "load_or_scan_context_sqlite",
]
