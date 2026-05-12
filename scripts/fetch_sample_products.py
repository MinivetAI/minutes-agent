import argparse
import asyncio
import csv
import json
import os
import sys
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from instructions import FETCH_PRODUCT_KNOWLEDGE
from models import ProductKnowledgeFetchedOutput
from openai_grounded import OpenAIResponsesTask


CATALOG_PATH = "/home/aditya/Minivet/minutes/data/minutes_catalog.tsv"
OUTPUT_DIR = Path("/home/aditya/Minivet/minutes/minutes-agent/sample_outputs_reduced_schema")
EVIDENCE_DIR = Path("/home/aditya/Minivet/minutes/minutes-agent/sample_outputs_reduced_schema_evidence")
RUNS_DIR = Path("/home/aditya/Minivet/minutes/minutes-agent/runs")
REPRESENTATIVE_TARGETS = [
    ("FoodAndNutrition", "Gourmet", "DairyProducts"),
    ("FoodAndNutrition", "Gourmet", "SnacksNibbles"),
    ("FoodAndNutrition", "Gourmet", "FruitsVegetables"),
    ("HouseHoldSupplies", "HouseHoldSuppliesAndConsummables", "HouseHoldSuppliesAndConsummables"),
    ("Grooming", "Grooming", "PersonalHygiene"),
    ("HealthCare", "OverTheCounterMedicine", "OTCLicensed"),
    ("WomenWesternGrowth", "WomenWesternGrowth", "LingerieandSleepwear"),
    ("MensClothingTopwearBranded", "MensTopwear", "MensShirt"),
    ("Mobile", "Mobile", "Handset"),
    ("HomeDecor", "SpiritualItems", "SpiritualItems"),
]


