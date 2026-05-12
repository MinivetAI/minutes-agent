import argparse
import math
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from openai_batch_products import (
    RUNS_DIR,
    get_db,
    load_all_rows,
    poll_batches,
    prepare_batches,
    submit_batches,
)


ACTIVE_PRODUCT_STATUSES = ("prepared", "validating", "in_progress", "finalizing", "completed")
FAILED_PRODUCT_STATUSES = ("failed_quota", "failed_remote", "failed_parse")
ACTIVE_SHARD_STATUSES = ("validating", "in_progress", "finalizing")


def now_slug() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def load_eligible_product_ids() -> list[str]:
    rows = load_all_rows(None, offset=0)
    return [row["product_id"] for row in rows]


def distinct_ids_for_statuses(conn, statuses: tuple[str, ...]) -> set[str]:
    placeholders = ",".join("?" for _ in statuses)
    rows = conn.execute(
        f"SELECT DISTINCT product_id FROM products WHERE status IN ({placeholders})",
        statuses,
    ).fetchall()
    return {row[0] for row in rows}


def get_retryable_ids(conn, cooldown_seconds: int) -> list[str]:
    placeholders = ",".join("?" for _ in FAILED_PRODUCT_STATUSES)
    cutoff = datetime.now() - timedelta(seconds=cooldown_seconds)
    rows = conn.execute(
        f"""
        SELECT product_id, MAX(updated_at) AS updated_at
        FROM products
        WHERE status IN ({placeholders})
        GROUP BY product_id
        ORDER BY updated_at ASC, product_id ASC
        """,
        FAILED_PRODUCT_STATUSES,
    ).fetchall()
    materialized = distinct_ids_for_statuses(conn, ("materialized",))
    active = distinct_ids_for_statuses(conn, ACTIVE_PRODUCT_STATUSES)
    retryable: list[str] = []
    for row in rows:
        product_id = row[0]
        updated_at = row[1]
        if product_id in materialized or product_id in active:
            continue
        if updated_at:
            try:
                updated_dt = datetime.fromisoformat(updated_at)
            except ValueError:
                updated_dt = datetime.min
            if updated_dt > cutoff:
                continue
        retryable.append(product_id)
    return retryable


def get_fresh_remaining_ids(conn, eligible_ids: list[str]) -> list[str]:
    materialized = distinct_ids_for_statuses(conn, ("materialized",))
    active = distinct_ids_for_statuses(conn, ACTIVE_PRODUCT_STATUSES)
    retryable = set(get_retryable_ids(conn, cooldown_seconds=0))
    excluded = materialized | active | retryable
    return [product_id for product_id in eligible_ids if product_id not in excluded]


