"""Validate structured dimension coverage and return a single paragraph."""

from dimension_reference import enrich_dimension_summary_payload
from models import DimensionDescriptionsOutput, DimensionSummaryOutput


def _normalize_text(text):
    return " ".join(text.split())


async def summarize_dimensions(task, data):
    payload = enrich_dimension_summary_payload(data)
    payload["dimensions"] = [
        {
            "input_index": index,
            "dimension_name": item["key"],
            "selected_value": item.get("value"),
        }
        for index, item in enumerate(data["dimensions"])
    ]
    expected = set(range(len(data["dimensions"])))
    # One call for the full list, with one bounded whole-request retry for invalid structured output.
    for attempt in range(2):
        result = await task.do(payload)
        try:
            raw = result.model_dump() if hasattr(result, "model_dump") else result
            parsed = DimensionDescriptionsOutput.model_validate(raw)
            indices = [item.input_index for item in parsed.descriptions]
            if len(indices) != len(expected) or set(indices) != expected:
                raise ValueError("Each input_index must occur exactly once")
            descriptions = {}
            errors = []
            for item in parsed.descriptions:
                combined_description = _normalize_text(item.description)
                if not combined_description:
                    errors.append(f"input_index {item.input_index} is missing its description")
                descriptions[item.input_index] = combined_description
            if errors:
                raise ValueError("; ".join(errors))
        except (ValueError, TypeError) as exc:
            if attempt:
                raise ValueError(f"Failed to generate complete dimension descriptions: {exc}")
            payload = {
                **payload,
                "coverage_correction": (
                    f"The previous output was invalid: {exc}. Return every input_index from 0 to "
                    f"{len(expected) - 1} exactly once. For each index, provide one concise description "
                    "that explicitly preserves the broader dimension concept and explains the named selected "
                    "value within it; a general-only or value-only explanation is invalid."
                ),
            }
            continue
        sentences = [descriptions[index] for index in range(len(expected))]
        sentences = [text if text.endswith((".", "!", "?")) else text + "." for text in sentences]
        return DimensionSummaryOutput(summary=" ".join(sentences))
