import re
from enum import Enum
from typing import Any, Dict

import instructions
from category_jumps import (
    load_category_jump_graph,
    prepare_exploratory_prompt,
    validate_exploratory_output,
)
from instructions import (
    FETCH_PRODUCT_KNOWLEDGE,
    MISSION_SEMANTIC_DOCUMENT,
    OCCASION_EVENT_OCCURRENCE_SUMMARY,
    PRODUCT_SEMANTIC_PARAGRAPH,
    QUERY_IMPROVEMENT,
    QUERY_PARSE,
    TEST_TASK,
    USER_AGGREGATE_SUMMARY,
    USER_BASKET_DAILY_SUMMARY,
    USER_BASKET_DAYPART_SUMMARY,
    USER_BASKET_MONTHLY_SUMMARY,
    USER_BASKET_PROFILE,
    USER_CATEGORY_DAILY_SUMMARY,
    USER_CATEGORY_DAYPART_SUMMARY,
    USER_CATEGORY_MONTHLY_SUMMARY,
    USER_CATEGORY_PREFERENCE_PROFILE,
    USER_CATEGORY_PROFILE,
    USER_CATEGORY_JUMP_EXPLORATORY_QUERIES,
    USER_CROSS_CATEGORY_PROFILE,
    USER_GLOBAL_PROFILE,
    USER_FEED_QUALITY_REVIEW,
    USER_HOURLY_SUMMARY,
    USER_MISSION_AGGREGATE_SUMMARY,
    USER_MISSION_GLOBAL_PROFILE,
    USER_MISSION_HOURLY_SUMMARY,
    USER_OCCASION_EVENT_PROFILE,
    USER_RUNNING_BASKET_PROFILE_UPDATE,
    USER_RUNNING_CATEGORY_PROFILE_UPDATE,
    USER_RUNNING_PROFILE_UPDATE,
    FEED_LOCATION_CATEGORY_DAILY_SUMMARY,
    FEED_LOCATION_CATEGORY_DAYPART_SUMMARY,
    FEED_LOCATION_CATEGORY_MONTHLY_SUMMARY,
    FEED_LOCATION_CATEGORY_PROFILE,
    FEED_LOCATION_GLOBAL_PROFILE,
    FEED_USER_BASKET_DAILY_SUMMARY,
    FEED_USER_BASKET_DAYPART_SUMMARY,
    FEED_USER_BASKET_MONTHLY_SUMMARY,
    FEED_USER_BASKET_PROFILE,
    FEED_USER_CATEGORY_DAILY_SUMMARY,
    FEED_USER_CATEGORY_DAYPART_SUMMARY,
    FEED_USER_CATEGORY_MONTHLY_SUMMARY,
    FEED_USER_CATEGORY_PROFILE,
    FEED_USER_GLOBAL_PROFILE,
)
from models import (
    ActivitySummary,
    BasketDailySummaryInput,
    BasketDailySummaryOutput,
    BasketDaypartSummaryInput,
    BasketDaypartSummaryOutput,
    BasketMonthlySummaryInput,
    BasketMonthlySummaryOutput,
    BasketProfileInput,
    BasketProfileOutput,
    CategoryDailySummaryInput,
    CategoryDailySummaryOutput,
    CategoryDaypartSummaryInput,
    CategoryDaypartSummaryOutput,
    CategoryMonthlySummaryInput,
    CategoryMonthlySummaryOutput,
    CategoryProfileInput,
    CategoryProfileOutput,
    CategorySummaryExploratoryInput,
    CategorySummaryExploratoryOutput,
    CrossCategoryProfileInput,
    FeedQueries,
    FeedBasketDailyInput,
    FeedBasketDaypartInput,
    FeedBasketMonthlyInput,
    FeedBasketProfileInput,
    FeedCategoryDailyInput,
    FeedCategoryDaypartInput,
    FeedCategoryMonthlyInput,
    FeedCategoryProfileInput,
    FeedGlobalProfileInput,
    FeedGlobalProfileOutput,
    FeedLocationCategoryDailyInput,
    FeedLocationCategoryDaypartInput,
    FeedLocationCategoryMonthlyInput,
    FeedLocationCategoryProfileInput,
    FeedLocationGlobalProfileInput,
    FeedProfileOutput,
    FeedSummaryOutput,
    FeedQualityReviewInput,
    FeedQualityReviewOutput,
    GlobalProfileInput,
    GlobalProfileOutput,
    HourlyActivityInput,
    MissionAggregateSummaryInput,
    MissionAggregateSummaryOutput,
    MissionGlobalProfileInput,
    MissionGlobalProfileOutput,
    MissionHourlySummaryInput,
    MissionHourlySummaryOutput,
    MissionSemanticDocumentInput,
    MissionSemanticDocumentOutput,
    OccasionEventOccurrenceSummaryInput,
    OccasionEventOccurrenceSummaryOutput,
    ProductKnowledgeFetchedOutput,
    ProductKnowledgeInput,
    ProductKnowledgeOutput,
    ProductParagraphInput,
    ProductParagraphOutput,
    QueryImprovement,
    QueryInput,
    QueryParsed,
    RunningBasketProfileInput,
    RunningBasketProfileOutput,
    RunningCategoryProfileInput,
    RunningCategoryProfileOutput,
    RunningProfileInput,
    RunningProfileOutput,
    SummaryAggregationInput,
    TestInput,
    TestResponse,
    UserCategoryProfileInput,
    UserOccasionEventProfileInput,
    UserOccasionEventProfileOutput,
    UserProfile,
)


MARKDOWN_LINK_RE = re.compile(r"\s*\(?\[[^\]]+\]\(https?://[^)]*\)\)?")
BARE_URL_RE = re.compile(r"https?://\S+")
CAMEL_CASE_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def _clean_text(value: Any) -> str:
    text = MARKDOWN_LINK_RE.sub("", str(value or ""))
    text = BARE_URL_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def _scalar(value: Any) -> Any:
    return value.value if isinstance(value, Enum) else value


def _humanize_catalog(value: Any) -> str:
    text = re.sub(r"(?<=[a-z])X(?=[A-Z])", " / ", str(_scalar(value) or ""))
    text = CAMEL_CASE_RE.sub(" ", text).replace("_", " ")
    return re.sub(r"\s+", " ", text).strip()


