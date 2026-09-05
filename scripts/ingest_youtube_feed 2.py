"""Manual runner for the daily Chrysalis YouTube feed ingestion."""

from __future__ import annotations

import argparse
import json

from integrations.youtube_ingest import ingest_youtube_videos_sqlite


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest YouTube videos into feed_videos.")
    parser.add_argument("--max-results", type=int, default=10, help="Per-query search result limit, 1-25.")
    parser.add_argument("--days-back", type=int, default=7, help="Published-after window, 2-7 days.")
    parser.add_argument("--db-path", default=None, help="Optional DATABASE_PATH override.")
    args = parser.parse_args()

    result = ingest_youtube_videos_sqlite(
        db_path=args.db_path,
        max_results_per_query=args.max_results,
        days_back=args.days_back,
    )
    print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()
