#!/usr/bin/env python3
"""Build a user's category + basket + global profile from raw order history.

Reads the sample_1000_users_payloads.json order-history file (one JSON object
per line: user_id, events[] of ORDER_PLACED with timestamp + items[product_id,
quantity]), deterministically buckets it into the LLM waterfall's inputs
(daypart -> daily -> monthly -> profile, for both the category and basket
pipelines), calls a running minutes-agent instance for every stage in
dependency order, and writes every stage's output to disk.

This script owns the deterministic layer described in
docs/LLMUserProfileContract.md section 10: counts, cadence, category-pair
lift/support, and the population daypart baseline. It never asks the LLM to
compute a number; it only ever hands numbers to the LLM and asks it to
interpret them.

Three sources feed the deterministic layer, combined per product:
- Input/minutes_catalog.tsv: the authoritative source for `category`
  (analytic_vertical) and `brand` — covers ~93% of ordered product_ids.
- Input/minutes_crawl_insights_v1/<product_id>.json: an existing
  fetch_product_knowledge output, read for product_paragraph/
  general_product_uses (never for category or brand).
- sample_1000_users_payloads.json itself: the order history (timestamps,
  quantities) that everything else is bucketed against.

A product_id absent from the catalog falls back to a small, evidence-backed
product_id-prefix lookup for category only (each mapping was confirmed by
inspecting a real enriched product under that prefix, not guessed from the
letters); brand has no such fallback and is left null rather than guessed from
the product name. Anything still unresolved is grouped under an explicit
"Unmapped-<prefix>" category rather than a fabricated English name.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT_DIR / "Input" / "sample_1000_users_payloads.json"
DEFAULT_ENRICHMENT_DIR = ROOT_DIR / "Input" / "minutes_crawl_insights_v1"
DEFAULT_CATALOG = ROOT_DIR / "Input" / "minutes_catalog.tsv"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "runs" / "user_profiles"

# Evidence-backed product_id-prefix -> category lookup. Every entry was
# confirmed by opening one real enriched product under that prefix in
# Input/minutes_crawl_insights_v1/<product_id>.json (the fetch_product_knowledge
# output, filed under its product_id) and reading its canonical_name /
# product_family; nothing here is guessed from the 3-letter code itself. These
# 120 prefixes, ranked by order-line volume in the sample, cover ~98% of all
# order lines; anything outside this list falls back to an explicit
# "Unmapped-<prefix>" category rather than a fabricated English name.
PREFIX_CATEGORY_MAP = {
    "VEG": "Vegetables",
    "MLK": "Milk",
    "CKB": "CookiesBiscuits",
    "FRT": "Fruits",
    "CUY": "CurdYogurt",
    "SCM": "SpicesMasala",
    "ARD": "AeratedDrinks",
    "SNS": "SavouriesNamkeens",
    "PLS": "Pulses",
    "BAB": "Breads",
    "FLR": "Flour",
    "CHP": "Chips",
    "EDO": "EdibleOil",
    "CHC": "Chocolates",
    "ICE": "IceCreams",
    "BTM": "Buttermilk",
    "NDL": "Noodles",
    "PTF": "Paneer",
    "RIC": "Rice",
    "DAJ": "Juice",
    "EEG": "Eggs",
    "NDF": "DryFruits",
    "SUG": "Sugar",
    "SAT": "Salt",
    "TEA": "Tea",
    "DWB": "DishWashingBar",
    "CEP": "Desserts",
    "LSI": "Lassi",
    "RMD": "ReadyMeals",
    "LDT": "LiquidDetergent",
    "FFW": "PoojaFlowers",
    "BUT": "Butter",
    "CAF": "Oats",
    "SOP": "Soap",
    "WBR": "WashingBar",
    "GHE": "Ghee",
    "SAK": "Ketchup",
    "CHE": "Cheese",
    "TPS": "Toothpaste",
    "ESR": "EnergyDrinkMix",
    "PSA": "InstantPasta",
    "WER": "PackagedWater",
    "RYM": "DessertMix",
    "LDG": "LiquidDetergent",
    "SAM": "IndianSweets",
    "EDS": "EdibleSeeds",
    "JAS": "Mayonnaise",
    "BCR": "BathroomCleaner",
    "CMF": "Candy",
    "PCP": "Popcorn",
    "DPR": "Diaper",
    "MEA": "FrozenMeat",
    "RUK": "Rusk",
    "PAP": "JuiceConcentrate",
    "SPP": "SanitaryPad",
    "TCN": "ToiletCleaner",
    "WSP": "WashingPowder",
    "MSC": "BodyLotion",
    "SMP": "Shampoo",
    "SYC": "SoyaChunks",
    "HWS": "HandWash",
    "ZET": "Cigarettes",
    "ACC": "Audio",
    "CFE": "FilterCoffee",
    "AIR": "CarFreshener",
    "DCG": "DishWashingGel",
    "HOL": "HairOil",
    "SRP": "ScrubPad",
    "FRY": "Fryums",
    "SOU": "InstantSoup",
    "INS": "PoojaEssentials",
    "FCW": "FaceWash",
    "DCE": "PoojaEssentials",
    "THB": "Toothbrush",
    "DEO": "Deodorant",
    "WFW": "ChocolateWafers",
    "ALO": "VitaminSupplement",
    "FSN": "FabricSoftener",
    "VMC": "Vermicelli",
    "HCO": "FestiveColorPowder",
    "HAI": "PoojaEssentials",
    "BWS": "BodyWash",
    "JGR": "Jaggery",
    "MDM": "MaltDrinkMix",
    "GNM": "Sago",
    "HAS": "Seasoning",
    "CNC": "ChocolateSyrup",
    "AYD": "FiberSupplement",
    "PSL": "ProteinBar",
    "PEN": "Stationery",
    "DTP": "AntacidPowder",
    "PER": "Perfume",
    "BKI": "BreakfastSyrup",
    "PFD": "PetFood",
    "CHT": "Chutney",
    "IRP": "PestControl",
    "HNY": "Honey",
    "SNR": "Sunscreen",
    "HRC": "HairColour",
    "WIP": "BabyWipes",
    "ICC": "IceCubes",
    "VNG": "Vinegar",
    "TLC": "Talc",
    "RXM": "RxMedicine",
    "GRB": "GarbageBags",
    "CDM": "Condoms",
    "FRN": "FaceCream",
    "ANS": "AntisepticCream",
    "CND": "Conditioner",
    "BBY": "BabyFood",
    "PCK": "Pickle",
    "GLA": "GlassCleaner",
    "TNR": "FaceToner",
    "NAP": "PaperNapkins",
    "MPW": "MilkPowder",
    "ART": "ArtStationery",
    "SHR": "FacialRazor",
    "DWD": "DishwashingPowder",
    "PNC": "Pencils",
    "CPB": "CottonSwabs",
}

DAYPART_HOURS = {
    "morning": range(5, 11),
    "afternoon": range(11, 16),
    "evening": range(16, 21),
}  # anything else (21:00-04:59) is night


def daypart_for(dt: datetime) -> str:
    for name, hours in DAYPART_HOURS.items():
        if dt.hour in hours:
            return name
    return "night"


def day_type_for(dt: datetime) -> str:
    return "weekend" if dt.weekday() >= 5 else "weekday"


class Catalog:
    """Authoritative product_id -> analytic_vertical / brand / title lookup
    from Input/minutes_catalog.tsv. A product_id absent from the catalog falls
    back to the evidence-backed prefix table for category only; brand has no
    fallback and stays null rather than being guessed from a product name."""

    def __init__(self, path: Path):
        self._rows: Dict[str, Dict[str, str]] = {}
        if not path.exists():
            return
        with path.open(encoding="utf-8", errors="replace", newline="") as f:
            csv.field_size_limit(10_000_000)
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                product_id = row.get("product_id")
                if product_id:
                    self._rows[product_id] = row

    def category(self, product_id: str) -> str:
        row = self._rows.get(product_id)
        if row and row.get("analytic_vertical"):
            return row["analytic_vertical"]
        prefix = product_id[:3]
        return PREFIX_CATEGORY_MAP.get(prefix, f"Unmapped-{prefix}")

    def brand(self, product_id: str) -> Optional[str]:
        row = self._rows.get(product_id)
        return row.get("brand") or None if row else None

    def title(self, product_id: str) -> Optional[str]:
        row = self._rows.get(product_id)
        return row.get("product_title") or None if row else None


def load_users(path: Path, user_ids: Optional[List[str]], limit: Optional[int]) -> List[Dict[str, Any]]:
    wanted = set(user_ids) if user_ids else None
    users = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if wanted and record["user_id"] not in wanted:
                continue
            users.append(record)
            if wanted and len(users) == len(wanted):
                break
            if not wanted and limit and len(users) >= limit:
                break
    return users


def compute_population_daypart_share(path: Path, sample_users: int = 1000) -> Dict[str, float]:
    """Deterministic population baseline: order share by daypart across the sample."""
    counts = Counter()
    with path.open() as f:
        for i, line in enumerate(f):
            if i >= sample_users:
                break
            record = json.loads(line)
            for event in record.get("events", []):
                if event.get("event_type") != "ORDER_PLACED":
                    continue
                dt = datetime.strptime(event["timestamp"], "%Y-%m-%d %H:%M:%S")
                counts[daypart_for(dt)] += 1
    total = sum(counts.values()) or 1
    return {
        daypart: round(counts.get(daypart, 0) / total, 4)
        for daypart in ("morning", "afternoon", "evening", "night")
    }


class EnrichmentCache:
    """Lazily reads existing fetch_product_knowledge outputs for a product_id."""

    def __init__(self, enrichment_dir: Path):
        self._dir = enrichment_dir
        self._cache: Dict[str, Optional[Dict[str, Any]]] = {}

    def get(self, product_id: str) -> Optional[Dict[str, Any]]:
        if product_id not in self._cache:
            path = self._dir / f"{product_id}.json"
            if path.exists():
                with path.open() as f:
                    self._cache[product_id] = json.load(f)
            else:
                self._cache[product_id] = None
        return self._cache[product_id]


def normalize_orders(user: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse raw events into orders with resolved timestamp/daypart/day_type/category-grouped items."""
    orders = []
    for event in user.get("events", []):
        if event.get("event_type") != "ORDER_PLACED":
            continue
        dt = datetime.strptime(event["timestamp"], "%Y-%m-%d %H:%M:%S")
        # Raw line quantity is always 1 in this dataset; a product's real
        # ordered quantity is the count of repeated lines for that product_id
        # within the same order, never the line-level quantity field itself.
        product_counts = Counter(item["product_id"] for item in event["items"])
        orders.append(
            {
                "order_id": event["event_id"],
                "timestamp": dt,
                "date": dt.strftime("%Y-%m-%d"),
                "month": dt.strftime("%Y-%m"),
                "daypart": daypart_for(dt),
                "day_type": day_type_for(dt),
                "products": [
                    {"product_id": product_id, "quantity": quantity}
                    for product_id, quantity in product_counts.items()
                ],
            }
        )
    orders.sort(key=lambda o: o["timestamp"])
    return orders