def _label(key: str) -> str:
    return key.replace("_", " ").strip().capitalize()


def _render_readable(value: Any, indent: int = 0) -> str:
    prefix = " " * indent
    if isinstance(value, dict):
        lines = []
        for key, child in value.items():
            if child in (None, "", [], {}):
                continue
            if isinstance(child, (dict, list)):
                lines.append(f"{prefix}{_label(key)}:")
                rendered = _render_readable(child, indent + 2)
                if rendered:
                    lines.append(rendered)
            else:
                displayed = (
                    _humanize_catalog(child)
                    if key in {"category", "product_type"}
                    else _scalar(child)
                )
                lines.append(f"{prefix}{_label(key)}: {displayed}")
        return "\n".join(lines)
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, dict):
                rendered = _render_readable(item, indent + 2)
                if rendered:
                    first, *rest = rendered.splitlines()
                    lines.append(f"{prefix}- {first.lstrip()}")
                    lines.extend(rest)
            else:
                lines.append(f"{prefix}- {_scalar(item)}")
        return "\n".join(lines)
    return f"{prefix}{_scalar(value)}"


def _without_window_evidence(items: Any) -> Any:
    """window_evidence is bookkeeping the calling system merges in after each
    waterfall call purely to carry cadence/evidence forward to the *next*
    stage (see WindowEvidence in models.py) — no instruction ever asks a
    model to read it, and its purchase_dates list only grows with history.
    Strip it from prior-stage outputs before they're rendered into any
    later-stage prompt, so it never bloats a call it isn't needed for."""
    return [
        {k: v for k, v in item.items() if k != "window_evidence"}
        for item in (items or [])
    ]


