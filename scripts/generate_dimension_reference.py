"""Refresh dimension descriptions from Markdown, preserving curated value explanations."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "dimesion-values.md"
DESTINATION = ROOT / "data" / "dimension-reference.json"


def parse_dimension_reference(markdown):
    reference = {}
    in_dimension_table = False
    for line in markdown.splitlines():
        if line == "| dimension | values | description |":
            in_dimension_table = True
            continue
        if in_dimension_table:
            if line.startswith("| :----"):
                continue
            if line.startswith("| `"):
                cells = [cell.strip() for cell in line.strip("|").split("|")]
                if len(cells) != 3:
                    raise ValueError("Expected dimension, values and description columns")
                name = cells[0].strip("`")
                if name in reference:
                    raise ValueError(f"Duplicate dimension: {name}")
                reference[name] = {
                    "description": cells[2],
                }
                continue
            in_dimension_table = False
    if not reference:
        raise ValueError("No dimensions found")
    return reference


def main():
    reference = parse_dimension_reference(SOURCE.read_text(encoding="utf-8"))
    existing = json.loads(DESTINATION.read_text(encoding="utf-8")) if DESTINATION.exists() else {}
    for name, entry in reference.items():
        explanations = existing.get(name, {}).get("value_explanations")
        if explanations:
            entry["value_explanations"] = explanations
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_text(json.dumps(reference, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {DESTINATION}")


if __name__ == "__main__":
    main()
