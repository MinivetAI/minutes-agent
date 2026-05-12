import argparse
import shutil
from pathlib import Path


ROOT = Path("/home/aditya/Minivet/minutes/minutes-agent")
RUNS = ROOT / "runs"


def parse_product_id(path: Path) -> str | None:
    parts = path.stem.split("_", 1)
    if len(parts) != 2:
        return None
    return parts[1]


def collect_latest_sources() -> dict[str, Path]:
    chosen: dict[str, Path] = {}
    for products_dir in sorted(RUNS.glob("*/products")):
        for path in sorted(products_dir.glob("*.json")):
            product_id = parse_product_id(path)
            if not product_id:
                continue
            existing = chosen.get(product_id)
            if existing is None or path.stat().st_mtime_ns >= existing.stat().st_mtime_ns:
                chosen[product_id] = path
    return chosen


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy deduplicated product JSONs into one directory keyed by product_id")
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "all_products_by_product_id"),
        help="Destination directory for copied product JSONs",
    )
    parser.add_argument(
        "--expected-count",
        type=int,
        default=76342,
        help="Expected unique product count; fail if the consolidated directory does not match",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    chosen = collect_latest_sources()
    for product_id, source_path in chosen.items():
        dest_path = output_dir / f"{product_id}.json"
        shutil.copy2(source_path, dest_path)

    final_count = len(list(output_dir.glob("*.json")))
    print(f"copied_unique={len(chosen)}")
    print(f"output_count={final_count}")
    print(f"output_dir={output_dir}")
    if final_count != args.expected_count:
        raise SystemExit(
            f"expected {args.expected_count} consolidated files, found {final_count}"
        )


if __name__ == "__main__":
    main()
