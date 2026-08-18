#!/usr/bin/env python3
"""Run the compact Minutes profile waterfall for one sampled user.

This is an inspection runner, not a serving process. It uses the exact task
definitions registered in ``tasks.py``: the same input schemas, prompt
preparation functions, instructions, and output models. It calls the internal
Qwen endpoint directly so a local FastAPI/Alfred process is not required for a
profile-quality preview.

The runner keeps user identity, dates, months, and output paths in its own
orchestration layer. None are sent to the LLM.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_USER_FILE = ROOT.parent / "sample_200_users_payloads.json"
DEFAULT_CATALOG = ROOT.parent / "minutes_catalog.tsv"
DEFAULT_OUTPUT = ROOT / "runs" / "feed_profile_preview"
DEFAULT_USER_ID = "ACC51292DCF5DF24DCE87A7753DE2CF7945D"
DEFAULT_ENDPOINT = "http://rtx-1.dev.internal:8040/v1/chat/completions"
DEFAULT_MODEL = "qwen3.6-35b"

sys.path.insert(0, str(ROOT))
from tasks import TASKS  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--users", type=Path, default=DEFAULT_USER_FILE)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--user-id", default=DEFAULT_USER_ID)
    parser.add_argument("--category", default="Milk")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--force", action="store_true", help="Ignore cached LLM task outputs")
    return parser.parse_args()


def load_user(path: Path, user_id: str) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        for line in source:
            row = json.loads(line)
            if row.get("user_id") == user_id:
                return row
    raise ValueError(f"user not found: {user_id}")


def product_ids(events: Iterable[Mapping[str, Any]]) -> set[str]:
    return {
        str(item["product_id"])
        for event in events
        if event.get("event_type") == "ORDER_PLACED"
        for item in event.get("items") or []
        if item.get("product_id")
    }


def load_catalog(path: Path, wanted: set[str]) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8", errors="replace", newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            product_id = row.get("product_id") or ""
            if product_id in wanted:
                rows[product_id] = row
    return rows


def daypart(timestamp: datetime) -> str:
    if 5 <= timestamp.hour < 11:
        return "morning"
    if 11 <= timestamp.hour < 16:
        return "afternoon"
    if 16 <= timestamp.hour < 21:
        return "evening"
    return "night"


def day_type(timestamp: datetime) -> str:
    return "weekend" if timestamp.weekday() >= 5 else "weekday"


def catalog_category(row: Mapping[str, str] | None, product_id: str) -> str:
    if row and row.get("analytic_vertical"):
        return str(row["analytic_vertical"])
    if product_id.startswith("MLK"):
        return "Milk"
    return product_id[:3]


def product_payload(product_id: str, quantity: int, catalog: Mapping[str, Mapping[str, str]]) -> dict[str, Any]:
    row = catalog.get(product_id) or {}
    description = row.get("rich_product_description") or row.get("detailed_description") or row.get("description") or None
    return {
        "product_name": row.get("product_title") or product_id,
        "brand": row.get("brand") or None,
        "type": row.get("type") or row.get("variant") or None,
        "pack_size": row.get("size") or row.get("quantity") or None,
        "ordered_quantity": quantity,
        "product_description": description,
    }


def normalized_orders(user: Mapping[str, Any], catalog: Mapping[str, Mapping[str, str]]) -> list[dict[str, Any]]:
    orders = []
    for event in user.get("events") or []:
        if event.get("event_type") != "ORDER_PLACED":
            continue
        timestamp = datetime.strptime(str(event["timestamp"]), "%Y-%m-%d %H:%M:%S")
        quantities = Counter(str(item["product_id"]) for item in event.get("items") or [])
        products = []
        for product_id, quantity in quantities.items():
            row = catalog.get(product_id)
            products.append(
                {
                    "product_id": product_id,
                    "category": catalog_category(row, product_id),
                    **product_payload(product_id, quantity, catalog),
                }
            )
        orders.append(
            {
                "timestamp": timestamp,
                "date": timestamp.strftime("%Y-%m-%d"),
                "month": timestamp.strftime("%Y-%m"),
                "daypart": daypart(timestamp),
                "day_type": day_type(timestamp),
                "products": products,
            }
        )
    return sorted(orders, key=lambda row: row["timestamp"])


class TaskRunner:
    def __init__(self, endpoint: str, model: str, cache_dir: Path, timeout: int, force: bool):
        self.endpoint = endpoint
        self.model = model
        self.cache_dir = cache_dir
        self.timeout = timeout
        self.force = force

    def run(self, task_name: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        config = TASKS[task_name]
        input_model = config["input_model"]
        output_model = config["output_model"]
        validated_input = input_model.model_validate(payload).model_dump()
        prompt_input = config["prepare_input"](validated_input)
        key_payload = {
            "task": task_name,
            "model": self.model,
            "instruction": config["instruction"],
            "input": prompt_input,
        }
        digest = hashlib.sha256(
            json.dumps(key_payload, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        cache_path = self.cache_dir / task_name / f"{digest}.json"
        if cache_path.exists() and not self.force:
            return json.loads(cache_path.read_text(encoding="utf-8"))

        messages = [
            {
                "role": "system",
                "content": "Return only one valid JSON object matching the output schema.",
            },
            {
                "role": "user",
                "content": (
                    f"TASK\n{config['instruction'].strip()}\n\nOUTPUT SCHEMA\n"
                    f"{json.dumps(output_model.model_json_schema(), ensure_ascii=False)}\n\nINPUTS\n"
                    f"{json.dumps(prompt_input, ensure_ascii=False)}"
                ),
            },
        ]
        last_error: Exception | None = None
        result: dict[str, Any] | None = None
        for attempt in range(int(config.get("postprocess_retries", 0)) + 1):
            body = {
                "model": self.model,
                "messages": messages,
                "max_tokens": config["max_tokens"],
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
                "chat_template_kwargs": {"enable_thinking": False},
            }
            request = urllib.request.Request(
                self.endpoint,
                data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = json.load(response)
            content = raw["choices"][0]["message"]["content"]
            try:
                validated_result = output_model.model_validate(json.loads(content))
                postprocess = config.get("postprocess_output")
                if postprocess:
                    validated_result = postprocess(validated_result, prompt_input)
                result = validated_result.model_dump(exclude_none=True)
                break
            except Exception as error:  # The agent server performs the same repair loop.
                last_error = error
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Your previous JSON did not validate. Correct it and return only a "
                            f"valid object matching the schema. Validation error: {error}"
                        ),
                    }
                )
        if result is None:
            raise RuntimeError(f"{task_name} failed output validation after retries: {last_error}")
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        return result


def category_waterfall(runner: TaskRunner, orders: list[dict[str, Any]], category: str) -> dict[str, Any]:
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for order in orders:
        category_products = [product for product in order["products"] if product["category"] == category]
        if category_products:
            buckets[(order["date"], order["daypart"])].append({**order, "products": category_products})

    dayparts = []
    for (date, part), bucket in sorted(buckets.items()):
        products: dict[str, dict[str, Any]] = {}
        for order in bucket:
            for product in order["products"]:
                products.setdefault(product["product_id"], dict(product))
        # Keep the first catalog record and aggregate all matching order lines
        # below, so repeated lines in one order become one factual product row.
        merged = []
        for product_id in products:
            original = products[product_id]
            total = sum(
                product["ordered_quantity"]
                for order in bucket
                for product in order["products"]
                if product["product_id"] == product_id
            )
            merged.append({key: value for key, value in original.items() if key not in {"product_id", "category"}} | {"ordered_quantity": total})
        output = runner.run(
            "user_category_daypart_summary",
            {"category": category, "daypart": part, "day_type": bucket[0]["day_type"], "products": merged},
        )
        dayparts.append({"date": date, "daypart": part, "day_type": bucket[0]["day_type"], **output})

    daily = []
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in dayparts:
        by_date[row["date"]].append(row)
    for date, rows in sorted(by_date.items()):
        output = runner.run(
            "user_category_daily_summary",
            {
                "category": category,
                "day_type": rows[0]["day_type"],
                "daypart_summaries": [{key: row[key] for key in ("daypart", "day_type", "summary_text")} for row in rows],
            },
        )
        daily.append({"date": date, "day_type": rows[0]["day_type"], **output})

    monthly = []
    by_month: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in daily:
        by_month[row["date"][:7]].append(row)
    for month, rows in sorted(by_month.items()):
        output = runner.run(
            "user_category_monthly_summary",
            {
                "category": category,
                "daily_summaries": [{key: row[key] for key in ("day_type", "summary_text")} for row in rows],
            },
        )
        monthly.append({"month": month, **output})

    profile = runner.run(
        "user_category_preference_profile",
        {
            "category": category,
            "recent_daypart_summaries": [{key: row[key] for key in ("daypart", "day_type", "summary_text")} for row in dayparts[-24:]],
            "recent_daily_summaries": [{key: row[key] for key in ("day_type", "summary_text")} for row in daily[-31:]],
            "monthly_summaries": [{"summary_text": row["summary_text"]} for row in monthly[-18:]],
        },
    )
    return {"daypart": dayparts, "daily": daily, "monthly": monthly, "profile": profile}


def basket_waterfall(runner: TaskRunner, orders: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for order in orders:
        buckets[(order["date"], order["daypart"])].append(order)

    dayparts = []
    for (date, part), bucket in sorted(buckets.items()):
        output = runner.run(
            "user_basket_daypart_summary",
            {
                "daypart": part,
                "day_type": bucket[0]["day_type"],
                "orders": [
                    {
                        "products": [
                            {key: product[key] for key in ("product_name", "brand", "type", "pack_size", "ordered_quantity")} | {"category": product["category"]}
                            for product in order["products"]
                        ]
                    }
                    for order in bucket
                ],
            },
        )
        dayparts.append({"date": date, "daypart": part, "day_type": bucket[0]["day_type"], **output})

    daily = []
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in dayparts:
        by_date[row["date"]].append(row)
    for date, rows in sorted(by_date.items()):
        output = runner.run(
            "user_basket_daily_summary",
            {"day_type": rows[0]["day_type"], "daypart_summaries": [{key: row[key] for key in ("daypart", "day_type", "summary_text")} for row in rows]},
        )
        daily.append({"date": date, "day_type": rows[0]["day_type"], **output})

    monthly = []
    by_month: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in daily:
        by_month[row["date"][:7]].append(row)
    for month, rows in sorted(by_month.items()):
        output = runner.run(
            "user_basket_monthly_summary",
            {"daily_summaries": [{key: row[key] for key in ("day_type", "summary_text")} for row in rows]},
        )
        monthly.append({"month": month, **output})

    profile = runner.run(
        "user_basket_profile",
        {
            "recent_daypart_summaries": [{key: row[key] for key in ("daypart", "day_type", "summary_text")} for row in dayparts[-24:]],
            "recent_daily_summaries": [{key: row[key] for key in ("day_type", "summary_text")} for row in daily[-31:]],
            "monthly_summaries": [{"summary_text": row["summary_text"]} for row in monthly[-18:]],
        },
    )
    return {"daypart": dayparts, "daily": daily, "monthly": monthly, "profile": profile}


def main() -> None:
    args = parse_args()
    user = load_user(args.users, args.user_id)
    catalog = load_catalog(args.catalog, product_ids(user.get("events") or []))
    orders = normalized_orders(user, catalog)
    runner = TaskRunner(args.endpoint, args.model, args.output / "llm_cache", args.timeout, args.force)

    category = category_waterfall(runner, orders, args.category)
    basket = basket_waterfall(runner, orders)
    global_profile = runner.run(
        "user_global_profile",
        {
            "category_profiles": [
                {
                    "category": args.category,
                    "summary_text": category["profile"]["summary_text"],
                }
            ],
            "basket_summary_text": basket["profile"]["summary_text"],
        },
    )
    result = {
        "source": {"user_id": user["user_id"], "category": args.category, "order_count": len(orders)},
        "category": category,
        "basket": basket,
        "global": global_profile,
    }
    output_path = args.output / "profiles" / f"{user['user_id']}_{args.category}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(output_path)
    print(json.dumps({"category": category["profile"], "basket": basket["profile"], "global": global_profile}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
