#!/usr/bin/env python3
"""Build a user's category, basket, and global profiles incrementally, order
by order, from a rolling window of recent orders plus each artifact's own
previous output — an alternative to the category/basket/monthly waterfall in
generate_user_profiles.py, built to compare profile quality between the two
approaches on the same users.

Unlike the waterfall (which aggregates deterministically bottom-up through
daypart -> daily -> monthly -> profile stages, rebuilding each artifact from
scratch every run), this script simulates one order-placed event at a time.
Each order triggers, in this dependency order:
1. one /user/running-profile/category-update call per category the order
   touched, each seeing only that category's own rolling window (default 40
   of its own past order-appearances) plus its own previous output;
2. one /user/running-profile/basket-update call, seeing a basket-level
   rolling window (default 40 orders, any category), that same window's
   freshly recomputed category_pair_evidence (support/confidence/lift, the
   same statistic the waterfall's basket daypart stage uses), and its own
   previous output;
3. one /user/running-profile/update (global) call, built — like the
   waterfall's global profile — from the user's current category profiles
   and basket profile, not from raw orders directly, plus its own previous
   output.

Steps 1 and 2 are mutually independent for the same order and run
concurrently; step 3 waits for both, since the global update needs their
fresh results. Across orders, everything is strictly sequential (each step
depends on the previous step's own output for that same artifact).

Reuses the deterministic order-parsing layer (Catalog, EnrichmentCache,
normalize_orders, load_users, cached_post_merged, run_concurrent) from
generate_user_profiles.py so both pipelines see identical order/category/
brand resolution and identical on-disk caching/resume behavior — the only
thing under comparison is the profile-building strategy itself.

Output layout mirrors generate_user_profiles.py's for direct comparison:
  <output-dir>/<user_id>/category_profile/<category>.json   (final, per category)
  <output-dir>/<user_id>/basket_profile/profile.json        (final)
  <output-dir>/<user_id>_running_profile.json               (final, global)
Every intermediate step is also cached under
<output-dir>/<user_id>/{category_profile_steps/<category>,basket_profile_steps,running_profile_steps}/<seq>_<date>.json
so a full run can be inspected step by step to watch each tier evolve.
"""

from __future__ import annotations

import argparse
import sys
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

_ROOT_DIR = Path(__file__).resolve().parent.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

from scripts.generate_user_profiles import (  # noqa: E402
    DEFAULT_CATALOG,
    DEFAULT_ENRICHMENT_DIR,
    DEFAULT_INPUT,
    ROOT_DIR,
    Catalog,
    EnrichmentCache,
    cached_post_merged,
    cadence_class_for,
    compute_category_pair_evidence,
    compute_observed_cadence,
    frequency_segment_for,
    load_users,
    normalize_orders,
    run_concurrent,
    write_stage,
)

DEFAULT_OUTPUT_DIR = ROOT_DIR / "runs" / "running_user_profiles"
DEFAULT_WINDOW_SIZE = 40
DEFAULT_CONCURRENCY = 4


def order_evidence(order: Dict[str, Any], enrichment_categories: Dict[str, str], catalog: Catalog) -> Dict[str, Any]:
    """Lean per-order product evidence (all categories): name, category,
    brand, quantity only — no product_paragraph/general_product_uses. This
    same evidence repeats across up to `--window-size` orders in every
    basket/global call, so it is kept deliberately minimal."""
    products = []
    for item in order["products"]:
        product_id = item["product_id"]
        products.append(
            {
                "product_name": catalog.title(product_id) or product_id,
                "category": enrichment_categories[product_id],
                "brand": catalog.brand(product_id),
                "quantity": item["quantity"],
            }
        )
    return {
        "date": order["date"],
        "daypart": order["daypart"],
        "day_type": order["day_type"],
        "products": products,
    }


