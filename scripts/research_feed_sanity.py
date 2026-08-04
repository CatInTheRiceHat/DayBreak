#!/usr/bin/env python3
"""Engineering-only distribution check for versioned research feed policies.

The utility expands the repository's deterministic demo-video fixtures into a
larger unique inventory, generates many independently seeded feed windows, and
prints aggregate selection metrics. It validates the technical manipulation;
it does not measure or make claims about participant well-being.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.ranking.research_policies import (  # noqa: E402
    BALANCED_POLICY_VERSION,
    HEALTHY_CATEGORIES,
    REGULAR_POLICY_VERSION,
    build_research_feed_payload,
)


SEED_FILE = ROOT / "datasets" / "seed_videos.json"


def load_validation_inventory(*, copies: int = 10) -> list[dict]:
    fixtures = json.loads(SEED_FILE.read_text(encoding="utf-8")).get("videos", [])
    inventory: list[dict] = []
    for copy_index in range(copies):
        for fixture_index, fixture in enumerate(fixtures):
            original_id = fixture.get("youtube_video_id") or f"fixture-{fixture_index}"
            inventory.append({
                "video_id": f"sanity-{copy_index}-{original_id}",
                "title": fixture.get("title") or "",
                "description": fixture.get("description") or "",
                "tags": fixture.get("tags") or [],
                "channel_id": f"fixture-creator-{fixture_index}",
                "channel_title": fixture.get("channel_title") or f"Creator {fixture_index}",
                "source_category": fixture.get("source_category") or "",
                "source_query": "research_feed_sanity",
                "source_type": "search",
                "integrity_score": 0.8,
                "popularity_score": (len(fixtures) - fixture_index) / max(1, len(fixtures)),
            })
    return inventory


def summarize_policy(
    inventory: list[dict],
    *,
    policy_version: str,
    windows: int,
    window_size: int,
    base_seed: str,
) -> dict:
    categories: Counter[str] = Counter()
    post_count = duplicate_count = adjacent_count = same_category_count = 0
    repeated_creator_count = fallback_windows = 0

    for window_index in range(windows):
        payload = build_research_feed_payload(
            inventory,
            policy_version=policy_version,
            k=window_size,
            seed=f"{base_seed}:{window_index}",
        )
        items = payload["items"]
        ids = [str(item.get("post_id") or "") for item in items]
        category_values = [str(item.get("content_category") or "unknown") for item in items]
        creator_values = [
            str(item.get("channel_id") or item.get("channel_title") or "unknown")
            for item in items
        ]
        post_count += len(items)
        duplicate_count += len(ids) - len(set(ids))
        categories.update(category_values)
        adjacent_count += max(0, len(category_values) - 1)
        same_category_count += sum(
            left == right for left, right in zip(category_values, category_values[1:])
        )
        repeated_creator_count += len(creator_values) - len(set(creator_values))
        fallback_windows += int(any(
            item.get("selection_reason") == "inventory_fallback" for item in items
        ))

    healthy_count = sum(categories[name] for name in HEALTHY_CATEGORIES)
    unknown_count = categories["unknown"]
    denominator = max(1, post_count)
    return {
        "policy_version": policy_version,
        "windows": windows,
        "window_size": window_size,
        "posts_returned": post_count,
        "category_distribution": {
            category: {
                "count": count,
                "percentage": round(100 * count / denominator, 2),
            }
            for category, count in sorted(categories.items())
        },
        "healthy_content_percentage": round(100 * healthy_count / denominator, 2),
        "unknown_category_percentage": round(100 * unknown_count / denominator, 2),
        "duplicate_post_rate": round(duplicate_count / denominator, 6),
        "consecutive_same_category_rate": round(
            same_category_count / max(1, adjacent_count), 6
        ),
        "repeated_creator_rate": round(repeated_creator_count / denominator, 6),
        "fallback_windows": fallback_windows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--windows", type=int, default=500)
    parser.add_argument("--window-size", type=int, default=12)
    parser.add_argument("--inventory-copies", type=int, default=10)
    parser.add_argument("--seed", default="chrysalis-policy-sanity-v1")
    args = parser.parse_args()
    if args.windows < 1 or args.window_size < 1 or args.inventory_copies < 1:
        parser.error("windows, window-size, and inventory-copies must all be positive")

    inventory = load_validation_inventory(copies=args.inventory_copies)
    report = {
        "purpose": "engineering_validation_only",
        "fixture_source": str(SEED_FILE.relative_to(ROOT)),
        "inventory_posts": len(inventory),
        "metrics": {
            "duplicate_post_rate": "duplicate selections divided by returned posts",
            "consecutive_same_category_rate": "equal-category adjacent pairs divided by all adjacent pairs",
            "repeated_creator_rate": "creator occurrences beyond the first per window divided by returned posts",
            "fallback_windows": "windows containing at least one inventory_fallback selection",
        },
        "policies": [
            summarize_policy(
                inventory,
                policy_version=policy_version,
                windows=args.windows,
                window_size=args.window_size,
                base_seed=args.seed,
            )
            for policy_version in (REGULAR_POLICY_VERSION, BALANCED_POLICY_VERSION)
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
