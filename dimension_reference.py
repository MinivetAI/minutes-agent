"""Attach server-owned dimension definitions to summary requests."""

from functools import lru_cache
import json
from pathlib import Path


REFERENCE_PATH = Path(__file__).resolve().parent / "data" / "dimension-reference.json"


@lru_cache(maxsize=1)
def load_dimension_reference():
    return json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))


def enrich_dimension_summary_payload(data):
    reference = load_dimension_reference()
    names = list(dict.fromkeys(item["key"] for item in data["dimensions"]))
    # Any unmatched name needs the full reference, including mixed known/unknown requests.
    selected = {name: reference[name] for name in names} if all(name in reference for name in names) else reference
    # Copy entries so selected-value context never leaks into cached definitions or other requests.
    selected = {name: {"description": entry["description"]} for name, entry in selected.items()}
    for item in data["dimensions"]:
        name, value = item["key"], item.get("value")
        explanation = reference.get(name, {}).get("value_explanations", {}).get(value)
        if explanation and name in selected:
            selected[name].setdefault("selected_value_descriptions", {})[value] = explanation
    return {
        **data,
        "dimension_reference": json.dumps(selected, ensure_ascii=False),
    }