def order_evidence_for_category(
    order: Dict[str, Any], category: str, enrichment_categories: Dict[str, str], catalog: Catalog
) -> Dict[str, Any]:
    """Same as order_evidence, filtered to only this category's products —
    only ever called for an order already known to touch this category, so
    the filtered products list is never empty."""
    products = []
    for item in order["products"]:
        product_id = item["product_id"]
        if enrichment_categories[product_id] != category:
            continue
        products.append(
            {
                "product_name": catalog.title(product_id) or product_id,
                "category": category,
                "brand": catalog.brand(product_id),
                "quantity": item["quantity"],
            }
        )
    return {
        "date": order["date"],
        "daypart": order["daypart"],
        "day_type": order["day_type"],
        "products": products,
    }


def merge_running_category_evidence(result: Dict[str, Any], category: str, window: List[Dict[str, Any]]) -> None:
    """replenishment/evidence are never sent to the model — both are
    computed here directly from this category's own rolling window (already
    capped to <= window_size orders that touched this category, including
    the just-placed order), never a fresh read of this user's full raw
    order history."""
    dates = [o["date"] for o in window]
    cadence_days, _, independent_date_count = compute_observed_cadence(dates)
    last_date = max(dates) if dates else None
    predicted_next_purchase_date = (
        (datetime.strptime(last_date, "%Y-%m-%d") + timedelta(days=cadence_days)).strftime("%Y-%m-%d")
        if last_date and cadence_days is not None
        else None
    )
    replenishment_text = (
        f"{category} is reordered roughly every {cadence_days:.0f} days."
        if cadence_days is not None
        else f"Not enough independent purchase dates to establish a cadence for {category} yet."
    )
    result["replenishment"] = {
        "cadence_days": cadence_days,
        "cadence_class": cadence_class_for(cadence_days),
        "predicted_next_purchase_date": predicted_next_purchase_date,
        "replenishment_text": replenishment_text,
    }
    result["evidence"] = {
        "evidence_count": len(window),
        "independent_date_count": independent_date_count,
        "first_seen_at": min(dates) if dates else None,
        "last_seen_at": max(dates) if dates else None,
    }


def merge_running_basket_evidence(result: Dict[str, Any], user_id: str, window: List[Dict[str, Any]]) -> None:
    """evidence/user_id/artifact_type/updated_at are never sent to the model
    — all four are computed here directly from the basket-level rolling
    window (already capped to <= window_size orders, any category,
    including the just-placed order), never a fresh read of this user's
    full raw order history."""
    dates = sorted({o["date"] for o in window})
    result["evidence"] = {
        "evidence_count": len(window),
        "independent_date_count": len(dates),
        "first_seen_at": dates[0] if dates else None,
        "last_seen_at": dates[-1] if dates else None,
    }
    result["user_id"] = user_id
    result["artifact_type"] = "running_basket_profile"
    result["updated_at"] = datetime.utcnow().isoformat()


def merge_running_global_metadata(result: Dict[str, Any], user_id: str, basket_profile: Dict[str, Any]) -> None:
    """shopping_style.frequency_segment/user_id/profile_type/updated_at are
    never sent to the model — frequency_segment is computed here from the
    basket profile's own accumulated evidence (never a fresh read of raw
    orders), the same pattern generate_user_profiles.py's
    merge_global_metadata uses for the waterfall."""
    basket_evidence = basket_profile.get("evidence") or {}
    order_count = basket_evidence.get("evidence_count") or 0
    first_seen_at = basket_evidence.get("first_seen_at")
    last_seen_at = basket_evidence.get("last_seen_at")
    span_days = (
        (datetime.strptime(last_seen_at, "%Y-%m-%d") - datetime.strptime(first_seen_at, "%Y-%m-%d")).days
        if first_seen_at and last_seen_at
        else 0
    )
    shopping_style = result.setdefault("shopping_style", {})
    shopping_style["frequency_segment"] = frequency_segment_for(order_count, max(span_days, 1)) if order_count else None
    shopping_style.setdefault("deal_seeking", None)
    shopping_style.setdefault("price_sensitivity", None)
    result["user_id"] = user_id
    result["profile_type"] = "running"
    result["updated_at"] = datetime.utcnow().isoformat()