def product_evidence(product_id: str, quantity: int, category: str, enrichment: EnrichmentCache, catalog: "Catalog") -> Dict[str, Any]:
    info = enrichment.get(product_id)
    product_name = (info or {}).get("canonical_name") or catalog.title(product_id) or product_id
    return {
        "product_name": product_name,
        "category": category,
        "brand": catalog.brand(product_id),
        "product_type": (info or {}).get("product_family"),
        "quantity": quantity,
        "product_paragraph": (info or {}).get("product_paragraph"),
        "general_product_uses": (info or {}).get("intent_paragraph"),
    }


def compute_observed_cadence(dates: List[str]) -> Tuple[Optional[float], int, int]:
    """Median days between consecutive independent purchase dates for one category."""
    independent_dates = sorted(set(dates))
    evidence_count = len(dates)
    if len(independent_dates) < 3:
        return None, evidence_count, len(independent_dates)
    parsed = [datetime.strptime(d, "%Y-%m-%d") for d in independent_dates]
    gaps = [(b - a).days for a, b in zip(parsed, parsed[1:])]
    return round(statistics.median(gaps), 1), evidence_count, len(independent_dates)


def cadence_class_for(cadence_days: Optional[float]) -> str:
    if cadence_days is None:
        return "unknown"
    if cadence_days <= 7:
        return "fast"
    if cadence_days <= 20:
        return "medium"
    return "slow"