def _prepare_product_knowledge(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    category_fields = {
        key: _humanize_catalog(input_dict.get(key))
        for key in (
            "vertical_name",
            "analytic_super_category",
            "analytic_category",
            "analytic_sub_category",
        )
        if input_dict.get(key)
    }
    catalog_facts = {
        "product_title": _clean_text(input_dict.get("product_title")),
        "brand": _clean_text(input_dict.get("brand")),
        **category_fields,
        "description": _clean_text(input_dict.get("description")),
        "rich_product_description": _clean_text(
            input_dict.get("rich_product_description")
        ),
        "variant": _clean_text(input_dict.get("variant")),
        "type": _clean_text(input_dict.get("type")),
        "size": _clean_text(input_dict.get("size")),
        "quantity": _clean_text(input_dict.get("quantity")),
        "pack_of": _clean_text(input_dict.get("pack_of")),
        "material": _clean_text(input_dict.get("material")),
        "color": _clean_text(input_dict.get("color")),
        "ideal_for": _clean_text(input_dict.get("ideal_for")),
        "sales_package": _clean_text(input_dict.get("sales_package")),
    }
    missing_evidence = []
    if not input_dict.get("ideal_for"):
        missing_evidence.append("buyer demographics or household type")
    description_text = " ".join(
        _clean_text(input_dict.get(key))
        for key in ("description", "rich_product_description")
    ).lower()
    if not any(
        token in description_text
        for token in (
            "protein",
            "calcium",
            "nutrition",
            "fat",
            "ingredient",
            "composition",
        )
    ):
        missing_evidence.append("nutrition, ingredients, composition, or benefits")
    missing_evidence.extend(
        [
            "price or value tier",
            "observed buyer intent, urgency, stockout, daypart, or routine",
        ]
    )
    return {
        "catalog_facts": _render_readable(catalog_facts),
        "explicit_grounding_limits": "\n".join(
            f"- Not supplied: {item}" for item in missing_evidence
        ),
    }


def _prepare_category_daypart(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    products = []
    for product in input_dict.get("products") or []:
        products.append(
            {
                "product": product.get("product_name"),
                "category": _humanize_catalog(product.get("category")),
                "brand": product.get("brand"),
                "product_type": _humanize_catalog(product.get("product_type")),
                "quantity": product.get("quantity"),
                "what_it_is": _clean_text(product.get("product_paragraph")),
                "general_product_uses_not_user_intent": _clean_text(
                    product.get("general_product_uses")
                ),
            }
        )
    population_daypart_share = input_dict.get("population_daypart_share") or {}
    return {
        "category": _humanize_catalog(input_dict.get("category")),
        "shopping_moment": (
            f"{input_dict.get('date')} | {_scalar(input_dict.get('daypart'))} | "
            f"{_scalar(input_dict.get('day_type'))}"
        ),
        "population_daypart_baseline": ", ".join(
            f"{daypart}={share}" for daypart, share in population_daypart_share.items()
        ),
        "observed_orders": input_dict.get("order_count") or 0,
        "products_ordered": _render_readable(products),
    }


def _prepare_mission_semantic_document(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    products = input_dict.get("representative_products") or []
    product_block = "\n".join(
        "\n".join(
            line
            for line in (
                f"- product: {product.get('product_name', '')}",
                f"  category: {_humanize_catalog(product.get('category'))}",
                (
                    "  general product uses, not user intent: "
                    f"{_clean_text(product.get('general_product_uses'))}"
                    if product.get("general_product_uses")
                    else ""
                ),
            )
            if line
        )
        for product in products
    )
    return {
        "mission_name": input_dict.get("mission_name", ""),
        "current_description": _clean_text(input_dict.get("current_description")),
        "mission_class": input_dict.get("mission_class", ""),
        "family": input_dict.get("family", ""),
        "dayparts": ", ".join(input_dict.get("dayparts") or []) or "anytime",
        "seasons": ", ".join(input_dict.get("seasons") or []) or "all season",
        "diet_tags": ", ".join(input_dict.get("diet_tags") or []) or "(none)",
        "lifestyle_tags": ", ".join(input_dict.get("lifestyle_tags") or [])
        or "(none)",
        "representative_products": product_block or "(none supplied)",
    }


def _prepare_category_daily(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "category": _humanize_catalog(input_dict.get("category")),
        "date": input_dict.get("date"),
        "weekday_or_weekend": _scalar(input_dict.get("day_type")),
        "daypart_summaries": _render_readable(
            _without_window_evidence(input_dict.get("daypart_summaries"))
        ),
    }


def _prepare_category_monthly(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "category": _humanize_catalog(input_dict.get("category")),
        "month": input_dict.get("month"),
        "daily_summaries": _render_readable(
            _without_window_evidence(input_dict.get("daily_summaries"))
        ),
    }


def _prepare_category_profile(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "category": _humanize_catalog(input_dict.get("category")),
        "recent_daypart_summaries": _render_readable(
            _without_window_evidence(input_dict.get("recent_daypart_summaries"))
        ),
        "recent_daily_summaries": _render_readable(
            _without_window_evidence(input_dict.get("recent_daily_summaries"))
        ),
        "monthly_summaries": _render_readable(
            _without_window_evidence(input_dict.get("monthly_summaries"))
        ),
    }


def _prepare_basket_daypart(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "shopping_moment": (
            f"{input_dict.get('date')} | {_scalar(input_dict.get('daypart'))} | "
            f"{_scalar(input_dict.get('day_type'))}"
        ),
        "complete_orders": _render_readable(input_dict.get("orders") or []),
        "category_pair_evidence_support_confidence_lift": _render_readable(
            input_dict.get("category_pair_evidence") or []
        ),
    }


def _prepare_basket_daily(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "date": input_dict.get("date"),
        "weekday_or_weekend": _scalar(input_dict.get("day_type")),
        "daypart_basket_summaries": _render_readable(
            _without_window_evidence(input_dict.get("daypart_summaries"))
        ),
    }


def _prepare_basket_monthly(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "month": input_dict.get("month"),
        "daily_basket_summaries": _render_readable(
            _without_window_evidence(input_dict.get("daily_summaries"))
        ),
    }


def _prepare_basket_profile(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "recent_daypart_basket_summaries": _render_readable(
            _without_window_evidence(input_dict.get("recent_daypart_summaries"))
        ),
        "recent_daily_basket_summaries": _render_readable(
            _without_window_evidence(input_dict.get("recent_daily_summaries"))
        ),
        "monthly_basket_summaries": _render_readable(
            _without_window_evidence(input_dict.get("monthly_summaries"))
        ),
    }


# Fields the global-profile prompt actually needs from each category profile.
# The rest (per-product/brand/variant/pack-size preference detail, and the
# post-processing-only replenishment/evidence blocks) is useful at the
# category level but is not cross-category synthesis material, and it
# dominates the size of this call's input — a category count near the cap
# (e.g. 40) times the full object risks exceeding the model's context window
# well before the output max_tokens budget is even reached.
_GLOBAL_PROFILE_CATEGORY_FIELDS = (
    "category_name",
    "summary_text",
    "substitution_text",
    "uncertainty_text",
)

# Fields the global-profile prompt actually needs from the one basket_profile.
# `retrieval_text` is the basket profile's own embedding paragraph — the
# global profile writes its own, it never reads this one. `evidence`,
# `user_id`, `artifact_type`, and `updated_at` are post-processing-only
# bookkeeping the model was never asked to use.
_GLOBAL_PROFILE_BASKET_FIELDS = (
    "summary_text",
    "basket_relationships",
    "value_text",
    "basket_size_segment",
    "large_basket_tendency",
    "multi_quantity_tendency",
    "daypart_understanding",
    "day_type_understanding",
    "uncertainty_text",
)


def _prepare_global_profile(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    category_profiles = input_dict.get("category_profiles") or []
    compact_category_profiles = [
        {
            **{field: profile.get(field) for field in _GLOBAL_PROFILE_CATEGORY_FIELDS},
            # Only the brand list, not the full preferences object (products/
            # variants/pack_sizes/ordered_quantities) — this is the one piece
            # of category-level detail shopping_style.brand_loyalty_level
            # actually needs, kept lean for the same context-window reason
            # the rest of this projection is compact.
            "brands": (profile.get("preferences") or {}).get("brands") or [],
        }
        for profile in category_profiles
    ]
    total_category_count = input_dict.get("total_category_count")
    omitted = (total_category_count - len(category_profiles)) if total_category_count else 0
    basket_profile = input_dict.get("basket_profile") or {}
    compact_basket_profile = {field: basket_profile.get(field) for field in _GLOBAL_PROFILE_BASKET_FIELDS}
    return {
        "category_profiles": _render_readable(compact_category_profiles),
        "basket_profile": _render_readable(compact_basket_profile),
        "recent_summaries": "\n".join(
            f"- {_clean_text(summary)}"
            for summary in (input_dict.get("recent_summaries") or [])
            if _clean_text(summary)
        ),
        "category_coverage": (
            f"{len(category_profiles)} of {total_category_count} total categories supplied here "
            f"({omitted} lower-evidence categories omitted from this call)"
            if omitted > 0
            else f"all {len(category_profiles)} of this user's categories are supplied here"
        ),
    }


# Compact feed-profile prompt preparation. The calling service owns temporal
# grouping and storage; these helpers render only the evidence the LLM needs.
def _prepare_feed_category_daypart(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    products = []
    for product in input_dict.get("products") or []:
        products.append(
            {
                "product_name": _clean_text(product.get("product_name")),
                "brand": _clean_text(product.get("brand")),
                "type": _humanize_catalog(product.get("type")),
                "brand_category": _clean_text(product.get("brand_category")),
                "brand_tier": _clean_text(product.get("brand_tier")),
                "price_tier": _clean_text(product.get("price_tier")),
                "pack_size": _clean_text(product.get("pack_size")),
                "ordered_quantity": product.get("ordered_quantity"),
                "product_description": _clean_text(product.get("product_description")),
            }
        )
    return {
        "category": _humanize_catalog(input_dict.get("category")),
        "daypart": _scalar(input_dict.get("daypart")),
        "day_type": _scalar(input_dict.get("day_type")),
        "products": _render_readable(products),
        "commercial_source_text": _commercial_source_text(input_dict.get("products") or []),
    }


def _prepare_feed_location_category_daypart(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    products = []
    for product in input_dict.get("products") or []:
        products.append(
            {
                "product_name": _clean_text(product.get("product_name")),
                "brand": _clean_text(product.get("brand")),
                "type": _humanize_catalog(product.get("type")),
                "brand_category": _clean_text(product.get("brand_category")),
                "brand_tier": _clean_text(product.get("brand_tier")),
                "price_tier": _clean_text(product.get("price_tier")),
                "pack_size": _clean_text(product.get("pack_size")),
                "ordered_quantity": product.get("ordered_quantity"),
                "order_count": product.get("order_count"),
                "buyer_count": product.get("buyer_count"),
                "product_description": _clean_text(product.get("product_description")),
            }
        )
    return {
        "category": _humanize_catalog(input_dict.get("category")),
        "daypart": _scalar(input_dict.get("daypart")),
        "day_type": _scalar(input_dict.get("day_type")),
        "products": _render_readable(products),
        "commercial_source_text": _commercial_source_text(input_dict.get("products") or []),
    }


def _prepare_feed_category_daily(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "category": _humanize_catalog(input_dict.get("category")),
        "day_type": _scalar(input_dict.get("day_type")),
        "daypart_summaries_oldest_to_newest": _render_readable(
            input_dict.get("daypart_summaries") or []
        ),
    }


def _prepare_feed_category_monthly(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "category": _humanize_catalog(input_dict.get("category")),
        "daily_summaries_oldest_to_newest": _render_readable(
            input_dict.get("daily_summaries") or []
        ),
    }


def _prepare_feed_category_profile(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "category": _humanize_catalog(input_dict.get("category")),
        "recent_daypart_summaries_oldest_to_newest": _render_readable(
            input_dict.get("recent_daypart_summaries") or []
        ),
        "recent_daily_summaries_oldest_to_newest": _render_readable(
            input_dict.get("recent_daily_summaries") or []
        ),
        "monthly_summaries_oldest_to_newest": _render_readable(
            input_dict.get("monthly_summaries") or []
        ),
    }


def _prepare_feed_basket_daypart(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "daypart": _scalar(input_dict.get("daypart")),
        "day_type": _scalar(input_dict.get("day_type")),
        "complete_orders": _render_readable(input_dict.get("orders") or []),
    }


def _prepare_feed_basket_daily(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "day_type": _scalar(input_dict.get("day_type")),
        "daypart_summaries_oldest_to_newest": _render_readable(
            input_dict.get("daypart_summaries") or []
        ),
    }


def _prepare_feed_basket_monthly(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "daily_summaries_oldest_to_newest": _render_readable(
            input_dict.get("daily_summaries") or []
        ),
    }


def _prepare_feed_basket_profile(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "recent_daypart_summaries_oldest_to_newest": _render_readable(
            input_dict.get("recent_daypart_summaries") or []
        ),
        "recent_daily_summaries_oldest_to_newest": _render_readable(
            input_dict.get("recent_daily_summaries") or []
        ),
        "monthly_summaries_oldest_to_newest": _render_readable(
            input_dict.get("monthly_summaries") or []
        ),
    }


def _prepare_feed_global_profile(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    categories = []
    for profile in input_dict.get("category_profiles") or []:
        categories.append(
            {
                "category": _humanize_catalog(profile.get("category")),
                "summary_text": _clean_text(profile.get("summary_text")),
            }
        )
    graph = load_category_jump_graph()
    expansions = [target.prompt_dict() for target in graph.select(profile["category"] for profile in categories)]
    return {
        "category_profiles": _render_readable(categories),
        "basket_summary_text": _clean_text(input_dict.get("basket_summary_text")),
        "approved_category_expansions": expansions,
    }


def _prepare_feed_location_global_profile(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    payload = _prepare_feed_global_profile({**input_dict, "basket_summary_text": ""})
    payload.pop("basket_summary_text", None)
    return payload


_COMMERCIAL_VALUES = {
    "brand_category": {"national", "d2c", "cheap", "local"},
    "brand_tier": {"value", "mass", "mass_premium", "premium"},
    "price_tier": {"low", "mid", "high"},
}
_COMMERCIAL_SUMMARY_PATTERN = re.compile(
    r"commercial preference:\s*brand_category=(national|d2c|cheap|local|not_observed);\s*"
    r"brand_tier=(value|mass|mass_premium|premium|not_observed);\s*"
    r"price_tier=(low|mid|high|not_observed)",
    flags=re.IGNORECASE,
)


def _commercial_source_text(products: list[dict[str, Any]]) -> str:
    """Render source commercial facts without asking the LLM to infer them."""
    parts = []
    for field, allowed in _COMMERCIAL_VALUES.items():
        observed = {
            str(product.get(field)).strip().lower()
            for product in products
            if product.get(field) is not None
            and str(product.get(field)).strip().lower() in allowed
        }
        # A scalar runtime boost is safe only for one unambiguous catalog value.
        value = next(iter(observed)) if len(observed) == 1 else "not_observed"
        parts.append(f"{field}={value}")
    return "; ".join(parts)


def validate_feed_category_commercial_output(result: Any, payload: Dict[str, Any]) -> Any:
    """Require one labelled commercial clause inside the sole summary field."""
    values = result.model_dump() if hasattr(result, "model_dump") else dict(result)
    summary_text = str(values.get("summary_text") or "")
    match = _COMMERCIAL_SUMMARY_PATTERN.search(summary_text)
    if not match:
        raise ValueError(
            "summary_text must include a Commercial preference clause with brand_category, "
            "brand_tier, and price_tier using approved values or not_observed"
        )
    source_text = str(payload).lower()
    for field, value in zip(_COMMERCIAL_VALUES, match.groups()):
        if value != "not_observed" and f"{field}={value}" not in source_text:
            raise ValueError(
                f"{field}={value!r} is not explicitly supplied by the preceding category evidence"
            )
    return result


def validate_feed_global_profile_output(result: Any, payload: Dict[str, Any]) -> Any:
    """Reject unsupported commercial preferences instead of silently passing
    an attractive but invented tier into a feed boost.

    This is validation, not a merge or enrichment step: the global task must
    return null unless its category-profile text contains the same supplied
    commercial value. Alfred retries the LLM with the validation failure.
    """
    values = result.model_dump() if hasattr(result, "model_dump") else dict(result)
    evidence = " ".join(
        [str(payload.get("category_profiles") or ""), str(payload.get("basket_summary_text") or "")]
    ).lower()
    for field in ("brand_category", "brand_tier", "price_tier"):
        value = values.get(field)
        if value and str(value).lower() not in evidence:
            raise ValueError(
                f"{field}={value!r} is not explicitly supported by category-profile text; return null"
            )
    categories = {
        match.strip().lower()
        for match in re.findall(r"Category:\s*([^\n]+)", evidence, flags=re.IGNORECASE)
        if match.strip()
    }
    for query in values.get("mission_queries") or []:
        if any(category in query.lower() for category in categories):
            raise ValueError(
                "global mission queries must expand beyond the observed category; "
                f"received {query!r}"
            )
    for query in values.get("product_queries") or []:
        if any(category in query.lower() for category in categories):
            raise ValueError(
                "global product queries must expand beyond the observed category; "
                f"received {query!r}"
            )
    mission_queries = " ".join(values.get("mission_queries") or []).lower()
    product_queries = " ".join(values.get("product_queries") or []).lower()
    for expansion in payload.get("approved_category_expansions") or []:
        required_terms = expansion.get("required_product_query_terms") or []
        if not any(str(term).lower() in product_queries for term in required_terms):
            raise ValueError(
                "global product queries must cover every approved category expansion; "
                f"missing one of {required_terms}"
            )
        if not any(str(term).lower() in mission_queries for term in required_terms):
            raise ValueError(
                "global mission queries must cover every approved category expansion; "
                f"missing one of {required_terms}"
            )
    return result


def validate_feed_profile_query_output(result: Any, payload: Dict[str, Any]) -> Any:
    """Keep brand/SKU phrases in product lanes, not mission lanes."""
    values = result.model_dump() if hasattr(result, "model_dump") else dict(result)
    evidence = str(payload).lower()
    brands = {
        match.strip().lower()
        for match in re.findall(r"Brand:\s*([^\n]+)", evidence, flags=re.IGNORECASE)
        if match.strip() and match.strip().lower() not in {"none", "null"}
    }
    mission_queries = list(values.get("mission_queries") or [])
    for daypart_profile in values.get("daypart_profiles") or []:
        mission_queries.extend(daypart_profile.get("mission_queries") or [])
    for query in mission_queries:
        if any(brand in query.lower() for brand in brands):
            raise ValueError(
                "mission queries must describe a need/use case rather than repeat a brand; "
                f"received {query!r}"
            )
    return result


def validate_feed_category_profile_output(result: Any, payload: Dict[str, Any]) -> Any:
    """Apply summary commercial grounding and retrieval-query safeguards."""
    validate_feed_category_commercial_output(result, payload)
    return validate_feed_profile_query_output(result, payload)


def _prepare_occasion_event_occurrence(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "occasion_type": input_dict.get("occasion_type", ""),
        "occasion_name": input_dict.get("occasion_name", ""),
        "occasion_basket_evidence": _render_readable(
            input_dict.get("basket_summaries") or []
        ),
        "ordinary_baseline_not_occasion": _clean_text(
            input_dict.get("ordinary_baseline_text")
        ),
    }


def _prepare_user_occasion_event_profile(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "occasion_type": input_dict.get("occasion_type", ""),
        "occurrence_summaries": _render_readable(
            input_dict.get("occurrence_summaries") or []
        ),
    }


# Fields each running-profile-update prompt actually needs from its own
# previous output. `retrieval_text` is the prior step's own embedding
# paragraph — every step writes its own, none reads an old one. `evidence`
# (and, for the basket/global tiers, `user_id`/`artifact_type`/
# `profile_type`/`updated_at`) are post-processing-only bookkeeping the
# model was never asked to use.
_RUNNING_CATEGORY_PROFILE_FIELDS = (
    "category_name",
    "summary_text",
    "preferences",
    "daypart_understanding",
    "substitution_text",
    "change_since_last_text",
    "uncertainty_text",
)

_RUNNING_BASKET_PROFILE_FIELDS = (
    "summary_text",
    "basket_relationships",
    "value_text",
    "basket_size_segment",
    "large_basket_tendency",
    "multi_quantity_tendency",
    "daypart_understanding",
    "day_type_understanding",
    "change_since_last_text",
    "uncertainty_text",
)

_RUNNING_PROFILE_FIELDS = (
    "summary_text",
    "daypart_understanding",
    "basket_understanding",
    "shopping_style",
    "change_since_last_text",
    "uncertainty_text",
)


def _prepare_running_category_profile_update(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    previous_category_profile = input_dict.get("previous_category_profile")
    compact_previous = (
        _render_readable({field: previous_category_profile.get(field) for field in _RUNNING_CATEGORY_PROFILE_FIELDS})
        if previous_category_profile
        else "(none supplied — this is this category's first order)"
    )
    return {
        "category": _humanize_catalog(input_dict.get("category")),
        "new_order": _render_readable(input_dict.get("new_order") or {}),
        "recent_orders": _render_readable(input_dict.get("recent_orders") or []),
        "previous_category_profile": compact_previous,
    }


def _prepare_running_basket_profile_update(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    previous_basket_profile = input_dict.get("previous_basket_profile")
    compact_previous = (
        _render_readable({field: previous_basket_profile.get(field) for field in _RUNNING_BASKET_PROFILE_FIELDS})
        if previous_basket_profile
        else "(none supplied — this is this user's first order)"
    )
    return {
        "new_order": _render_readable(input_dict.get("new_order") or {}),
        "recent_orders": _render_readable(input_dict.get("recent_orders") or []),
        "category_pair_evidence": _render_readable(input_dict.get("category_pair_evidence") or []),
        "previous_basket_profile": compact_previous,
    }


# Fields the running global-profile prompt actually needs from each entry in
# category_profiles — same projection the waterfall's global profile uses
# (_GLOBAL_PROFILE_CATEGORY_FIELDS), so both pipelines send comparably lean
# category context into their global synthesis step.
_RUNNING_GLOBAL_CATEGORY_FIELDS = (
    "category_name",
    "summary_text",
    "substitution_text",
    "uncertainty_text",
)

# Fields the running global-profile prompt actually needs from basket_profile
# — same projection the waterfall's global profile uses
# (_GLOBAL_PROFILE_BASKET_FIELDS): drops retrieval_text (this step writes its
# own), evidence/user_id/artifact_type/updated_at (post-processing-only), and
# change_since_last_text (not needed for cross-category synthesis).
_RUNNING_GLOBAL_BASKET_FIELDS = (
    "summary_text",
    "basket_relationships",
    "value_text",
    "basket_size_segment",
    "large_basket_tendency",
    "multi_quantity_tendency",
    "daypart_understanding",
    "day_type_understanding",
    "uncertainty_text",
)


def _prepare_running_profile_update(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    category_profiles = input_dict.get("category_profiles") or []
    compact_category_profiles = [
        {
            **{field: profile.get(field) for field in _RUNNING_GLOBAL_CATEGORY_FIELDS},
            "brands": (profile.get("preferences") or {}).get("brands") or [],
        }
        for profile in category_profiles
    ]
    basket_profile = input_dict.get("basket_profile") or {}
    compact_basket_profile = {field: basket_profile.get(field) for field in _RUNNING_GLOBAL_BASKET_FIELDS}
    previous_profile = input_dict.get("previous_profile")
    compact_previous_profile = (
        _render_readable({field: previous_profile.get(field) for field in _RUNNING_PROFILE_FIELDS})
        if previous_profile
        else "(none supplied — this is this user's first order)"
    )
    return {
        "category_profiles": _render_readable(compact_category_profiles),
        "basket_profile": _render_readable(compact_basket_profile),
        "previous_profile": compact_previous_profile,
    }


def _prepare_feed_quality_review(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "daypart": input_dict.get("daypart"),
        "global_profile": _render_readable(input_dict.get("global_profile") or {}),
        "category_profiles": _render_readable(input_dict.get("category_profiles") or []),
        "basket_profile": _render_readable(input_dict.get("basket_profile") or {}),
        "recent_summaries": "\n".join(
            f"- {_clean_text(summary)}"
            for summary in (input_dict.get("recent_summaries") or [])
            if _clean_text(summary)
        ),
        "eligible_mission_names": "\n".join(
            f"- {name}" for name in (input_dict.get("eligible_mission_names") or [])
        ),
        "selected_missions": _render_readable(input_dict.get("selected_missions") or []),
        "selected_products": _render_readable(input_dict.get("selected_products") or []),
    }


TASKS: Dict[str, Dict[str, Any]] = {
    "test_task": {
        "input_model": TestInput,
        "output_model": TestResponse,
        "instruction": TEST_TASK,
        "endpoint": "/test",
        "load_level": "high",
    },
    "fetch_product_knowledge": {
        "input_model": ProductKnowledgeInput,
        "output_model": ProductKnowledgeFetchedOutput,
        "response_model": ProductKnowledgeOutput,
        "drop_fields": ["source_urls"],
        "instruction": FETCH_PRODUCT_KNOWLEDGE,
        "endpoint": "/v1/llm/knowledge/fetch-product",
        "load_level": "high",
        "prepare_input": _prepare_product_knowledge,
    },
    "product_semantic_paragraph": {
        "input_model": ProductParagraphInput,
        "output_model": ProductParagraphOutput,
        "instruction": PRODUCT_SEMANTIC_PARAGRAPH,
        "endpoint": "/v1/llm/enrich/product-paragraph",
        "load_level": "medium",
    },
    "mission_semantic_document": {
        "input_model": MissionSemanticDocumentInput,
        "output_model": MissionSemanticDocumentOutput,
        "instruction": MISSION_SEMANTIC_DOCUMENT,
        "endpoint": "/v1/llm/mission/semantic-document",
        "load_level": "medium",
        "max_tokens": 1000,
        "prepare_input": _prepare_mission_semantic_document,
    },
    "query_improvement": {
        "input_model": QueryInput,
        "output_model": QueryImprovement,
        "instruction": QUERY_IMPROVEMENT,
        "endpoint": "/improve-query",
        "load_level": "medium",
    },
    "query_parse": {
        "input_model": QueryInput,
        "output_model": QueryParsed,
        "instruction": QUERY_PARSE,
        "endpoint": "/parse-query",
        "load_level": "medium",
    },
    "user_hourly_summary": {
        "input_model": HourlyActivityInput,
        "output_model": ActivitySummary,
        "instruction": USER_HOURLY_SUMMARY,
        "endpoint": "/user/hourly-summary",
        "load_level": "medium",
    },
    "user_aggregate_summary": {
        "input_model": SummaryAggregationInput,
        "output_model": ActivitySummary,
        "instruction": USER_AGGREGATE_SUMMARY,
        "endpoint": "/user/aggregate-summary",
        "load_level": "medium",
    },
    "user_category_profile": {
        "input_model": UserCategoryProfileInput,
        "output_model": UserProfile,
        "instruction": USER_CATEGORY_PROFILE,
        "endpoint": "/user/category-profile",
        "load_level": "medium",
    },
    "user_cross_category_profile": {
        "input_model": CrossCategoryProfileInput,
        "output_model": UserProfile,
        "instruction": USER_CROSS_CATEGORY_PROFILE,
        "endpoint": "/user/cross-category-profile",
        "load_level": "medium",
    },
    "user_category_daypart_summary": {
        "input_model": FeedCategoryDaypartInput,
        "output_model": FeedSummaryOutput,
        "instruction": FEED_USER_CATEGORY_DAYPART_SUMMARY,
        "endpoint": "/user/category/daypart-summary",
        "load_level": "medium",
        "max_tokens": 350,
        "repair": 3,
        "prepare_input": _prepare_feed_category_daypart,
        "postprocess_output": validate_feed_category_commercial_output,
        "postprocess_retries": 3,
    },
    "user_category_daily_summary": {
        "input_model": FeedCategoryDailyInput,
        "output_model": FeedSummaryOutput,
        "instruction": FEED_USER_CATEGORY_DAILY_SUMMARY,
        "endpoint": "/user/category/daily-summary",
        "load_level": "medium",
        "max_tokens": 350,
        "repair": 3,
        "prepare_input": _prepare_feed_category_daily,
        "postprocess_output": validate_feed_category_commercial_output,
        "postprocess_retries": 3,
    },
    "user_category_monthly_summary": {
        "input_model": FeedCategoryMonthlyInput,
        "output_model": FeedSummaryOutput,
        "instruction": FEED_USER_CATEGORY_MONTHLY_SUMMARY,
        "endpoint": "/user/category/monthly-summary",
        "load_level": "medium",
        "max_tokens": 400,
        "repair": 3,
        "prepare_input": _prepare_feed_category_monthly,
        "postprocess_output": validate_feed_category_commercial_output,
        "postprocess_retries": 3,
    },
    "user_category_preference_profile": {
        "input_model": FeedCategoryProfileInput,
        "output_model": FeedProfileOutput,
        "instruction": FEED_USER_CATEGORY_PROFILE,
        "endpoint": "/user/category/preference-profile",
        "load_level": "medium",
        "max_tokens": 900,
        "repair": 3,
        "prepare_input": _prepare_feed_category_profile,
        "postprocess_output": validate_feed_category_profile_output,
        "postprocess_retries": 3,
    },
    "user_basket_daypart_summary": {
        "input_model": FeedBasketDaypartInput,
        "output_model": FeedSummaryOutput,
        "instruction": FEED_USER_BASKET_DAYPART_SUMMARY,
        "endpoint": "/user/basket/daypart-summary",
        "load_level": "medium",
        "max_tokens": 350,
        "repair": 3,
        "prepare_input": _prepare_feed_basket_daypart,
    },
    "user_basket_daily_summary": {
        "input_model": FeedBasketDailyInput,
        "output_model": FeedSummaryOutput,
        "instruction": FEED_USER_BASKET_DAILY_SUMMARY,
        "endpoint": "/user/basket/daily-summary",
        "load_level": "medium",
        "max_tokens": 350,
        "repair": 3,
        "prepare_input": _prepare_feed_basket_daily,
    },
    "user_basket_monthly_summary": {
        "input_model": FeedBasketMonthlyInput,
        "output_model": FeedSummaryOutput,
        "instruction": FEED_USER_BASKET_MONTHLY_SUMMARY,
        "endpoint": "/user/basket/monthly-summary",
        "load_level": "medium",
        "max_tokens": 400,
        "repair": 3,
        "prepare_input": _prepare_feed_basket_monthly,
    },
    "user_basket_profile": {
        "input_model": FeedBasketProfileInput,
        "output_model": FeedProfileOutput,
        "instruction": FEED_USER_BASKET_PROFILE,
        "endpoint": "/user/basket/profile",
        "load_level": "medium",
        "max_tokens": 900,
        "repair": 3,
        "prepare_input": _prepare_feed_basket_profile,
        "postprocess_output": validate_feed_profile_query_output,
        "postprocess_retries": 3,
    },
    "user_global_profile": {
        "input_model": FeedGlobalProfileInput,
        "output_model": FeedGlobalProfileOutput,
        "instruction": FEED_USER_GLOBAL_PROFILE,
        "endpoint": "/user/global-profile",
        "load_level": "medium",
        "max_tokens": 900,
        "repair": 3,
        "prepare_input": _prepare_feed_global_profile,
        "postprocess_output": validate_feed_global_profile_output,
        "postprocess_retries": 3,
    },
    "location_category_daypart_summary": {
        "input_model": FeedLocationCategoryDaypartInput,
        "output_model": FeedSummaryOutput,
        "instruction": FEED_LOCATION_CATEGORY_DAYPART_SUMMARY,
        "endpoint": "/location/category/daypart-summary",
        "load_level": "medium",
        "max_tokens": 350,
        "repair": 3,
        "prepare_input": _prepare_feed_location_category_daypart,
        "postprocess_output": validate_feed_category_commercial_output,
        "postprocess_retries": 3,
    },
    "location_category_daily_summary": {
        "input_model": FeedLocationCategoryDailyInput,
        "output_model": FeedSummaryOutput,
        "instruction": FEED_LOCATION_CATEGORY_DAILY_SUMMARY,
        "endpoint": "/location/category/daily-summary",
        "load_level": "medium",
        "max_tokens": 350,
        "repair": 3,
        "prepare_input": _prepare_feed_category_daily,
        "postprocess_output": validate_feed_category_commercial_output,
        "postprocess_retries": 3,
    },
    "location_category_monthly_summary": {
        "input_model": FeedLocationCategoryMonthlyInput,
        "output_model": FeedSummaryOutput,
        "instruction": FEED_LOCATION_CATEGORY_MONTHLY_SUMMARY,
        "endpoint": "/location/category/monthly-summary",
        "load_level": "medium",
        "max_tokens": 400,
        "repair": 3,
        "prepare_input": _prepare_feed_category_monthly,
        "postprocess_output": validate_feed_category_commercial_output,
        "postprocess_retries": 3,
    },
    "location_category_profile": {
        "input_model": FeedLocationCategoryProfileInput,
        "output_model": FeedProfileOutput,
        "instruction": FEED_LOCATION_CATEGORY_PROFILE,
        "endpoint": "/location/category/profile",
        "load_level": "medium",
        "max_tokens": 900,
        "repair": 3,
        "prepare_input": _prepare_feed_category_profile,
        "postprocess_output": validate_feed_category_profile_output,
        "postprocess_retries": 3,
    },
    "location_global_profile": {
        "input_model": FeedLocationGlobalProfileInput,
        "output_model": FeedGlobalProfileOutput,
        "instruction": FEED_LOCATION_GLOBAL_PROFILE,
        "endpoint": "/location/global-profile",
        "load_level": "medium",
        "max_tokens": 900,
        "repair": 3,
        "prepare_input": _prepare_feed_location_global_profile,
        "postprocess_output": validate_feed_global_profile_output,
        "postprocess_retries": 3,
    },
    "user_category_jump_exploratory_queries": {
        "input_model": CategorySummaryExploratoryInput,
        "output_model": CategorySummaryExploratoryOutput,
        "instruction": USER_CATEGORY_JUMP_EXPLORATORY_QUERIES,
        "endpoint": "/user/global/exploratory-queries",
        "load_level": "medium",
        "max_tokens": 1800,
        "repair": 3,
        "postprocess_retries": 4,
        "prepare_input": prepare_exploratory_prompt,
        "postprocess_output": validate_exploratory_output,
    },
    "user_running_category_profile_update": {
        "input_model": RunningCategoryProfileInput,
        "output_model": RunningCategoryProfileOutput,
        "instruction": USER_RUNNING_CATEGORY_PROFILE_UPDATE,
        "endpoint": "/user/running-profile/category-update",
        "load_level": "medium",
        # Higher than user_category_preference_profile's 3500 despite the
        # same output shape: that waterfall task reads monthly_summaries,
        # text already filtered down to stable relationships by the daily ->
        # monthly stages. This task reads this category's raw rolling window
        # directly and must do that same noise-filtering itself, every call,
        # while also reconciling against previous_category_profile — real
        # 502 parse_error/truncation failures at 3500 confirmed this needed
        # more room in practice.
        "max_tokens": 5000,
        "repair": 3,
        "prepare_input": _prepare_running_category_profile_update,
    },
    "user_running_basket_profile_update": {
        "input_model": RunningBasketProfileInput,
        "output_model": RunningBasketProfileOutput,
        "instruction": USER_RUNNING_BASKET_PROFILE_UPDATE,
        "endpoint": "/user/running-profile/basket-update",
        "load_level": "medium",
        # Higher than user_basket_profile's 3500 despite the same output
        # shape: that waterfall task reads monthly_summaries whose
        # category_combination_patterns were already filtered to stable,
        # repeated relationships by the daily -> monthly stages. This task
        # reads the raw basket-level rolling window directly (up to
        # window_size orders, any category — cross-category combinatorics
        # grow with how many categories this user has) and must do that same
        # noise-filtering itself, every call, while also reconciling against
        # previous_basket_profile. Confirmed in practice: 3500 produced a
        # genuine (non-repetition) truncation for a 17-category, 27-order
        # user whose entire history still fit in one window.
        "max_tokens": 6000,
        "repair": 3,
        "prepare_input": _prepare_running_basket_profile_update,
    },
    "user_running_profile_update": {
        "input_model": RunningProfileInput,
        "output_model": RunningProfileOutput,
        "instruction": USER_RUNNING_PROFILE_UPDATE,
        "endpoint": "/user/running-profile/update",
        "load_level": "medium",
        # category_profiles grows with how many categories this user has
        # touched (same heavy-tail concern as user_global_profile's own
        # max_tokens note) — matched to that value rather than the lower
        # one this started with.
        "max_tokens": 6000,
        "repair": 3,
        "prepare_input": _prepare_running_profile_update,
    },
    "user_feed_quality_review": {
        "input_model": FeedQualityReviewInput,
        "output_model": FeedQualityReviewOutput,
        "instruction": USER_FEED_QUALITY_REVIEW,
        "endpoint": "/user/feed-quality-review",
        "load_level": "medium",
        "max_tokens": 700,
        "prepare_input": _prepare_feed_quality_review,
    },
    "user_occasion_event_occurrence_summary": {
        "input_model": OccasionEventOccurrenceSummaryInput,
        "output_model": OccasionEventOccurrenceSummaryOutput,
        "instruction": OCCASION_EVENT_OCCURRENCE_SUMMARY,
        "endpoint": "/user/occasion/occurrence-summary",
        "load_level": "medium",
        "max_tokens": 900,
        "prepare_input": _prepare_occasion_event_occurrence,
    },
    "user_occasion_event_profile": {
        "input_model": UserOccasionEventProfileInput,
        "output_model": UserOccasionEventProfileOutput,
        "instruction": USER_OCCASION_EVENT_PROFILE,
        "endpoint": "/user/occasion/profile",
        "load_level": "medium",
        "max_tokens": 1100,
        "prepare_input": _prepare_user_occasion_event_profile,
    },
    "user_mission_hourly_summary": {
        "input_model": MissionHourlySummaryInput,
        "output_model": MissionHourlySummaryOutput,
        "instruction": USER_MISSION_HOURLY_SUMMARY,
        "endpoint": "/user/mission-hourly-summary",
        "load_level": "medium",
    },
    "user_mission_aggregate_summary": {
        "input_model": MissionAggregateSummaryInput,
        "output_model": MissionAggregateSummaryOutput,
        "instruction": USER_MISSION_AGGREGATE_SUMMARY,
        "endpoint": "/user/mission-aggregate-summary",
        "load_level": "medium",
    },
    "user_mission_global_profile": {
        "input_model": MissionGlobalProfileInput,
        "output_model": MissionGlobalProfileOutput,
        "instruction": USER_MISSION_GLOBAL_PROFILE,
        "endpoint": "/user/mission-global-profile",
        "load_level": "medium",
    },
}


OPTIONAL_TASKS = [
    (
        "feed_query_generation",
        {
            "input_model": CrossCategoryProfileInput,
            "output_model": FeedQueries,
            "instruction_name": "FEED_QUERY_GENERATION",
            "endpoint": "/user/feed-queries",
            "load_level": "medium",
        },
    ),
]

for task_name, config in OPTIONAL_TASKS:
    instruction = getattr(instructions, config["instruction_name"], None)
    if instruction:
        TASKS[task_name] = {
            "input_model": config["input_model"],
            "output_model": config["output_model"],
            "instruction": instruction,
            "endpoint": config["endpoint"],
            "load_level": config["load_level"],
        }


def get_task_names():
    return list(TASKS.keys())


def get_task_config(task_name: str):
    return TASKS.get(task_name)


def get_enabled_tasks(enabled_task_names):
    enabled = {}
    for task_name in enabled_task_names:
        if task_name in TASKS:
            enabled[task_name] = TASKS[task_name]
        else:
            print(f"Warning: Task '{task_name}' not found in available tasks")
            print(f"Available tasks: {', '.join(get_task_names())}")
    return enabled