def run_user(
    user: Dict[str, Any],
    enrichment: EnrichmentCache,
    catalog: Catalog,
    base_url: str,
    output_dir: Path,
    window_size: int,
    concurrency: int,
    max_orders: Optional[int],
) -> Optional[Dict[str, Any]]:
    user_id = user["user_id"]
    orders = normalize_orders(user)
    if not orders:
        print(f"[{user_id}] no orders, skipping")
        return None
    if max_orders:
        orders = orders[-max_orders:]

    enrichment_categories = {
        p["product_id"]: catalog.category(p["product_id"])
        for order in orders
        for p in order["products"]
    }

    user_output_dir = output_dir / user_id
    category_windows: Dict[str, deque] = {}
    category_profiles: Dict[str, Dict[str, Any]] = {}
    basket_window: deque = deque(maxlen=window_size)
    previous_basket_profile: Optional[Dict[str, Any]] = None
    previous_global_profile: Optional[Dict[str, Any]] = None

    print(f"[{user_id}] simulating {len(orders)} order-placed events, window size {window_size}")
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        for seq, order in enumerate(orders, start=1):
            order_date = order["date"]
            key = f"{seq:04d}_{order_date}"
            touched_categories = sorted({enrichment_categories[p["product_id"]] for p in order["products"]})

            # ---- category + basket updates: independent of each other for this one order ----
            jobs = []
            routes = []
            for category in touched_categories:
                # Append first, so the deque (maxlen=window_size) always
                # holds at most window_size orders *including* the new one —
                # recent_orders is everything else in that same capped
                # window, so recent_orders plus new_order together never
                # exceed window_size total.
                window = category_windows.setdefault(category, deque(maxlen=window_size))
                window.append(order)
                window_snapshot = list(window)
                new_order_evidence = order_evidence_for_category(order, category, enrichment_categories, catalog)
                recent_orders_evidence = [
                    order_evidence_for_category(o, category, enrichment_categories, catalog)
                    for o in window_snapshot[:-1]
                ]
                request = {
                    "category": category,
                    "new_order": new_order_evidence,
                    "recent_orders": recent_orders_evidence,
                    "previous_category_profile": category_profiles.get(category),
                }

                def merge_category(result: Dict[str, Any], category=category, window_snapshot=window_snapshot) -> None:
                    merge_running_category_evidence(result, category, window_snapshot)

                jobs.append((("category", category), lambda req=request, k=key, cat=category, merge=merge_category: cached_post_merged(
                    base_url, "/user/running-profile/category-update", req,
                    user_output_dir, f"category_profile_steps/{cat}", k, merge,
                )))
                routes.append({"kind": "category", "category": category})

            # Same append-first pattern as the category loop above: recent_orders
            # plus new_order together never exceed window_size total.
            basket_window.append(order)
            basket_window_snapshot = list(basket_window)
            basket_new_order_evidence = order_evidence(order, enrichment_categories, catalog)
            basket_recent_orders_evidence = [
                order_evidence(o, enrichment_categories, catalog) for o in basket_window_snapshot[:-1]
            ]
            # category_pair_evidence uses the full capped window (including
            # the just-placed order) — recomputed fresh from it on every
            # call, never accumulated through the model's own prior output,
            # so a relationship the model previously failed to surface can
            # still be recovered on the very next call instead of staying
            # lost.
            category_pair_evidence = compute_category_pair_evidence(basket_window_snapshot, enrichment_categories)
            basket_request = {
                "new_order": basket_new_order_evidence,
                "recent_orders": basket_recent_orders_evidence,
                "category_pair_evidence": category_pair_evidence,
                "previous_basket_profile": previous_basket_profile,
            }

            def merge_basket(result: Dict[str, Any], user_id=user_id, window_snapshot=basket_window_snapshot) -> None:
                merge_running_basket_evidence(result, user_id, window_snapshot)

            jobs.append((("basket",), lambda req=basket_request, k=key, merge=merge_basket: cached_post_merged(
                base_url, "/user/running-profile/basket-update", req,
                user_output_dir, "basket_profile_steps", k, merge,
            )))
            routes.append({"kind": "basket"})

            results = run_concurrent(executor, jobs)
            for route, result in zip(routes, results):
                if result is None:
                    continue
                if route["kind"] == "category":
                    category_profiles[route["category"]] = result
                else:
                    previous_basket_profile = result

            # ---- global update: depends on this order's fresh category + basket results ----
            if not category_profiles or previous_basket_profile is None:
                print(
                    f"[{user_id}] order {seq}: skipping global update "
                    f"(categories={len(category_profiles)}, basket_profile={'ok' if previous_basket_profile else 'missing'})"
                )
                continue

            # Deliberately no raw order data here — like the waterfall's
            # global profile, this tier only ever sees what the category and
            # basket tiers have already synthesized, never the order itself.
            global_request = {
                "category_profiles": list(category_profiles.values()),
                "basket_profile": previous_basket_profile,
                "previous_profile": previous_global_profile,
            }

            def merge_global(result: Dict[str, Any], user_id=user_id, basket_profile=previous_basket_profile) -> None:
                merge_running_global_metadata(result, user_id, basket_profile)

            previous_global_profile = cached_post_merged(
                base_url, "/user/running-profile/update", global_request,
                user_output_dir, "running_profile_steps", key, merge_global,
            )

    for category, profile in category_profiles.items():
        write_stage(user_output_dir, "category_profile", category, profile)
    if previous_basket_profile is not None:
        write_stage(user_output_dir, "basket_profile", "profile", previous_basket_profile)
    if previous_global_profile is not None:
        write_stage(output_dir, ".", f"{user_id}_running_profile", previous_global_profile)
        print(
            f"[{user_id}] running profile ({len(orders)} orders simulated, {len(category_profiles)} categories) "
            f"written to {output_dir / f'{user_id}_running_profile.json'}"
        )
    return previous_global_profile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Path to sample_1000_users_payloads.json")
    parser.add_argument("--enrichment-dir", default=str(DEFAULT_ENRICHMENT_DIR), help="Path to per-product fetch_product_knowledge outputs")
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG), help="Path to minutes_catalog.tsv (authoritative category/brand source)")
    parser.add_argument("--base-url", default="http://localhost:8091", help="Running minutes-agent base URL")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Where to write every tier's final profile and intermediate steps")
    parser.add_argument("--user-id", action="append", dest="user_ids", help="Process this user_id; repeatable. Overrides --limit-users.")
    parser.add_argument("--limit-users", type=int, default=1, help="Number of users to process when --user-id is not given")
    parser.add_argument("--window-size", type=int, default=DEFAULT_WINDOW_SIZE, help="Rolling window size: how many recent orders stay visible to each tier's update call (per-category for category updates, any-category for basket updates)")
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY, help="Concurrent in-flight LLM calls per order step (every touched category's update plus the basket update, which are mutually independent for the same order)")
    parser.add_argument("--max-orders-per-user", type=int, default=None, help="Simulate at most this many of each user's most recent orders (one round of LLM calls per order) instead of their full history; omit to replay every order")
    parser.add_argument("--user-concurrency", type=int, default=1, help="Users processed in parallel; each user's own order sequence is inherently sequential (every step depends on the previous step's own output for that tier), so this is the only concurrency knob across users")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    enrichment = EnrichmentCache(Path(args.enrichment_dir))
    catalog_path = Path(args.catalog)
    print(f"Loading catalog from {catalog_path} ...")
    catalog = Catalog(catalog_path)
    print(f"Catalog loaded: {len(catalog._rows)} products" if catalog_path.exists() else "No catalog found; category/brand fall back to the prefix table only")

    users = load_users(input_path, args.user_ids, None if args.user_ids else args.limit_users)
    if not users:
        print("No matching users found.", file=sys.stderr)
        sys.exit(1)

    def run_one(user: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            return run_user(
                user, enrichment, catalog, args.base_url, output_dir,
                args.window_size, args.concurrency, args.max_orders_per_user,
            )
        except Exception as exc:
            print(f"[{user['user_id']}] FAILED: {exc}", file=sys.stderr)
            return None

    succeeded = 0
    if args.user_concurrency > 1:
        with ThreadPoolExecutor(max_workers=args.user_concurrency) as executor:
            for result in executor.map(run_one, users):
                succeeded += result is not None
    else:
        for user in users:
            succeeded += run_one(user) is not None

    print(f"Done: {succeeded} succeeded out of {len(users)} users. Output: {output_dir}")


if __name__ == "__main__":
    main()