_CONFIDENCE_RANK = {"high": 2, "medium": 1, "low": 0}


def category_profile_quality_key(profile: Dict[str, Any], purchase_volume: int) -> Tuple[int, int, int, int]:
    """Rank a generated CategoryProfileOutput by how well-evidenced it actually
    is, not by how much was purchased. A high-volume category with thin,
    low-confidence evidence should lose out to a modest-volume category the
    LLM itself was confident about. Purchase volume is only the tie-breaker."""
    confidence = _CONFIDENCE_RANK.get(profile.get("overall_confidence"), 0)
    replenishment = profile.get("replenishment") or {}
    evidence_count = replenishment.get("evidence_count") or 0
    independent_date_count = replenishment.get("independent_date_count") or 0
    return (confidence, evidence_count, independent_date_count, purchase_volume)


def compute_category_pair_evidence(orders: List[Dict[str, Any]], enrichment_categories: Dict[str, str], top_n: int = 8) -> List[Dict[str, Any]]:
    """Support/confidence/lift for category pairs, computed once across this user's own orders."""
    basket_categories = []
    for order in orders:
        cats = sorted({enrichment_categories[p["product_id"]] for p in order["products"]})
        if len(cats) >= 2:
            basket_categories.append(cats)
    total = len(orders) or 1
    single_counts = Counter()
    pair_counts = Counter()
    for cats in basket_categories:
        for c in cats:
            single_counts[c] += 1
        for i in range(len(cats)):
            for j in range(i + 1, len(cats)):
                pair_counts[(cats[i], cats[j])] += 1
    results = []
    for (a, b), co_count in pair_counts.items():
        support = co_count / total
        confidence = co_count / (single_counts[a] or 1)
        lift = confidence / ((single_counts[b] / total) or 1)
        results.append(
            {
                "categories": [a, b],
                "support": round(support, 3),
                "confidence": round(confidence, 3),
                "lift": round(lift, 3),
                "co_order_count": co_count,
            }
        )
    results.sort(key=lambda r: r["co_order_count"], reverse=True)
    return results[:top_n]


