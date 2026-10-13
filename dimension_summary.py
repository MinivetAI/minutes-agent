"""Validate structured dimension coverage and return a single paragraph."""

from functools import lru_cache
import json
from pathlib import Path
import re

from models import DimensionDescriptionsOutput, DimensionSummaryOutput


REFERENCE_PATH = Path(__file__).resolve().parent / "data" / "dimension-reference.json"


@lru_cache(maxsize=1)
def _load_reference():
    return json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))


def _enrich_payload(data):
    reference = _load_reference()
    dimensions = []
    unknown_names = []
    for index, item in enumerate(data["dimensions"]):
        name, value = item["key"], item.get("value")
        entry = reference.get(name)
        enriched = {
            "input_index": index,
            "dimension_name": name,
            "selected_value": value,
        }
        if entry:
            enriched["dimension_description"] = entry["description"]
            explanation = entry.get("value_explanations", {}).get(value)
            if explanation:
                enriched["selected_value_description"] = explanation
        elif name not in unknown_names:
            unknown_names.append(name)
        dimensions.append(enriched)
    return {
        "dimensions": dimensions,
        "unknown_dimension_names": unknown_names,
    }


def _normalize_text(text):
    return " ".join(text.split())


def _is_single_sentence(text):
    body = text.rstrip(".!?")
    return re.search(r"[.!?]\s+[A-Z]", body) is None


async def summarize_dimensions(task, data):
    payload = _enrich_payload(data)
    expected_indices = list(range(len(data["dimensions"])))
    max_sentences = min(4, len(expected_indices))
    # One call for the full list, with one bounded whole-request retry for invalid structured output.
    for attempt in range(2):
        result = await task.do(payload)
        try:
            raw = result.model_dump() if hasattr(result, "model_dump") else result
            parsed = DimensionDescriptionsOutput.model_validate(raw)
            if len(parsed.sentences) > max_sentences:
                raise ValueError(f"Use at most {max_sentences} sentences for this request")
            indices = [index for sentence in parsed.sentences for index in sentence.input_indices]
            if indices != expected_indices:
                raise ValueError(f"Expected input_indices {expected_indices}, received {indices}")
            sentences = []
            errors = []
            for sentence_number, item in enumerate(parsed.sentences, start=1):
                description = _normalize_text(item.description)
                if not description:
                    errors.append(f"sentence {sentence_number} is empty")
                elif not _is_single_sentence(description):
                    errors.append(f"sentence {sentence_number} contains multiple sentences")
                sentences.append(description)
            if errors:
                raise ValueError("; ".join(errors))
        except (ValueError, TypeError) as exc:
            if attempt:
                raise ValueError(f"Failed to generate complete dimension descriptions: {exc}")
            payload = {
                **payload,
                "coverage_correction": (
                    f"The previous output was invalid: {exc}. Return every input_index from 0 to "
                    f"{len(expected_indices) - 1} exactly once across 1 to {max_sentences} sentences. Each sentence must "
                    "list the input_indices it covers. Preserve every broader dimension concept and explain "
                    "every named selected value; a general-only or value-only explanation is invalid."
                ),
            }
            continue
        sentences = [text if text.endswith((".", "!", "?")) else text + "." for text in sentences]
        return DimensionSummaryOutput(summary=" ".join(sentences))
