"""Agent-owned analytical-category jumps for exploratory profile queries."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


RESOURCE_PATH = Path(__file__).resolve().parent / "resources" / "category_jumps.v1.json"
WORD_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class JumpTarget:
    route_id: str
    source_categories: tuple[str, ...]
    target_category: str
    intent: str
    required_query_terms: tuple[str, ...]
    allowed_source_terms: tuple[str, ...]
    priority: int
    route_order: int
    target_order: int

    def prompt_dict(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "source_categories": list(self.source_categories),
            "target_category": self.target_category,
            "intent": self.intent,
            "required_product_query_terms": list(self.required_query_terms),
            "allowed_source_terms": list(self.allowed_source_terms),
        }


@dataclass(frozen=True)
class CategoryJumpGraph:
    version: str
    max_routes_per_profile: int
    targets: tuple[JumpTarget, ...]

    def select(self, observed_categories: Iterable[str]) -> list[JumpTarget]:
        observed_by_key = {
            str(category).strip().casefold(): str(category).strip()
            for category in observed_categories
            if str(category).strip()
        }
        observed_keys = set(observed_by_key)
        eligible = [
            target
            for target in self.targets
            if all(source.casefold() in observed_keys for source in target.source_categories)
            and target.target_category.casefold() not in observed_keys
        ]
        eligible.sort(
            key=lambda target: (
                -len(target.source_categories),
                target.target_order,
                -target.priority,
                target.route_order,
            )
        )

        selected: list[JumpTarget] = []
        seen_targets: set[str] = set()
        for target in eligible:
            key = target.target_category.casefold()
            if key in seen_targets:
                continue
            selected.append(target)
            seen_targets.add(key)
            if len(selected) >= self.max_routes_per_profile:
                break
        return selected


def _non_empty_strings(values: Any, label: str) -> tuple[str, ...]:
    if not isinstance(values, list):
        raise ValueError(f"{label} must be an array")
    result = tuple(str(value).strip() for value in values if str(value).strip())
    if not result:
        raise ValueError(f"{label} must contain at least one value")
    return result


@lru_cache(maxsize=1)
def load_category_jump_graph(path: Path = RESOURCE_PATH) -> CategoryJumpGraph:
    payload = json.loads(path.read_text(encoding="utf-8"))
    version = str(payload.get("version") or "").strip()
    limit = int(payload.get("max_routes_per_profile") or 0)
    if not version:
        raise ValueError("category-jump graph version is required")
    if limit < 1:
        raise ValueError("max_routes_per_profile must be positive")

    targets: list[JumpTarget] = []
    route_ids: set[str] = set()
    for route_order, route in enumerate(payload.get("routes") or []):
        route_id = str(route.get("route_id") or "").strip()
        if not route_id or route_id in route_ids:
            raise ValueError(f"invalid or duplicate route_id: {route_id!r}")
        route_ids.add(route_id)
        sources = _non_empty_strings(route.get("source_categories"), f"{route_id}.source_categories")
        priority = int(route.get("priority") or 0)
        for target_order, target in enumerate(route.get("targets") or []):
            target_category = str(target.get("category") or "").strip()
            intent = str(target.get("intent") or "").strip()
            required_terms = _non_empty_strings(
                target.get("required_query_terms"),
                f"{route_id}.{target_category}.required_query_terms",
            )
            allowed_source_terms = tuple(
                str(value).strip().lower()
                for value in target.get("allowed_source_terms") or []
                if str(value).strip()
            )
            if not target_category or not intent:
                raise ValueError(f"{route_id} target category and intent are required")
            if target_category.casefold() in {source.casefold() for source in sources}:
                raise ValueError(f"{route_id} cannot jump back into source category {target_category}")
            targets.append(
                JumpTarget(
                    route_id=route_id,
                    source_categories=sources,
                    target_category=target_category,
                    intent=intent,
                    required_query_terms=required_terms,
                    allowed_source_terms=allowed_source_terms,
                    priority=priority,
                    route_order=route_order,
                    target_order=target_order,
                )
            )
    if not targets:
        raise ValueError("category-jump graph has no targets")
    return CategoryJumpGraph(version=version, max_routes_per_profile=limit, targets=tuple(targets))


def prepare_exploratory_prompt(input_dict: Mapping[str, Any]) -> dict[str, Any]:
    summaries = {
        str(category).strip(): " ".join(str(summary or "").split())
        for category, summary in (input_dict.get("category_summaries") or {}).items()
        if str(category).strip() and str(summary or "").strip()
    }
    graph = load_category_jump_graph()
    selected = graph.select(summaries)
    return {
        "category_summaries": summaries,
        "category_jump_graph_version": graph.version,
        "approved_category_jumps": [target.prompt_dict() for target in selected],
    }


def _query_contains_required_term(queries: Sequence[str], terms: Sequence[str]) -> bool:
    normalized_queries = [" ".join(WORD_RE.findall(str(query).lower())) for query in queries]
    normalized_terms = [" ".join(WORD_RE.findall(str(term).lower())) for term in terms]
    return any(term and term in query for term in normalized_terms for query in normalized_queries)


def _source_terms(sources: Sequence[str]) -> set[str]:
    tokens = {
        token
        for source in sources
        for token in WORD_RE.findall(re.sub(r"(?<=[a-z])(?=[A-Z])", " ", source).lower())
        if len(token) > 3
    }
    return tokens | {token[:-1] for token in tokens if token.endswith("s") and len(token) > 4}


def validate_exploratory_output(result: Any, prompt_payload: Mapping[str, Any]) -> Any:
    result_dict = result.model_dump() if hasattr(result, "model_dump") else dict(result)
    approved_rows = prompt_payload.get("approved_category_jumps") or []
    approved = {
        (str(row["route_id"]), str(row["target_category"])): row
        for row in approved_rows
    }
    output_rows = result_dict.get("exploratory_routes") or []

    if not approved:
        if output_rows:
            raise ValueError("no category jumps were approved, so exploratory_routes must be empty")
        return result
    if len(output_rows) != len(approved):
        raise ValueError(
            f"expected exactly {len(approved)} approved exploratory routes, got {len(output_rows)}"
        )

    seen: set[tuple[str, str]] = set()
    for row in output_rows:
        key = (str(row.get("route_id") or ""), str(row.get("target_category") or ""))
        approved_row = approved.get(key)
        if approved_row is None:
            raise ValueError(f"unapproved exploratory route: {key}")
        if key in seen:
            raise ValueError(f"duplicate exploratory route: {key}")
        seen.add(key)
        expected_sources = list(approved_row["source_categories"])
        if list(row.get("source_categories") or []) != expected_sources:
            raise ValueError(f"route {key} must preserve source_categories {expected_sources}")
        product_queries = [str(value) for value in row.get("product_queries") or []]
        if not _query_contains_required_term(
            product_queries,
            approved_row.get("required_product_query_terms") or [],
        ):
            raise ValueError(
                f"route {key} product_queries do not name the approved target product space"
            )
        forbidden = _source_terms(expected_sources)
        forbidden -= {
            str(value).strip().lower()
            for value in approved_row.get("allowed_source_terms") or []
        }
        product_tokens = set(WORD_RE.findall(" ".join(product_queries).lower()))
        leaked = sorted(forbidden & product_tokens)
        if leaked:
            raise ValueError(
                f"route {key} product_queries repeat source-category terms instead of the target: {leaked}"
            )
    if seen != set(approved):
        raise ValueError("LLM output omitted one or more approved exploratory routes")
    return result