def post(base_url: str, path: str, payload: Dict[str, Any], timeout: int = 240) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"POST {path} returned HTTP {error.code}: {body}") from error


def write_stage(output_dir: Path, stage: str, key: str, payload: Dict[str, Any]) -> Path:
    stage_dir = output_dir / stage
    stage_dir.mkdir(parents=True, exist_ok=True)
    safe_key = key.replace("/", "_")
    path = stage_dir / f"{safe_key}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return path


def cached_post(base_url: str, path: str, payload: Dict[str, Any], output_dir: Path, stage: str, key: str) -> Dict[str, Any]:
    """POST once and cache to disk; a re-run of the same command skips any
    stage whose output file already exists, so a large multi-hour job can be
    safely interrupted and resumed without redoing completed work."""
    safe_key = key.replace("/", "_")
    cache_path = output_dir / stage / f"{safe_key}.json"
    if cache_path.exists():
        with cache_path.open() as f:
            return json.load(f)
    result = post(base_url, path, payload)
    write_stage(output_dir, stage, key, result)
    return result


def run_concurrent(executor, jobs: List[Tuple[Any, Any]]) -> List[Optional[Dict[str, Any]]]:
    """jobs: list of (label_for_logging, thunk) pairs; thunk() may raise.
    Returns a list of results in the same order as `jobs` (None for any job
    whose thunk raised, logged but not fatal, so one bad bucket never aborts
    the whole run). Positional alignment, not a label-keyed dict, on purpose:
    labels here are for logging only and are not guaranteed unique across
    dayparts/dates/months, so a dict keyed by label would silently drop
    same-labeled results instead of just one of them winning arbitrarily."""
    futures = [(label, executor.submit(thunk)) for label, thunk in jobs]
    results = []
    for label, future in futures:
        try:
            results.append(future.result())
        except Exception as exc:
            print(f"  ! failed [{label}]: {exc}", file=sys.stderr)
            results.append(None)
    return results


