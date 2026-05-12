import argparse
import csv
import json
import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

from dotenv import load_dotenv
from openai import OpenAI

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from instructions import FETCH_PRODUCT_KNOWLEDGE
from models import ProductKnowledgeFetchedOutput
from openai_grounded import (
    build_responses_request_kwargs,
    extract_source_urls_from_response_items,
)


CATALOG_PATH = Path("/home/aditya/Minivet/minutes/data/minutes_catalog.tsv")
RUNS_DIR = Path("/home/aditya/Minivet/minutes/minutes-agent/runs")
DB_PATH = RUNS_DIR / "batch_state.sqlite3"
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


def utc_now() -> str:
    return datetime.now().isoformat()


def get_db() -> sqlite3.Connection:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS runs (
            run_name TEXT PRIMARY KEY,
            mode TEXT,
            limit_value INTEGER,
            offset_value INTEGER,
            model TEXT,
            reasoning_effort TEXT,
            shard_size INTEGER,
            exclude_product_ids_file TEXT,
            prepared_at TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS shards (
            run_name TEXT NOT NULL,
            shard_id TEXT NOT NULL,
            request_path TEXT,
            manifest_path TEXT,
            request_count INTEGER,
            status TEXT,
            file_id TEXT,
            batch_id TEXT,
            output_file_id TEXT,
            error_file_id TEXT,
            materialized_count INTEGER DEFAULT 0,
            materialized_at TEXT,
            request_counts_json TEXT,
            usage_json TEXT,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (run_name, shard_id)
        );

        CREATE TABLE IF NOT EXISTS products (
            custom_id TEXT PRIMARY KEY,
            run_name TEXT NOT NULL,
            shard_id TEXT NOT NULL,
            item_index INTEGER NOT NULL,
            product_id TEXT NOT NULL,
            product_title TEXT,
            analytic_super_category TEXT,
            analytic_category TEXT,
            analytic_sub_category TEXT,
            status TEXT NOT NULL,
            output_path TEXT,
            evidence_path TEXT,
            materialized_at TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_products_product_id ON products(product_id);
        CREATE INDEX IF NOT EXISTS idx_products_status ON products(status);
        CREATE INDEX IF NOT EXISTS idx_products_run_shard ON products(run_name, shard_id);
        CREATE INDEX IF NOT EXISTS idx_shards_status ON shards(status);
        """
    )
    return conn


def upsert_run_db(conn: sqlite3.Connection, state: Dict) -> None:
    conn.execute(
        """
        INSERT INTO runs (
            run_name, mode, limit_value, offset_value, model, reasoning_effort,
            shard_size, exclude_product_ids_file, prepared_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_name) DO UPDATE SET
            mode=excluded.mode,
            limit_value=excluded.limit_value,
            offset_value=excluded.offset_value,
            model=excluded.model,
            reasoning_effort=excluded.reasoning_effort,
            shard_size=excluded.shard_size,
            exclude_product_ids_file=excluded.exclude_product_ids_file,
            prepared_at=excluded.prepared_at,
            updated_at=excluded.updated_at
        """,
        (
            state["run_name"],
            state.get("mode"),
            state.get("limit"),
            state.get("offset"),
            state.get("model"),
            state.get("reasoning_effort"),
            state.get("shard_size"),
            state.get("exclude_product_ids_file"),
            state.get("prepared_at"),
            utc_now(),
        ),
    )


def upsert_shard_db(conn: sqlite3.Connection, run_name: str, shard: Dict) -> None:
    conn.execute(
        """
        INSERT INTO shards (
            run_name, shard_id, request_path, manifest_path, request_count, status,
            file_id, batch_id, output_file_id, error_file_id, materialized_count,
            materialized_at, request_counts_json, usage_json, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_name, shard_id) DO UPDATE SET
            request_path=excluded.request_path,
            manifest_path=excluded.manifest_path,
            request_count=excluded.request_count,
            status=excluded.status,
            file_id=excluded.file_id,
            batch_id=excluded.batch_id,
            output_file_id=excluded.output_file_id,
            error_file_id=excluded.error_file_id,
            materialized_count=excluded.materialized_count,
            materialized_at=excluded.materialized_at,
            request_counts_json=excluded.request_counts_json,
            usage_json=excluded.usage_json,
            updated_at=excluded.updated_at
        """,
        (
            run_name,
            shard["shard_id"],
            shard.get("request_path"),
            shard.get("manifest_path"),
            shard.get("request_count"),
            shard.get("status"),
            shard.get("file_id"),
            shard.get("batch_id"),
            shard.get("output_file_id"),
            shard.get("error_file_id"),
            shard.get("materialized_count", 0),
            shard.get("materialized_at"),
            json.dumps(shard.get("request_counts"), ensure_ascii=True) if shard.get("request_counts") is not None else None,
            json.dumps(shard.get("usage"), ensure_ascii=True) if shard.get("usage") is not None else None,
            utc_now(),
        ),
    )


def upsert_products_db(conn: sqlite3.Connection, run_name: str, shard_id: str, manifest: List[Dict], status: str) -> None:
    now = utc_now()
    rows = [
        (
            item["custom_id"],
            run_name,
            shard_id,
            item["index"],
            item["product_id"],
            item.get("product_title"),
            item.get("analytic_super_category"),
            item.get("analytic_category"),
            item.get("analytic_sub_category"),
            status,
            now,
        )
        for item in manifest
    ]
    conn.executemany(
        """
        INSERT INTO products (
            custom_id, run_name, shard_id, item_index, product_id, product_title,
            analytic_super_category, analytic_category, analytic_sub_category,
            status, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(custom_id) DO UPDATE SET
            run_name=excluded.run_name,
            shard_id=excluded.shard_id,
            item_index=excluded.item_index,
            product_id=excluded.product_id,
            product_title=excluded.product_title,
            analytic_super_category=excluded.analytic_super_category,
            analytic_category=excluded.analytic_category,
            analytic_sub_category=excluded.analytic_sub_category,
            status=excluded.status,
            updated_at=excluded.updated_at
        """,
        rows,
    )


def update_products_status_for_shard(conn: sqlite3.Connection, run_name: str, shard_id: str, status: str) -> None:
    conn.execute(
        """
        UPDATE products
        SET status = ?, updated_at = ?
        WHERE run_name = ? AND shard_id = ?
          AND status NOT IN ('materialized', 'failed_quota', 'failed_remote', 'failed_parse', 'abandoned')
        """,
        (status, utc_now(), run_name, shard_id),
    )


def mark_product_failed_db(conn: sqlite3.Connection, custom_id: str, status: str) -> None:
    conn.execute(
        """
        UPDATE products
        SET status = ?, updated_at = ?
        WHERE custom_id = ?
        """,
        (status, utc_now(), custom_id),
    )


def mark_product_materialized_db(
    conn: sqlite3.Connection,
    custom_id: str,
    output_path: Path,
    evidence_path: Path,
) -> None:
    now = utc_now()
    conn.execute(
        """
        UPDATE products
        SET status = ?, output_path = ?, evidence_path = ?, materialized_at = ?, updated_at = ?
        WHERE custom_id = ?
        """,
        ("materialized", str(output_path), str(evidence_path), now, now, custom_id),
    )


def load_excluded_ids_from_db(
    conn: sqlite3.Connection,
    *,
    include_inflight: bool = True,
) -> set[str]:
    statuses = ["materialized"]
    if include_inflight:
        statuses.extend(["prepared", "submitted", "validating", "in_progress", "finalizing", "completed"])
    query = (
        "SELECT DISTINCT product_id FROM products "
        f"WHERE status IN ({','.join('?' for _ in statuses)})"
    )
    rows = conn.execute(query, statuses).fetchall()
    return {row[0] for row in rows}


def sync_run_to_db(paths: Dict[str, Path], state: Dict) -> None:
    conn = get_db()
    try:
        upsert_run_db(conn, state)
        for shard in state.get("shards", []):
            upsert_shard_db(conn, state["run_name"], shard)
            manifest = shard.get("requests") or []
            if manifest:
                product_status = "materialized" if shard.get("materialized_at") else shard.get("status", "prepared")
                upsert_products_db(conn, state["run_name"], shard["shard_id"], manifest, product_status)
        conn.commit()
    finally:
        conn.close()


def load_representative_rows(limit: int) -> List[Dict[str, str]]:
    selected: List[Dict[str, str]] = []
    pending = set(REPRESENTATIVE_TARGETS[:limit])
    with CATALOG_PATH.open(newline="", encoding="utf-8") as handle:
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


def load_diverse_rows(limit: int) -> List[Dict[str, str]]:
    buckets: Dict[tuple[str, str, str], List[Dict[str, str]]] = {}
    with CATALOG_PATH.open(newline="", encoding="utf-8") as handle:
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
    selected: List[Dict[str, str]] = []
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


def load_all_rows(limit: int | None, offset: int = 0) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    seen = 0
    with CATALOG_PATH.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            if row.get("product_state") != "ready":
                continue
            if row.get("is_discoverable") not in ("TRUE", "true", "True"):
                continue
            if seen < offset:
                seen += 1
                continue
            rows.append(row)
            if limit is not None and len(rows) >= limit:
                break
    return rows


def build_payload(row: Dict[str, str]) -> Dict[str, str | None]:
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


def write_json_atomic(path: Path, payload) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True)
    tmp_path.replace(path)


def load_completed_ids(output_dir: Path) -> set[str]:
    completed_ids: set[str] = set()
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
            continue
    return completed_ids


def load_product_ids_file(path: Path | None) -> set[str]:
    if path is None or not path.exists():
        return set()
    product_ids: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            product_id = line.strip()
            if product_id:
                product_ids.add(product_id)
    return product_ids


def load_product_ids_ordered(path: Path | None) -> List[str]:
    if path is None or not path.exists():
        return []
    product_ids: List[str] = []
    seen: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            product_id = line.strip()
            if product_id and product_id not in seen:
                seen.add(product_id)
                product_ids.append(product_id)
    return product_ids


def ensure_run_dirs(run_name: str) -> Dict[str, Path]:
    run_root = RUNS_DIR / run_name
    paths = {
        "run_root": run_root,
        "products": run_root / "products",
        "evidence": run_root / "evidence",
        "batches": run_root / "batches",
        "artifacts": run_root / "artifacts",
        "state": run_root / "state.json",
        "errors": run_root / "errors.jsonl",
    }
    for key in ("run_root", "products", "evidence", "batches", "artifacts"):
        paths[key].mkdir(parents=True, exist_ok=True)
    return paths


def load_state(state_path: Path) -> Dict:
    if state_path.exists():
        return json.loads(state_path.read_text(encoding="utf-8"))
    return {"shards": []}


def save_state(state_path: Path, state: Dict) -> None:
    write_json_atomic(state_path, state)


def select_rows(mode: str, limit: int, offset: int = 0) -> List[Dict[str, str]]:
    if mode == "representative":
        return load_representative_rows(limit)
    if mode == "diverse":
        return load_diverse_rows(limit)
    return load_all_rows(None if limit <= 0 else limit, offset=offset)


def chunked(items: List[Dict[str, str]], size: int) -> Iterable[List[Dict[str, str]]]:
    for start in range(0, len(items), size):
        yield items[start:start + size]


def product_output_path(products_dir: Path, index: int, product_id: str) -> Path:
    return products_dir / f"{index:05d}_{product_id}.json"


def evidence_output_path(evidence_dir: Path, index: int, product_id: str) -> Path:
    return evidence_dir / f"{index:05d}_{product_id}.json"


def create_request_line(
    *,
    run_name: str,
    model: str,
    reasoning_effort: str,
    index: int,
    row: Dict[str, str],
) -> Dict:
    payload = build_payload(row)
    body = build_responses_request_kwargs(
        instruction=FETCH_PRODUCT_KNOWLEDGE.strip(),
        guide=ProductKnowledgeFetchedOutput,
        model=model,
        data=payload,
        use_web_search=True,
        max_output_tokens=4000,
        reasoning_effort=reasoning_effort,
    )
    custom_id = f"{run_name}:{index:05d}:{row['product_id']}"
    return {
        "custom_id": custom_id,
        "method": "POST",
        "url": "/v1/responses",
        "body": body,
    }


def prepare_batches(args) -> None:
    paths = ensure_run_dirs(args.run_name)
    conn = get_db()
    include_ids = load_product_ids_ordered(
        Path(args.include_product_ids_file) if getattr(args, "include_product_ids_file", "") else None
    )
    selection_limit = args.limit
    if include_ids:
        selection_limit = 0
    elif args.mode == "all" and (
        args.resume
        or args.exclude_product_ids_file
    ):
        # For catalog-wide runs with exclusion/resume, apply the limit after filtering
        # so "next N products" really means N incomplete products.
        selection_limit = 0
    rows = select_rows(args.mode, selection_limit, offset=args.offset)
    if include_ids:
        include_set = set(include_ids)
        row_by_id = {row["product_id"]: row for row in rows if row["product_id"] in include_set}
        rows = [row_by_id[product_id] for product_id in include_ids if product_id in row_by_id]
    if args.resume:
        completed_ids = load_completed_ids(paths["products"])
        if completed_ids:
            rows = [row for row in rows if row["product_id"] not in completed_ids]

    db_exclude_ids = load_excluded_ids_from_db(conn, include_inflight=True)
    if db_exclude_ids:
        rows = [row for row in rows if row["product_id"] not in db_exclude_ids]

    exclude_ids = load_product_ids_file(
        Path(args.exclude_product_ids_file) if args.exclude_product_ids_file else None
    )
    if exclude_ids:
        rows = [row for row in rows if row["product_id"] not in exclude_ids]
    if args.limit > 0 and len(rows) > args.limit:
        rows = rows[:args.limit]

    state = load_state(paths["state"])
    state.update(
        {
            "run_name": args.run_name,
            "mode": args.mode,
            "limit": args.limit,
            "offset": args.offset,
            "model": args.model,
            "reasoning_effort": args.reasoning_effort,
            "shard_size": args.shard_size,
            "exclude_product_ids_file": args.exclude_product_ids_file,
            "include_product_ids_file": args.include_product_ids_file,
            "prepared_at": datetime.now().isoformat(),
        }
    )

    existing_custom_ids = {
        item["custom_id"]
        for shard in state.get("shards", [])
        for item in shard.get("requests", [])
    }

    shards = state.setdefault("shards", [])
    next_shard_num = len(shards) + 1
    total_written = 0

    for batch_rows in chunked(rows, args.shard_size):
        requests = []
        manifest = []
        for offset, row in enumerate(batch_rows, start=1):
            index = total_written + offset
            request_line = create_request_line(
                run_name=args.run_name,
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                index=index,
                row=row,
            )
            if request_line["custom_id"] in existing_custom_ids:
                continue
            requests.append(request_line)
            manifest.append(
                {
                    "custom_id": request_line["custom_id"],
                    "index": index,
                    "product_id": row["product_id"],
                    "product_title": row.get("product_title"),
                    "analytic_super_category": row.get("analytic_super_category"),
                    "analytic_category": row.get("analytic_category"),
                    "analytic_sub_category": row.get("analytic_sub_category"),
                }
            )
        total_written += len(batch_rows)
        if not requests:
            continue

        shard_id = f"shard_{next_shard_num:04d}"
        request_path = paths["batches"] / f"{shard_id}.requests.jsonl"
        manifest_path = paths["batches"] / f"{shard_id}.manifest.jsonl"
        with request_path.open("w", encoding="utf-8") as handle:
            for line in requests:
                handle.write(json.dumps(line, ensure_ascii=True) + "\n")
        with manifest_path.open("w", encoding="utf-8") as handle:
            for line in manifest:
                handle.write(json.dumps(line, ensure_ascii=True) + "\n")

        shards.append(
            {
                "shard_id": shard_id,
                "request_path": str(request_path),
                "manifest_path": str(manifest_path),
                "request_count": len(requests),
                "status": "prepared",
                "requests": manifest,
                "file_id": None,
                "batch_id": None,
                "output_file_id": None,
                "error_file_id": None,
                "materialized_count": 0,
            }
        )
        next_shard_num += 1

    save_state(paths["state"], state)
    sync_run_to_db(paths, state)
    print(f"Prepared {len(state['shards'])} shard(s) for run {args.run_name}")
    for shard in state["shards"]:
        print(f"{shard['shard_id']}: {shard['status']} ({shard['request_count']} requests)")
    conn.close()


def submit_batches(args) -> None:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY")
    client = OpenAI(api_key=api_key)
    conn = get_db()

    paths = ensure_run_dirs(args.run_name)
    state = load_state(paths["state"])

    submitted = 0
    for shard in state.get("shards", []):
        if shard["status"] not in {"prepared", "upload_failed", "submit_failed"}:
            continue
        if args.max_shards and submitted >= args.max_shards:
            break

        request_path = Path(shard["request_path"])
        with request_path.open("rb") as handle:
            uploaded = client.files.create(
                file=handle,
                purpose="batch",
            )

        batch = client.batches.create(
            input_file_id=uploaded.id,
            endpoint="/v1/responses",
            completion_window="24h",
            metadata={
                "run_name": args.run_name,
                "shard_id": shard["shard_id"],
                "model": state["model"],
            },
            output_expires_after={"anchor": "created_at", "seconds": 2592000},
        )

        shard["file_id"] = uploaded.id
        shard["batch_id"] = batch.id
        shard["status"] = batch.status
        upsert_shard_db(conn, state["run_name"], shard)
        update_products_status_for_shard(conn, state["run_name"], shard["shard_id"], batch.status)
        conn.commit()
        save_state(paths["state"], state)
        print(f"{shard['shard_id']} -> file {uploaded.id} -> batch {batch.id} ({batch.status})")
        submitted += 1
    conn.close()


def poll_batches(args) -> None:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY")
    client = OpenAI(api_key=api_key)
    conn = get_db()

    paths = ensure_run_dirs(args.run_name)
    state = load_state(paths["state"])

    newly_completed = 0
    for shard in state.get("shards", []):
        batch_id = shard.get("batch_id")
        if not batch_id:
            continue
        previous_status = shard.get("status")
        batch = client.batches.retrieve(batch_id)
        shard["status"] = batch.status
        shard["output_file_id"] = getattr(batch, "output_file_id", None)
        shard["error_file_id"] = getattr(batch, "error_file_id", None)
        shard["request_counts"] = (
            batch.request_counts.model_dump()
            if getattr(batch, "request_counts", None)
            else None
        )
        if getattr(batch, "usage", None):
            shard["usage"] = batch.usage.model_dump()
        upsert_shard_db(conn, state["run_name"], shard)
        update_products_status_for_shard(conn, state["run_name"], shard["shard_id"], batch.status)
        print(
            f"{shard['shard_id']}: {batch.status} "
            f"completed={getattr(batch.request_counts, 'completed', 0) if getattr(batch, 'request_counts', None) else 0} "
            f"failed={getattr(batch.request_counts, 'failed', 0) if getattr(batch, 'request_counts', None) else 0}"
        )
        if batch.status == "completed" and previous_status != "completed":
            newly_completed += 1

    conn.commit()
    save_state(paths["state"], state)
    auto_materialized = materialize_batches(args, client=client, state=state, paths=paths, conn=conn)
    if newly_completed or auto_materialized:
        print(
            f"poll summary: newly_completed_shards={newly_completed} "
            f"auto_materialized_products={auto_materialized}"
        )
    conn.close()


def download_file_content(client: OpenAI, file_id: str) -> str:
    content = client.files.content(file_id)
    text = getattr(content, "text", None)
    if callable(text):
        return text()
    if isinstance(text, str):
        return text
    string = str(content)
    if string and string != repr(content):
        return string
    if hasattr(content, "read"):
        data = content.read()
        if isinstance(data, bytes):
            return data.decode("utf-8")
        return data
    raise RuntimeError(f"Unable to read content for file {file_id}")


def load_manifest(manifest_path: Path) -> Dict[str, Dict]:
    manifest: Dict[str, Dict] = {}
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            item = json.loads(line)
            manifest[item["custom_id"]] = item
    return manifest


def extract_output_text_from_response_body(body: Dict) -> str | None:
    if body.get("output_text"):
        return body["output_text"]

    for item in body.get("output") or []:
        if item.get("type") != "message":
            continue
        for content in item.get("content") or []:
            if content.get("type") == "output_text" and content.get("text"):
                return content["text"]
    return None


def materialize_shard(client: OpenAI, paths: Dict[str, Path], state: Dict, shard: Dict) -> int:
    if shard.get("status") not in {"completed", "expired", "cancelled"}:
        return 0
    if shard.get("materialized_at"):
        return 0
    if not shard.get("output_file_id") and not shard.get("error_file_id"):
        return 0

    manifest = load_manifest(Path(shard["manifest_path"]))
    materialized = 0

    if shard.get("output_file_id"):
        output_text = download_file_content(client, shard["output_file_id"])
        artifact_path = paths["artifacts"] / f"{shard['shard_id']}.output.jsonl"
        artifact_path.write_text(output_text, encoding="utf-8")
        for line in output_text.splitlines():
            item = json.loads(line)
            custom_id = item["custom_id"]
            meta = manifest.get(custom_id)
            if not meta:
                continue
            body = ((item.get("response") or {}).get("body") or {})
            output_text_body = extract_output_text_from_response_body(body)
            if not output_text_body:
                continue
            try:
                payload = json.loads(output_text_body)
                parsed = ProductKnowledgeFetchedOutput.model_validate(payload)
            except Exception as exc:
                with paths["errors"].open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps({
                        "custom_id": custom_id,
                        "product_id": meta["product_id"],
                        "type": "parse_error",
                        "message": str(exc),
                    }, ensure_ascii=True) + "\n")
                continue

            source_urls = extract_source_urls_from_response_items(body.get("output"))
            fetched_dict = parsed.model_dump()
            production_dict = dict(fetched_dict)
            production_dict.pop("source_urls", None)
            evidence_dict = {
                "product_id": meta["product_id"],
                "product_title": meta.get("product_title"),
                "canonical_name": fetched_dict.get("canonical_name"),
                "source_urls": source_urls,
            }

            output_path = product_output_path(paths["products"], meta["index"], meta["product_id"])
            evidence_path = evidence_output_path(paths["evidence"], meta["index"], meta["product_id"])
            write_json_atomic(output_path, production_dict)
            write_json_atomic(evidence_path, evidence_dict)
            materialized += 1

    if shard.get("error_file_id"):
        error_text = download_file_content(client, shard["error_file_id"])
        artifact_path = paths["artifacts"] / f"{shard['shard_id']}.errors.jsonl"
        artifact_path.write_text(error_text, encoding="utf-8")
        with paths["errors"].open("a", encoding="utf-8") as handle:
            handle.write(error_text)
            if error_text and not error_text.endswith("\n"):
                handle.write("\n")

    shard["materialized_count"] = materialized
    shard["materialized_at"] = datetime.now().isoformat()
    save_state(paths["state"], state)
    print(f"{shard['shard_id']}: materialized {materialized} product(s)")
    return materialized


def materialize_batches(
    args,
    *,
    client: OpenAI | None = None,
    state: Dict | None = None,
    paths: Dict[str, Path] | None = None,
    conn: sqlite3.Connection | None = None,
) -> int:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY")
    client = client or OpenAI(api_key=api_key)
    owns_conn = conn is None
    conn = conn or get_db()

    paths = paths or ensure_run_dirs(args.run_name)
    state = state or load_state(paths["state"])

    total_materialized = 0
    for shard in state.get("shards", []):
        if shard.get("status") not in {"completed", "expired", "cancelled"}:
            continue
        if shard.get("materialized_at"):
            continue
        if not shard.get("output_file_id") and not shard.get("error_file_id"):
            continue
        manifest = load_manifest(Path(shard["manifest_path"]))
        materialized = 0

        if shard.get("output_file_id"):
            output_text = download_file_content(client, shard["output_file_id"])
            artifact_path = paths["artifacts"] / f"{shard['shard_id']}.output.jsonl"
            artifact_path.write_text(output_text, encoding="utf-8")
            for line in output_text.splitlines():
                item = json.loads(line)
                custom_id = item["custom_id"]
                meta = manifest.get(custom_id)
                if not meta:
                    continue
                body = ((item.get("response") or {}).get("body") or {})
                output_text_body = extract_output_text_from_response_body(body)
                if not output_text_body:
                    continue
                try:
                    payload = json.loads(output_text_body)
                    parsed = ProductKnowledgeFetchedOutput.model_validate(payload)
                except Exception as exc:
                    with paths["errors"].open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps({
                            "custom_id": custom_id,
                            "product_id": meta["product_id"],
                            "type": "parse_error",
                            "message": str(exc),
                        }, ensure_ascii=True) + "\n")
                    mark_product_failed_db(conn, custom_id, "failed_parse")
                    continue

                source_urls = extract_source_urls_from_response_items(body.get("output"))
                fetched_dict = parsed.model_dump()
                production_dict = dict(fetched_dict)
                production_dict.pop("source_urls", None)
                evidence_dict = {
                    "product_id": meta["product_id"],
                    "product_title": meta.get("product_title"),
                    "canonical_name": fetched_dict.get("canonical_name"),
                    "source_urls": source_urls,
                }

                output_path = product_output_path(paths["products"], meta["index"], meta["product_id"])
                evidence_path = evidence_output_path(paths["evidence"], meta["index"], meta["product_id"])
                write_json_atomic(output_path, production_dict)
                write_json_atomic(evidence_path, evidence_dict)
                mark_product_materialized_db(conn, custom_id, output_path, evidence_path)
                materialized += 1

        if shard.get("error_file_id"):
            error_text = download_file_content(client, shard["error_file_id"])
            artifact_path = paths["artifacts"] / f"{shard['shard_id']}.errors.jsonl"
            artifact_path.write_text(error_text, encoding="utf-8")
            with paths["errors"].open("a", encoding="utf-8") as handle:
                handle.write(error_text)
                if error_text and not error_text.endswith("\n"):
                    handle.write("\n")
            for line in error_text.splitlines():
                item = json.loads(line)
                custom_id = item.get("custom_id")
                response = item.get("response") or {}
                body = response.get("body") or {}
                error = body.get("error") or {}
                error_code = error.get("code")
                if custom_id:
                    status = "failed_remote"
                    if error_code == "insufficient_quota":
                        status = "failed_quota"
                    mark_product_failed_db(conn, custom_id, status)

        shard["materialized_count"] = materialized
        shard["materialized_at"] = utc_now()
        upsert_shard_db(conn, state["run_name"], shard)
        conn.commit()
        save_state(paths["state"], state)
        print(f"{shard['shard_id']}: materialized {materialized} product(s)")
        total_materialized += materialized
    if owns_conn:
        conn.close()
    return total_materialized


def status(args) -> None:
    paths = ensure_run_dirs(args.run_name)
    state = load_state(paths["state"])
    products_count = sum(1 for _ in paths["products"].glob("*.json"))
    evidence_count = sum(1 for _ in paths["evidence"].glob("*.json"))
    conn = get_db()
    db_counts = {
        row["status"]: row["count"]
        for row in conn.execute(
            "SELECT status, COUNT(*) AS count FROM products WHERE run_name = ? GROUP BY status",
            (args.run_name,),
        ).fetchall()
    }
    conn.close()
    print(f"run_name={args.run_name}")
    print(f"products={products_count}")
    print(f"evidence={evidence_count}")
    print(f"db_status_counts={db_counts}")
    completed_unmaterialized = 0
    for shard in state.get("shards", []):
        if shard.get("status") == "completed" and not shard.get("materialized_at"):
            completed_unmaterialized += 1
        print(
            f"{shard['shard_id']} status={shard.get('status')} "
            f"batch_id={shard.get('batch_id')} "
            f"materialized={shard.get('materialized_count', 0)}/{shard.get('request_count')}"
        )
    print(f"completed_unmaterialized_shards={completed_unmaterialized}")


def sync_db(args) -> None:
    run_names: List[str]
    if args.run_name:
        run_names = [args.run_name]
    else:
        run_names = sorted(
            path.name
            for path in RUNS_DIR.iterdir()
            if path.is_dir() and (path / "state.json").exists()
        )

    conn = get_db()
    try:
        for run_name in run_names:
            paths = ensure_run_dirs(run_name)
            state_path = paths["state"]
            if not state_path.exists():
                continue
            state = load_state(state_path)
            sync_run_to_db(paths, state)
            for shard in state.get("shards", []):
                manifest = shard.get("requests") or []
                for item in manifest:
                    output_path = product_output_path(paths["products"], item["index"], item["product_id"])
                    evidence_path = evidence_output_path(paths["evidence"], item["index"], item["product_id"])
                    if output_path.exists() and evidence_path.exists():
                        mark_product_materialized_db(conn, item["custom_id"], output_path, evidence_path)
            conn.commit()
            count = conn.execute(
                "SELECT COUNT(*) FROM products WHERE run_name = ? AND status = 'materialized'",
                (run_name,),
            ).fetchone()[0]
            print(f"{run_name}: synced, materialized_products={count}")
    finally:
        conn.close()


def abandon_prepared(args) -> None:
    conn = get_db()
    try:
        prepared_shards = conn.execute(
            """
            SELECT shard_id FROM shards
            WHERE run_name = ? AND status = 'prepared' AND batch_id IS NULL
            """,
            (args.run_name,),
        ).fetchall()
        shard_ids = [row[0] for row in prepared_shards]
        if not shard_ids:
            print(f"{args.run_name}: no prepared shards to abandon")
            return
        conn.execute(
            """
            UPDATE shards
            SET status = 'abandoned', updated_at = ?
            WHERE run_name = ? AND status = 'prepared' AND batch_id IS NULL
            """,
            (utc_now(), args.run_name),
        )
        conn.execute(
            f"""
            UPDATE products
            SET status = 'abandoned', updated_at = ?
            WHERE run_name = ? AND shard_id IN ({','.join('?' for _ in shard_ids)})
            """,
            [utc_now(), args.run_name, *shard_ids],
        )
        conn.commit()
        print(f"{args.run_name}: abandoned {len(shard_ids)} prepared shard(s)")
    finally:
        conn.close()


def export_failed_product_ids(args) -> None:
    conn = get_db()
    try:
        statuses = [status.strip() for status in args.statuses.split(",") if status.strip()]
        rows = conn.execute(
            f"""
            SELECT DISTINCT product_id
            FROM products
            WHERE run_name IN ({','.join('?' for _ in args.run_names)})
              AND status IN ({','.join('?' for _ in statuses)})
            ORDER BY product_id
            """,
            [*args.run_names, *statuses],
        ).fetchall()
        output_path = Path(args.output)
        output_path.write_text(
            "\n".join(row[0] for row in rows) + ("\n" if rows else ""),
            encoding="utf-8",
        )
        print(f"{len(rows)}")
        print(output_path)
    finally:
        conn.close()


def smoke(args) -> None:
    prepare_batches(args)
    submit_batches(args)

    deadline = time.time() + args.wait_seconds
    while time.time() < deadline:
        poll_batches(args)
        paths = ensure_run_dirs(args.run_name)
        state = load_state(paths["state"])
        statuses = {shard.get("status") for shard in state.get("shards", [])}
        if statuses and statuses.issubset({"completed", "expired", "cancelled", "failed"}):
            break
        time.sleep(args.poll_interval)

    materialize_batches(args)
    status(args)


def build_parser():
    parser = argparse.ArgumentParser(description="Batch-mode OpenAI Responses runner for Minutes product enrichment")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(p):
        p.add_argument("--run-name", required=True, help="Run directory name under minutes-agent/runs")
        p.add_argument("--model", default="gpt-5.4-mini-2026-03-17", help="OpenAI model name")
        p.add_argument("--reasoning-effort", default="none", help="OpenAI reasoning effort, typically none")
        p.add_argument("--mode", default="all", choices=("representative", "diverse", "all"))
        p.add_argument("--limit", type=int, default=10)
        p.add_argument("--offset", type=int, default=0, help="Skip this many ready+discoverable rows before selecting")
        p.add_argument("--shard-size", type=int, default=1000)
        p.add_argument("--exclude-product-ids-file", default="", help="Optional newline-delimited product_id file to exclude from preparation")
        p.add_argument("--include-product-ids-file", default="", help="Optional newline-delimited product_id file to prepare explicitly")
        p.add_argument("--resume", action="store_true")

    prepare_p = subparsers.add_parser("prepare")
    add_common(prepare_p)
    prepare_p.set_defaults(func=prepare_batches)

    submit_p = subparsers.add_parser("submit")
    submit_p.add_argument("--run-name", required=True)
    submit_p.add_argument("--max-shards", type=int, default=0, help="Submit at most this many prepared shards in this invocation")
    submit_p.set_defaults(func=submit_batches)

    poll_p = subparsers.add_parser("poll")
    poll_p.add_argument("--run-name", required=True)
    poll_p.set_defaults(func=poll_batches)

    materialize_p = subparsers.add_parser("materialize")
    materialize_p.add_argument("--run-name", required=True)
    materialize_p.set_defaults(func=materialize_batches)

    status_p = subparsers.add_parser("status")
    status_p.add_argument("--run-name", required=True)
    status_p.set_defaults(func=status)

    sync_p = subparsers.add_parser("sync-db")
    sync_p.add_argument("--run-name", default="", help="Optional run to sync; omit to sync all runs with state.json")
    sync_p.set_defaults(func=sync_db)

    abandon_p = subparsers.add_parser("abandon-prepared")
    abandon_p.add_argument("--run-name", required=True)
    abandon_p.set_defaults(func=abandon_prepared)

    export_failed_p = subparsers.add_parser("export-failed-product-ids")
    export_failed_p.add_argument("--run-names", nargs="+", required=True)
    export_failed_p.add_argument("--statuses", default="failed_quota,failed_remote")
    export_failed_p.add_argument("--output", required=True)
    export_failed_p.set_defaults(func=export_failed_product_ids)

    smoke_p = subparsers.add_parser("smoke")
    add_common(smoke_p)
    smoke_p.add_argument("--wait-seconds", type=int, default=120)
    smoke_p.add_argument("--poll-interval", type=int, default=10)
    smoke_p.set_defaults(func=smoke)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