def get_runs_needing_poll(conn) -> list[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT run_name
        FROM shards
        WHERE batch_id IS NOT NULL
          AND (
            status IN ('validating', 'in_progress', 'finalizing')
            OR (status = 'completed' AND materialized_at IS NULL)
          )
        ORDER BY run_name
        """
    ).fetchall()
    return [row[0] for row in rows]


def count_active_shards(conn) -> int:
    row = conn.execute(
        f"SELECT COUNT(*) FROM shards WHERE status IN ({','.join('?' for _ in ACTIVE_SHARD_STATUSES)})",
        ACTIVE_SHARD_STATUSES,
    ).fetchone()
    return int(row[0])


def count_materialized_unique(conn) -> int:
    row = conn.execute(
        "SELECT COUNT(DISTINCT product_id) FROM products WHERE status = ?",
        ("materialized",),
    ).fetchone()
    return int(row[0])


def create_include_file(run_name: str, product_ids: list[str]) -> Path:
    run_root = RUNS_DIR / run_name
    run_root.mkdir(parents=True, exist_ok=True)
    include_path = run_root / "include_product_ids.txt"
    include_path.write_text("\n".join(product_ids) + "\n", encoding="utf-8")
    return include_path


def launch_run(
    *,
    run_name: str,
    product_ids: list[str],
    model: str,
    reasoning_effort: str,
    shard_size: int,
) -> None:
    if not product_ids:
        return
    include_path = create_include_file(run_name, product_ids)
    prepare_args = SimpleNamespace(
        run_name=run_name,
        model=model,
        reasoning_effort=reasoning_effort,
        mode="all",
        limit=len(product_ids),
        offset=0,
        shard_size=shard_size,
        exclude_product_ids_file="",
        include_product_ids_file=str(include_path),
        resume=True,
    )
    prepare_batches(prepare_args)
    submit_args = SimpleNamespace(run_name=run_name, max_shards=0)
    submit_batches(submit_args)


def print_summary(conn, eligible_total: int) -> None:
    materialized = count_materialized_unique(conn)
    retryable = len(get_retryable_ids(conn, cooldown_seconds=0))
    active = len(distinct_ids_for_statuses(conn, ACTIVE_PRODUCT_STATUSES))
    remaining = eligible_total - materialized
    active_shards = count_active_shards(conn)
    print(
        f"summary materialized={materialized} remaining={remaining} "
        f"active_products={active} retryable={retryable} active_shards={active_shards}"
    )


def orchestrate(args) -> None:
    eligible_ids = load_eligible_product_ids()
    eligible_total = len(eligible_ids)
    print(f"eligible_catalog_products={eligible_total}")

    while True:
        conn = get_db()
        try:
            runs_to_poll = get_runs_needing_poll(conn)
        finally:
            conn.close()

        for run_name in runs_to_poll:
            poll_batches(SimpleNamespace(run_name=run_name))

        conn = get_db()
        try:
            materialized = count_materialized_unique(conn)
            remaining = eligible_total - materialized
            retryable = get_retryable_ids(conn, cooldown_seconds=args.retry_cooldown_seconds)
            fresh = get_fresh_remaining_ids(conn, eligible_ids)
            active_shards = count_active_shards(conn)
            active_capacity = max(0, args.max_active_shards - active_shards)

            print_summary(conn, eligible_total)

            if remaining <= 0:
                print("All eligible products are complete.")
                return

            if active_capacity > 0:
                shard_capacity_products = active_capacity * args.shard_size

                if retryable:
                    retry_take = min(len(retryable), shard_capacity_products, args.max_retry_products_per_wave)
                    retry_ids = retryable[:retry_take]
                    retry_run_name = f"{args.run_prefix}_retry_{now_slug()}"
                    launch_run(
                        run_name=retry_run_name,
                        product_ids=retry_ids,
                        model=args.model,
                        reasoning_effort=args.reasoning_effort,
                        shard_size=min(args.shard_size, max(1, len(retry_ids))),
                    )
                    shard_capacity_products -= retry_take

                if shard_capacity_products > 0 and fresh:
                    fresh_take = min(len(fresh), shard_capacity_products, args.max_fresh_products_per_wave)
                    fresh_ids = fresh[:fresh_take]
                    fresh_run_name = f"{args.run_prefix}_fresh_{now_slug()}"
                    launch_run(
                        run_name=fresh_run_name,
                        product_ids=fresh_ids,
                        model=args.model,
                        reasoning_effort=args.reasoning_effort,
                        shard_size=args.shard_size,
                    )

        finally:
            conn.close()

        time.sleep(args.poll_interval_seconds)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unattended orchestrator for remaining Minutes product enrichment")
    parser.add_argument("--run-prefix", default="batch_finish_remaining")
    parser.add_argument("--model", default="gpt-5.4-mini-2026-03-17")
    parser.add_argument("--reasoning-effort", default="none")
    parser.add_argument("--shard-size", type=int, default=500)
    parser.add_argument("--max-active-shards", type=int, default=40)
    parser.add_argument("--max-fresh-products-per-wave", type=int, default=20000)
    parser.add_argument("--max-retry-products-per-wave", type=int, default=500)
    parser.add_argument("--retry-cooldown-seconds", type=int, default=900)
    parser.add_argument("--poll-interval-seconds", type=int, default=300)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    orchestrate(args)


if __name__ == "__main__":
    main()
