#!/usr/bin/env python3
"""Run the complete enrichment and user-profile flow against minutes-agent."""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


REQUIRED_TASKS = {
    "fetch_product_knowledge",
    "product_semantic_paragraph",
    "mission_semantic_document",
    "user_category_daypart_summary",
    "user_category_daily_summary",
    "user_category_monthly_summary",
    "user_category_preference_profile",
    "user_basket_daypart_summary",
    "user_basket_daily_summary",
    "user_basket_monthly_summary",
    "user_basket_profile",
    "user_global_profile",
    "user_feed_quality_review",
}


def _request(url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method="POST" if data else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{url} returned HTTP {error.code}: {body}") from error
    if not isinstance(result, dict):
        raise RuntimeError(f"{url} did not return a JSON object")
    return result


def run(base_url: str) -> dict[str, Any]:
    base_url = base_url.rstrip("/")
    health = _request(f"{base_url}/health")
    enabled = set(health.get("tasks") or [])
    missing = REQUIRED_TASKS - enabled
    if missing:
        raise RuntimeError(f"minutes-agent is missing required tasks: {sorted(missing)}")

    definitions = health.get("task_definitions") or {}
    for task in REQUIRED_TASKS:
        definition = definitions.get(task) or {}
        if not definition.get("definition_sha256"):
            raise RuntimeError(f"{task} has no task-definition fingerprint")

    product = _request(
        f"{base_url}/v1/llm/knowledge/fetch-product",
        {
            "product_title": "Amul Taaza Pasteurised Toned Milk 500 ml",
            "brand": "Amul",
            "vertical_name": "Milk",
            "analytic_super_category": "FoodAndNutrition",
            "analytic_category": "Dairy",
            "analytic_sub_category": "MilkXPlain",
            "description": "Pasteurised toned milk in a 500 ml pouch.",
            "variant": "Toned",
            "size": "500 ml",
            "quantity": "500 ml",
            "pack_of": "1",
        },
    )
    product_paragraph = _request(
        f"{base_url}/v1/llm/enrich/product-paragraph",
        {
            "product_paragraph": product["product_paragraph"],
            "intent_paragraph": product["intent_paragraph"],
            "context_paragraph": product["context_paragraph"],
            "canonical_name": product["canonical_name"],
            "product_family": product["product_family"],
            "mission_mappings": product["mission_mappings"],
            "close_substitutes": product["close_substitutes"],
            "common_complements": product["common_complements"],
        },
    )
    mission = _request(
        f"{base_url}/v1/llm/mission/semantic-document",
        {
            "mission_name": "Everyday Milk Refill",
            "current_description": "Replenish household milk for regular use.",
            "mission_class": "routine",
            "family": "daily_essentials",
            "dayparts": ["morning", "afternoon", "night"],
            "seasons": [],
            "diet_tags": ["vegetarian"],
            "lifestyle_tags": [],
            "representative_products": [
                {
                    "product_name": "Amul Taaza Pasteurised Toned Milk 500 ml",
                    "category": "MilkXPlain",
                    "general_product_uses": product["intent_paragraph"],
                }
            ],
        },
    )

    category_daypart = _request(
        f"{base_url}/user/category/daypart-summary",
        {
            "category": "Dairy",
            "date": "2026-07-17",
            "daypart": "afternoon",
            "day_type": "weekday",
            "order_count": 1,
            "products": [
                {
                    "product_name": "Amul Taaza Pasteurised Toned Milk 500 ml",
                    "category": "Dairy",
                    "product_type": "MilkXPlain",
                    "quantity": 2,
                    "product_paragraph": product_paragraph["paragraph"],
                    "general_product_uses": product["intent_paragraph"],
                }
            ],
        },
    )
    category_daily = _request(
        f"{base_url}/user/category/daily-summary",
        {
            "category": "Dairy",
            "date": "2026-07-17",
            "day_type": "weekday",
            "daypart_summaries": [category_daypart],
        },
    )
    category_monthly = _request(
        f"{base_url}/user/category/monthly-summary",
        {
            "category": "Dairy",
            "month": "2026-07",
            "daily_summaries": [category_daily],
        },
    )
    category_profile = _request(
        f"{base_url}/user/category/preference-profile",
        {
            "category": "Dairy",
            "recent_daypart_summaries": [category_daypart],
            "recent_daily_summaries": [category_daily],
            "monthly_summaries": [category_monthly],
        },
    )

    basket_daypart = _request(
        f"{base_url}/user/basket/daypart-summary",
        {
            "date": "2026-07-17",
            "daypart": "afternoon",
            "day_type": "weekday",
            "orders": [
                {
                    "products": [
                        {
                            "product_name": "Amul Taaza Pasteurised Toned Milk 500 ml",
                            "category": "Dairy",
                            "quantity": 2,
                        },
                        {
                            "product_name": "Britannia Brown Bread 400 g",
                            "category": "Bread",
                            "quantity": 1,
                        },
                    ]
                }
            ],
        },
    )
    basket_daily = _request(
        f"{base_url}/user/basket/daily-summary",
        {
            "date": "2026-07-17",
            "day_type": "weekday",
            "daypart_summaries": [basket_daypart],
        },
    )
    basket_monthly = _request(
        f"{base_url}/user/basket/monthly-summary",
        {
            "month": "2026-07",
            "daily_summaries": [basket_daily],
        },
    )
    basket_profile = _request(
        f"{base_url}/user/basket/profile",
        {
            "recent_daypart_summaries": [basket_daypart],
            "recent_daily_summaries": [basket_daily],
            "monthly_summaries": [basket_monthly],
        },
    )
    global_profile = _request(
        f"{base_url}/user/global-profile",
        {
            "category_profiles": [category_profile],
            "basket_profile": basket_profile,
            "recent_summaries": [
                category_daypart["summary_text"],
                basket_daypart["basket_summary_text"],
            ],
        },
    )
    feed_review = _request(
        f"{base_url}/user/feed-quality-review",
        {
            "daypart": "afternoon",
            "global_profile": global_profile,
            "category_profiles": [category_profile],
            "basket_profile": basket_profile,
            "recent_summaries": [category_daypart["summary_text"]],
            "eligible_mission_names": [
                "Everyday Milk Refill",
                "Breakfast Basics",
            ],
            "selected_missions": [
                {
                    "mission_name": "Everyday Milk Refill",
                    "family": "daily_essentials",
                    "semantic_score": 0.91,
                }
            ],
            "selected_products": [
                {
                    "product_name": "Amul Taaza Pasteurised Toned Milk 500 ml",
                    "category": "Dairy",
                    "semantic_score": 0.95,
                }
            ],
        },
    )

    if category_profile["overall_confidence"] != "low":
        raise RuntimeError("single-date category profile must have low confidence")
    if basket_profile["overall_confidence"] != "low":
        raise RuntimeError("single-date basket profile must have low confidence")
    if global_profile["overall_confidence"] != "low":
        raise RuntimeError("single-date global profile must have low confidence")
    if category_monthly["stable_preference_claims"]:
        raise RuntimeError("single-date category summary created a stable preference")
    if basket_monthly["stable_behavior_patterns"]:
        raise RuntimeError("single-date basket summary created a stable behavior")
    semantic_text = " ".join(
        [
            product["product_paragraph"],
            product["intent_paragraph"],
            product["context_paragraph"],
            product_paragraph["paragraph"],
            mission["need_state_text"],
            mission["user_context_text"],
            mission["retrieval_text"],
        ]
    ).lower()
    unsupported_claims = {
        "3% fat",
        "calcium",
        "protein",
        "reduced fat",
        "low fat",
        "all ages",
        "any demographic",
        "age restrictions",
        "500 ml bottles",
        "small family",
        "children",
        "nuclear families",
        "bachelors",
        "working professionals",
    }
    present_claims = sorted(
        claim for claim in unsupported_claims if claim in semantic_text
    )
    if present_claims:
        raise RuntimeError(
            f"enrichment invented unsupported claims: {present_claims}"
        )

    return {
        "status": "passed",
        "tasks_tested": sorted(REQUIRED_TASKS),
        "product": {
            "canonical_name": product["canonical_name"],
            "product_family": product["product_family"],
            "semantic_paragraph": product_paragraph["paragraph"],
        },
        "mission": {
            "identity_text": mission["identity_text"],
            "retrieval_text": mission["retrieval_text"],
        },
        "category_profile": category_profile,
        "basket_profile": basket_profile,
        "global_profile": global_profile,
        "feed_review": feed_review,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8091")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run(args.base_url)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
