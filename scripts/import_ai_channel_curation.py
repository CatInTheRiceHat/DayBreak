#!/usr/bin/env python3
"""Import AI-generated channel curation rows into the Chrysalis trust registry.

AI labels channels (trusted / blocked / pending / rejected); a human later
removes or disables exceptions directly in Supabase. AI-added rows are marked
``added_by='ai'`` / ``review_status='unreviewed'`` and never overwrite a human's
review or a human-disabled (active=false) row.

IMPORTANT: a trusted/whitelisted row is NOT a safety bypass. Ingestion still runs
every video through the English-only, blocked-language, blocked-term, and
integrity gates; ``active`` only gates *eligibility*.

Examples:
  .venv/bin/python scripts/import_ai_channel_curation.py --backend postgres --input ai_channels.json
  .venv/bin/python scripts/import_ai_channel_curation.py --backend sqlite  --input ai_channels.json --dry-run
  .venv/bin/python scripts/import_ai_channel_curation.py --backend postgres --input ai_channels.json --force-reactivate --limit 5

Input JSON: an array of objects, e.g.
  [{"platform":"youtube","channel_id":"UCxxxx","channel_title":"...",
    "channel_url":"https://...","trust_status":"trusted","source_type":"wellness",
    "confidence_score":0.86,"reason":"..."}]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Make the project importable when run directly as a script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.trust_registry import (  # noqa: E402
    AI_TRUST_STATUSES,
    ensure_trust_tables_sqlite,
    upsert_ai_channel_curation,
    validate_ai_curation_row,
)


def _load_rows(path: str) -> list:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        raise SystemExit(f"error: input file not found: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"error: invalid JSON in {path}: {exc}")
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise SystemExit("error: input must be a JSON array of channel objects")
    return data


def _connect(backend: str, db_path: str | None):
    """Open a connection. Never prints DATABASE_URL or any secret."""
    if backend == "postgres":
        if "DATABASE_URL" not in os.environ:
            raise SystemExit("error: DATABASE_URL is not set in the environment")
        try:
            import psycopg2
            return psycopg2.connect(os.environ["DATABASE_URL"])
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001 — sanitize: only the error TYPE, never the URL
            raise SystemExit(f"error: could not connect to Postgres ({type(exc).__name__})")
    import sqlite3
    from core.database import resolve_database_path
    conn = sqlite3.connect(resolve_database_path(db_path))
    conn.row_factory = sqlite3.Row
    ensure_trust_tables_sqlite(conn)
    return conn


def _route_table(trust_status: str) -> str:
    return "blocked_youtube_channels" if trust_status == "blocked" else "trusted_youtube_channels"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import AI channel curation rows into the Chrysalis trust registry."
    )
    parser.add_argument("--input", required=True, help="Path to a JSON array of channel curation objects.")
    parser.add_argument("--backend", choices=["sqlite", "postgres"], default="postgres",
                        help="Target database backend (default: postgres).")
    parser.add_argument("--db-path", default=None, help="sqlite DATABASE_PATH override (sqlite backend only).")
    parser.add_argument("--dry-run", action="store_true", help="Validate + preview only; makes no DB changes.")
    parser.add_argument("--force-reactivate", action="store_true",
                        help="Reactivate rows a human set active=false (otherwise left disabled).")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N rows.")
    args = parser.parse_args(argv)

    rows = _load_rows(args.input)
    if args.limit is not None:
        rows = rows[: max(0, args.limit)]

    # Validate everything up front (used by both dry-run and real run).
    valid: list[dict] = []
    invalid: list[tuple[int, str | None, str]] = []
    for i, raw in enumerate(rows):
        try:
            valid.append(validate_ai_curation_row(raw))
        except Exception as exc:  # noqa: BLE001
            cid = raw.get("channel_id") if isinstance(raw, dict) else None
            invalid.append((i, cid, str(exc)))

    if args.dry_run:
        print(f"DRY RUN — {len(rows)} row(s) from {args.input} (backend={args.backend})")
        by_status: dict[str, int] = {}
        for norm in valid:
            by_status[norm["trust_status"]] = by_status.get(norm["trust_status"], 0) + 1
            print(f"  OK   {norm['channel_id']:<28} {norm['trust_status']:<9} "
                  f"active={str(norm['active']):<5} → {_route_table(norm['trust_status'])}")
        for idx, cid, err in invalid:
            print(f"  SKIP [{idx}] {cid or '?'}: {err}")
        print(f"\nwould process {len(valid)} valid {by_status} | skipped(invalid)={len(invalid)}")
        print("no database changes were made (dry run).")
        return 0

    conn = _connect(args.backend, args.db_path)
    inserted = updated = skipped = 0
    errors: list[tuple[str | None, str]] = []
    try:
        for norm in valid:
            try:
                res = upsert_ai_channel_curation(
                    conn, backend=args.backend, force_reactivate=args.force_reactivate, **norm
                )
                if res["action"] == "inserted":
                    inserted += 1
                else:
                    updated += 1
            except Exception as exc:  # noqa: BLE001 — one bad row never aborts the batch
                skipped += 1
                errors.append((norm.get("channel_id"), str(exc)))
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass

    skipped += len(invalid)
    for idx, cid, err in invalid:
        errors.append((cid, err))

    print(f"import complete (backend={args.backend}): "
          f"inserted={inserted} updated={updated} skipped={skipped}")
    for cid, err in errors:
        print(f"  skipped {cid or '?'}: {err}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