def build_user_profile(
    user: Dict[str, Any],
    enrichment: EnrichmentCache,
    catalog: Catalog,
    population_daypart_share: Dict[str, float],
    base_url: str,
    output_dir: Path,
    top_categories: Optional[int],
    dry_run: bool,
    concurrency: int,
    max_global_profile_categories: Optional[int] = 40,
) -> Optional[Dict[str, Any]]:
    user_id = user["user_id"]
    orders = normalize_orders(user)
    if not orders:
        print(f"[{user_id}] no orders, skipping")
        return None

    enrichment_categories = {
        p["product_id"]: catalog.category(p["product_id"])
        for order in orders
        for p in order["products"]
    }

    category_counts = Counter()
    for order in orders:
        for p in order["products"]:
            category_counts[enrichment_categories[p["product_id"]]] += p["quantity"]
    categories = [c for c, _ in category_counts.most_common(top_categories)]

    print(f"[{user_id}] {len(orders)} orders across {len(category_counts)} categories; "
          f"processing {len(categories)} categories" + (" (dry run)" if dry_run else ""))

    user_output_dir = output_dir / user_id
    category_orders = {
        c: [o for o in orders if any(enrichment_categories[p["product_id"]] == c for p in o["products"])]
        for c in categories
    }

    if dry_run:
        category_calls = []
        for c in categories:
            buckets = defaultdict(list)
            for order in category_orders[c]:
                buckets[(order["date"], order["daypart"])].append(order)
            category_calls.append({"category": c, "dry_run_daypart_calls": len(buckets)})
        basket_buckets = defaultdict(list)
        for order in orders:
            basket_buckets[(order["date"], order["daypart"])].append(order)
        summary = {
            "user_id": user_id,
            "order_count": len(orders),
            "categories_processed": categories,
            "category_dry_run_calls": category_calls,
            "basket_dry_run_calls": {"dry_run_daypart_calls": len(basket_buckets)},
        }
        write_stage(output_dir, ".", f"{user_id}_dry_run", summary)
        return summary

    category_pair_evidence = compute_category_pair_evidence(orders, enrichment_categories)

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        # ---- stage 1: daypart, every category + basket bucket in one batch ----
        jobs = []
        routes = []  # parallel list: routing metadata for the same-index job
        for c in categories:
            buckets = defaultdict(list)
            for order in category_orders[c]:
                buckets[(order["date"], order["daypart"])].append(order)
            for (date, daypart), bucket_orders in buckets.items():
                merged = Counter()
                for order in bucket_orders:
                    for p in order["products"]:
                        if enrichment_categories[p["product_id"]] == c:
                            merged[p["product_id"]] += p["quantity"]
                products = [product_evidence(pid, qty, c, enrichment, catalog) for pid, qty in merged.items()]
                request = {
                    "category": c, "date": date, "daypart": daypart,
                    "day_type": bucket_orders[0]["day_type"],
                    "population_daypart_share": population_daypart_share,
                    "order_count": len(bucket_orders), "products": products, "funnel_events": [],
                }
                key = f"{c}_{date}_{daypart}"
                label = ("category_daypart", key)
                jobs.append((label, lambda req=request, k=key: cached_post(base_url, "/user/category/daypart-summary", req, user_output_dir, "category_daypart", k)))
                routes.append({"kind": "category_daypart", "category": c, "date": date})

        basket_buckets = defaultdict(list)
        for order in orders:
            basket_buckets[(order["date"], order["daypart"])].append(order)
        for (date, daypart), bucket_orders in basket_buckets.items():
            basket_orders = [
                {"products": [
                    {"product_name": p["product_id"], "category": enrichment_categories[p["product_id"]], "quantity": p["quantity"]}
                    for p in order["products"]
                ]}
                for order in bucket_orders
            ]
            request = {
                "date": date, "daypart": daypart, "day_type": bucket_orders[0]["day_type"],
                "orders": basket_orders, "abandoned_carts": [], "category_pair_evidence": category_pair_evidence,
            }
            key = f"{date}_{daypart}"
            label = ("basket_daypart", key)
            jobs.append((label, lambda req=request, k=key: cached_post(base_url, "/user/basket/daypart-summary", req, user_output_dir, "basket_daypart", k)))
            routes.append({"kind": "basket_daypart", "date": date})

        print(f"[{user_id}] stage daypart: {len(jobs)} calls")
        daypart_results = run_concurrent(executor, jobs)

        category_daily_inputs: Dict[str, Dict[str, List[Dict]]] = defaultdict(lambda: defaultdict(list))
        basket_daily_inputs: Dict[str, List[Dict]] = defaultdict(list)
        for route, result in zip(routes, daypart_results):
            if result is None:
                continue
            if route["kind"] == "category_daypart":
                category_daily_inputs[route["category"]][route["date"]].append(result)
            else:
                basket_daily_inputs[route["date"]].append(result)

        # ---- stage 2: daily, every category + basket date in one batch ----
        jobs = []
        routes = []
        for c, by_date in category_daily_inputs.items():
            for date, daypart_summaries in by_date.items():
                request = {"category": c, "date": date, "day_type": daypart_summaries[0]["day_type"], "daypart_summaries": daypart_summaries}
                key = f"{c}_{date}"
                label = ("category_daily", key)
                jobs.append((label, lambda req=request, k=key: cached_post(base_url, "/user/category/daily-summary", req, user_output_dir, "category_daily", k)))
                routes.append({"kind": "category_daily", "category": c, "month": date[:7]})
        for date, daypart_summaries in basket_daily_inputs.items():
            request = {"date": date, "day_type": daypart_summaries[0]["day_type"], "daypart_summaries": daypart_summaries}
            label = ("basket_daily", date)
            jobs.append((label, lambda req=request, k=date: cached_post(base_url, "/user/basket/daily-summary", req, user_output_dir, "basket_daily", k)))
            routes.append({"kind": "basket_daily", "month": date[:7]})

        print(f"[{user_id}] stage daily: {len(jobs)} calls")
        daily_results = run_concurrent(executor, jobs)

        category_monthly_inputs: Dict[str, Dict[str, List[Dict]]] = defaultdict(lambda: defaultdict(list))
        basket_monthly_inputs: Dict[str, List[Dict]] = defaultdict(list)
        for route, result in zip(routes, daily_results):
            if result is None:
                continue
            if route["kind"] == "category_daily":
                category_monthly_inputs[route["category"]][route["month"]].append(result)
            else:
                basket_monthly_inputs[route["month"]].append(result)

        # ---- stage 3: monthly, every category + basket month in one batch ----
        jobs = []
        routes = []
        for c, by_month in category_monthly_inputs.items():
            for month, daily_summaries in by_month.items():
                request = {"category": c, "month": month, "daily_summaries": daily_summaries}
                key = f"{c}_{month}"
                label = ("category_monthly", key)
                jobs.append((label, lambda req=request, k=key: cached_post(base_url, "/user/category/monthly-summary", req, user_output_dir, "category_monthly", k)))
                routes.append({"kind": "category_monthly", "category": c})
        for month, daily_summaries in basket_monthly_inputs.items():
            request = {"month": month, "daily_summaries": daily_summaries}
            label = ("basket_monthly", month)
            jobs.append((label, lambda req=request, k=month: cached_post(base_url, "/user/basket/monthly-summary", req, user_output_dir, "basket_monthly", k)))
            routes.append({"kind": "basket_monthly"})

        print(f"[{user_id}] stage monthly: {len(jobs)} calls")
        monthly_results = run_concurrent(executor, jobs)

        category_monthly_outputs: Dict[str, List[Dict]] = defaultdict(list)
        basket_monthly_outputs: List[Dict] = []
        for route, result in zip(routes, monthly_results):
            if result is None:
                continue
            if route["kind"] == "category_monthly":
                category_monthly_outputs[route["category"]].append(result)
            else:
                basket_monthly_outputs.append(result)

        # ---- stage 4: category profiles + basket profile, one batch ----
        jobs = []
        routes = []
        for c in categories:
            monthly_outputs = category_monthly_outputs.get(c, [])
            if not monthly_outputs:
                continue
            purchase_dates = sorted({o["date"] for o in category_orders[c]})
            cadence_days, evidence_count, independent_date_count = compute_observed_cadence(purchase_dates)
            last_purchase_date = purchase_dates[-1] if purchase_dates else None
            predicted_next_purchase_date = (
                (datetime.strptime(last_purchase_date, "%Y-%m-%d") + timedelta(days=cadence_days)).strftime("%Y-%m-%d")
                if last_purchase_date and cadence_days is not None else None
            )
            request = {
                "category": c, "observed_cadence_days": cadence_days,
                "observed_cadence_evidence_count": evidence_count,
                "observed_cadence_independent_date_count": independent_date_count,
                "observed_cadence_class": cadence_class_for(cadence_days),
                "observed_last_purchase_date": last_purchase_date,
                "observed_predicted_next_purchase_date": predicted_next_purchase_date,
                "monthly_summaries": monthly_outputs,
            }
            label = ("category_profile", c)
            jobs.append((label, lambda req=request, k=c: cached_post(base_url, "/user/category/preference-profile", req, user_output_dir, "category_profile", k)))
            routes.append({"kind": "category_profile", "category": c})
        if basket_monthly_outputs:
            label = ("basket_profile",)
            jobs.append((label, lambda req={"monthly_summaries": basket_monthly_outputs}: cached_post(
                base_url, "/user/basket/profile", req, user_output_dir, "basket_profile", "profile"
            )))
            routes.append({"kind": "basket_profile"})

        print(f"[{user_id}] stage profile: {len(jobs)} calls")
        profile_results = run_concurrent(executor, jobs)

    category_profile_by_name = {
        route["category"]: result
        for route, result in zip(routes, profile_results)
        if route["kind"] == "category_profile" and result is not None
    }
    # Rank by how well-evidenced each generated profile actually is
    # (overall_confidence, then evidence/independent-date counts from its own
    # replenishment block), not by purchase volume — a high-volume category
    # with thin evidence should not bump a lower-volume category the LLM was
    # actually confident about. Purchase volume only breaks ties.
    ranked_categories = sorted(
        category_profile_by_name.keys(),
        key=lambda c: category_profile_quality_key(category_profile_by_name[c], category_counts.get(c, 0)),
        reverse=True,
    )
    category_profiles_all = [category_profile_by_name[c] for c in ranked_categories]
    basket_profile = next(
        (result for route, result in zip(routes, profile_results) if route["kind"] == "basket_profile"),
        None,
    )
    if not category_profiles_all or basket_profile is None:
        print(f"[{user_id}] insufficient evidence for a global profile (category_profiles={len(category_profiles_all)}, "
              f"basket_profile={'ok' if basket_profile else 'missing'}); skipping global profile", file=sys.stderr)
        return None

    total_category_count = len(category_profiles_all)
    if max_global_profile_categories and total_category_count > max_global_profile_categories:
        included, omitted = ranked_categories[:max_global_profile_categories], ranked_categories[max_global_profile_categories:]
        category_profiles_for_global = category_profiles_all[:max_global_profile_categories]
        print(f"[{user_id}] global profile will detail the {max_global_profile_categories} best-evidenced of "
              f"{total_category_count} categories.\n  included: {included}\n  omitted:  {omitted}")
    else:
        category_profiles_for_global = category_profiles_all

    recent_summaries = []
    for c in categories[:3]:
        path = user_output_dir / "category_daily"
        if path.exists():
            files = sorted(path.glob(f"{c}_*.json"))
            if files:
                with files[-1].open() as f:
                    recent_summaries.append(json.load(f).get("summary_text", ""))
    basket_daily_dir = user_output_dir / "basket_daily"
    if basket_daily_dir.exists():
        files = sorted(basket_daily_dir.glob("*.json"))
        if files:
            with files[-1].open() as f:
                recent_summaries.append(json.load(f).get("summary_text", ""))

    global_profile = cached_post(
        base_url, "/user/global-profile",
        {
            "category_profiles": category_profiles_for_global,
            "basket_profile": basket_profile,
            "recent_summaries": [s for s in recent_summaries if s],
            "total_category_count": total_category_count,
        },
        output_dir, ".", f"{user_id}_global_profile",
    )
    print(f"[{user_id}] global profile written to {output_dir / f'{user_id}_global_profile.json'}")
    return global_profile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Path to sample_1000_users_payloads.json")
    parser.add_argument("--enrichment-dir", default=str(DEFAULT_ENRICHMENT_DIR), help="Path to per-product fetch_product_knowledge outputs")
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG), help="Path to minutes_catalog.tsv (authoritative category/brand source)")
    parser.add_argument("--base-url", default="http://localhost:8091", help="Running minutes-agent base URL")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Where to write every stage's JSON output")
    parser.add_argument("--user-id", action="append", dest="user_ids", help="Process this user_id; repeatable. Overrides --limit-users.")
    parser.add_argument("--limit-users", type=int, default=1, help="Number of users to process when --user-id is not given")
    parser.add_argument("--top-categories", type=int, default=None, help="Only process each user's N most-purchased categories; omit to process every category the user has")
    parser.add_argument("--max-global-profile-categories", type=int, default=40, help="Cap how many category profiles feed the global-profile call, keeping the best-evidenced by confidence and evidence depth (not purchase volume); every category is still individually profiled and cached regardless. 0 disables the cap.")
    parser.add_argument("--concurrency", type=int, default=8, help="Concurrent in-flight LLM calls per user (within one user's own stage batches)")
    parser.add_argument("--user-concurrency", type=int, default=1, help="Users processed in parallel; total in-flight calls can reach concurrency x user-concurrency, so raise this only once the server's own --max-concurrent and rate limits can absorb it")
    parser.add_argument("--dry-run", action="store_true", help="Build every payload and report call counts without contacting the LLM service")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Computing population daypart baseline from {input_path} ...")
    population_daypart_share = compute_population_daypart_share(input_path)
    print(f"Population daypart share: {population_daypart_share}")

    users = load_users(input_path, args.user_ids, None if args.user_ids else args.limit_users)
    if not users:
        print("No matching users found.", file=sys.stderr)
        sys.exit(1)

    enrichment = EnrichmentCache(Path(args.enrichment_dir))
    catalog_path = Path(args.catalog)
    print(f"Loading catalog from {catalog_path} ...")
    catalog = Catalog(catalog_path)
    print(f"Catalog loaded: {len(catalog._rows)} products" if catalog_path.exists() else "No catalog found; category/brand fall back to the prefix table only")

    def run_one(user):
        try:
            return build_user_profile(
                user, enrichment, catalog, population_daypart_share,
                args.base_url, output_dir, args.top_categories, args.dry_run,
                args.concurrency, args.max_global_profile_categories,
            )
        except Exception as exc:
            print(f"[{user['user_id']}] FAILED: {exc}", file=sys.stderr)
            return None

    succeeded = 0
    failed = 0
    if args.user_concurrency > 1 and not args.dry_run:
        with ThreadPoolExecutor(max_workers=args.user_concurrency) as user_executor:
            for result in user_executor.map(run_one, users):
                succeeded += result is not None
                failed += result is None
    else:
        for user in users:
            result = run_one(user)
            succeeded += result is not None
            failed += result is None

    print(f"Done: {succeeded} succeeded, {failed} failed/skipped out of {len(users)} users. Output: {output_dir}")


if __name__ == "__main__":
    main()