def load_representative_rows(limit: int):
    selected = []
    pending = set(REPRESENTATIVE_TARGETS[:limit])
    with open(CATALOG_PATH, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            key = (
                row.get("analytic_super_category") or "",
                row.get("analytic_category") or "",
                row.get("analytic_sub_category") or "",
            )
            if key in pending:
                selected.append(row)
                pending.remove(key)
            if not pending:
                break
    return selected


def load_diverse_rows(limit: int):
    buckets = {}
    with open(CATALOG_PATH, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            if row.get("product_state") != "ready":
                continue
            if row.get("is_discoverable") not in ("TRUE", "true", "True"):
                continue
            key = (
                row.get("analytic_super_category") or "",
                row.get("analytic_category") or "",
                row.get("analytic_sub_category") or "",
            )
            buckets.setdefault(key, []).append(row)

    ordered_keys = sorted(buckets.keys(), key=lambda item: len(buckets[item]), reverse=True)
    selected = []
    round_index = 0
    while len(selected) < limit:
        any_added = False
        for key in ordered_keys:
            bucket = buckets[key]
            if round_index < len(bucket):
                selected.append(bucket[round_index])
                any_added = True
                if len(selected) >= limit:
                    break
        if not any_added:
            break
        round_index += 1
    return selected


def load_all_rows(limit: int | None):
    rows = []
    with open(CATALOG_PATH, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            if row.get("product_state") != "ready":
                continue
            if row.get("is_discoverable") not in ("TRUE", "true", "True"):
                continue
            rows.append(row)
            if limit is not None and len(rows) >= limit:
                break
    return rows


def build_payload(row):
    return {
        "product_title": row.get("product_title"),
        "brand": row.get("brand") or row.get("seller_entered_brand"),
        "vertical_name": row.get("vertical_name"),
        "analytic_super_category": row.get("analytic_super_category"),
        "analytic_category": row.get("analytic_category"),
        "analytic_sub_category": row.get("analytic_sub_category"),
        "description": row.get("description"),
        "rich_product_description": row.get("rich_product_description"),
        "variant": row.get("variant"),
        "type": row.get("type"),
        "size": row.get("size"),
        "quantity": row.get("quantity"),
        "pack_of": row.get("pack_of"),
        "material": row.get("material"),
        "color": row.get("color"),
        "ideal_for": row.get("ideal_for"),
        "sales_package": row.get("sales_package"),
    }


def write_json_atomic(path: Path, payload):
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True)
    tmp_path.replace(path)


def load_completed_ids(output_dir: Path):
    completed_ids = set()
    for path in output_dir.glob("*.json"):
        parts = path.stem.split("_", 1)
        if len(parts) != 2:
            continue
        product_id = parts[1]
        try:
            with path.open("r", encoding="utf-8") as handle:
                json.load(handle)
            completed_ids.add(product_id)
        except Exception:
            # Corrupt or partial file should be retried on resume.
            continue
    return completed_ids


async def main():
    parser = argparse.ArgumentParser(description="Fetch knowledge for Minutes products")
    parser.add_argument("--limit", type=int, default=10, help="Number of products to fetch")
    parser.add_argument("--model", type=str, default="gpt-5.4-mini-2026-03-17", help="OpenAI model name")
    parser.add_argument(
        "--mode",
        type=str,
        default="representative",
        choices=("representative", "diverse", "all"),
        help="Representative fixed sample, diverse batch, or full ready+discoverable catalog order",
    )
    parser.add_argument("--concurrency", type=int, default=4, help="Maximum concurrent OpenAI requests")
    parser.add_argument("--run-name", type=str, default="", help="Optional run directory name under minutes-agent/runs")
    parser.add_argument("--resume", action="store_true", help="Skip products already written in this run directory")
    args = parser.parse_args()

    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY")

    if args.mode == "representative":
        rows = load_representative_rows(args.limit)
    elif args.mode == "diverse":
        rows = load_diverse_rows(args.limit)
    else:
        rows = load_all_rows(None if args.limit <= 0 else args.limit)

    if args.limit > 0 and len(rows) < args.limit:
        print(f"Warning: only found {len(rows)} rows")

    if args.mode == "all":
        run_name = args.run_name or f"full_openai_{args.model}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        run_root = RUNS_DIR / run_name
        output_dir = run_root / "products"
        evidence_dir = run_root / "evidence"
        failures_path = run_root / "failures.jsonl"
        progress_path = run_root / "progress.json"
    else:
        output_dir = OUTPUT_DIR
        evidence_dir = EVIDENCE_DIR
        failures_path = None
        progress_path = None

    output_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    if args.resume:
        completed_ids = load_completed_ids(output_dir)
        if completed_ids:
            rows = [row for row in rows if row["product_id"] not in completed_ids]
            print(f"Resuming run, skipping {len(completed_ids)} already completed products")

    print(f"Selected {len(rows)} rows for mode={args.mode}")
    if args.mode == "all":
        print(f"Run root: {run_root}")

    task = OpenAIResponsesTask(
        instruction=FETCH_PRODUCT_KNOWLEDGE.strip(),
        guide=ProductKnowledgeFetchedOutput,
        api_key=api_key,
        model=args.model,
        use_web_search=True,
        max_output_tokens=4000,
        max_concurrent=args.concurrency,
        reasoning_effort="none",
    )

    semaphore = asyncio.Semaphore(args.concurrency)
    stats = {"completed": 0, "failed": 0, "total": len(rows)}

    def write_progress():
        if progress_path is None:
            return
        progress_payload = {
            "mode": args.mode,
            "model": args.model,
            "concurrency": args.concurrency,
            "completed": stats["completed"],
            "failed": stats["failed"],
            "total": stats["total"],
        }
        with progress_path.open("w", encoding="utf-8") as handle:
            json.dump(progress_payload, handle, indent=2, ensure_ascii=True)

    async def process_row(index, row):
        payload = build_payload(row)
        async with semaphore:
            print(f"[{index}/{len(rows)}] {payload['product_title']}")
            result = None
            for attempt in range(1, 4):
                result = await task.do(payload)
                if result is not None:
                    break
                print(f"  retry {attempt} failed")
            if result is None:
                print("  -> skipped after repeated parse failures")
                stats["failed"] += 1
                if failures_path is not None:
                    with failures_path.open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps({
                            "product_id": row["product_id"],
                            "product_title": row["product_title"],
                            "analytic_super_category": row.get("analytic_super_category"),
                            "analytic_category": row.get("analytic_category"),
                            "analytic_sub_category": row.get("analytic_sub_category"),
                        }, ensure_ascii=True) + "\n")
                write_progress()
                return

            result_dict = result.model_dump()
            evidence_dict = {
                "product_id": row["product_id"],
                "product_title": row["product_title"],
                "canonical_name": result_dict.get("canonical_name"),
                "source_urls": result_dict.pop("source_urls", []),
            }

            output_path = output_dir / f"{index:05d}_{row['product_id']}.json"
            evidence_path = evidence_dir / f"{index:05d}_{row['product_id']}.json"
            write_json_atomic(output_path, result_dict)
            write_json_atomic(evidence_path, evidence_dict)
            stats["completed"] += 1
            write_progress()
            print(f"  -> {output_path}")

    try:
        await asyncio.gather(*(process_row(index, row) for index, row in enumerate(rows, start=1)))
    finally:
        await task.close()


if __name__ == "__main__":
    asyncio.run(main())
